"""
HTTP surface for Lumina.

Changes over the previous revision:

* ``/api/v1/tutor/solve`` runs LangGraph + crewai -- paid model calls -- on
  every request, and was unauthenticated. Anyone reaching the port could
  spend the operator's API credit. It now requires ``X-API-Key``.
* ``task`` was unbounded; a single request could carry an arbitrarily large
  string into a model call. It is capped.
* ``allow_origins=["*"]`` with ``allow_credentials=True`` is replaced by a
  configured allowlist; the page is served from this app, so it is same-origin.
* ``detail=str(e)`` returned provider and internal exception text to the
  caller; errors now carry a correlation id and the detail goes to the log.
* ``database.init_db()`` and the ChromaDB seed ran as import side effects;
  they run in the lifespan now.
* Adds ``/ready`` and serves the frontend at ``/``.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import database
from config import settings

logger = logging.getLogger("lumina.api")

FRONTEND = Path(__file__).resolve().parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=settings.LOG_LEVEL, format="%(levelname)-8s %(name)s %(message)s"
    )
    if settings.is_production:
        settings.validate_production()
    database.init_db()
    logger.info("ready: environment=%s", settings.ENVIRONMENT)
    yield


app = FastAPI(
    title="Lumina AI",
    description="Multi-agent tutoring: an orchestrator routes a task to a specialist agent.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    openapi_url=None if settings.is_production else "/openapi.json",
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Depends(_api_key_header)) -> None:
    if not api_key or not secrets.compare_digest(api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "X-API-Key"},
        )


class StudentProfile(BaseModel):
    student_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=100)
    grade_level: str = Field(min_length=1, max_length=40)
    age: int = Field(ge=3, le=120)
    learning_style: str = Field(default="reading", max_length=40)
    language: str = Field(default="English", max_length=40)


class TaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=settings.MAX_TASK_CHARS)
    student: StudentProfile
    context: dict[str, Any] | None = None


@app.get("/health", tags=["ops"])
async def health() -> dict[str, Any]:
    return {"status": "ok", "environment": settings.ENVIRONMENT, "version": app.version}


@app.get("/ready", tags=["ops"])
async def ready() -> JSONResponse:
    checks = {
        "model_provider": {"ok": settings.has_model_provider, "required": True},
        "api_key": {
            "ok": not (settings.is_production and settings.has_insecure_api_key),
            "required": True,
        },
        "frontend": {"ok": (FRONTEND / "index.html").is_file(), "required": False},
    }
    is_ready = all(c["ok"] for c in checks.values() if c["required"])
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"ready": is_ready, "checks": checks},
    )


@app.post(
    "/api/v1/tutor/solve", dependencies=[Depends(require_api_key)], tags=["tutor"]
)
async def solve_tutor_task(
    request: TaskRequest, http_request: Request
) -> dict[str, Any]:
    correlation_id = http_request.headers.get("X-Request-ID") or uuid.uuid4().hex
    student = request.student.model_dump()
    student_id = student["student_id"]
    student["mastery_levels"] = database.get_student_mastery(student_id)
    database.upsert_student(student)

    from agent_graph import get_graph

    state = {
        "task_input": request.task,
        "student_profile": student,
        "classification": {},
        "final_response": None,
    }
    try:
        final_state = get_graph().invoke(state)
    except Exception:
        logger.exception("tutor task failed [%s]", correlation_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "processing_failed",
                "message": "The task could not be processed.",
                "request_id": correlation_id,
            },
        ) from None

    agent_invoked = final_state.get("classification", {}).get("next_agent", "unknown")
    response = final_state.get("final_response") or {}
    database.log_session(student_id, agent_invoked, request.task, response)

    if agent_invoked == "progress_tracker":
        mastery_map = (response.get("output") or {}).get("mastery_map", {})
        if isinstance(mastery_map, dict):
            for topics in mastery_map.values():
                if isinstance(topics, dict):
                    for topic_name, details in topics.items():
                        if isinstance(details, dict) and isinstance(
                            details.get("score"), int
                        ):
                            database.update_topic_mastery(
                                student_id, topic_name, details["score"]
                            )

    return {"status": "success", "agent_invoked": agent_invoked, "response": response}


# The dashboard is served by this app, so browser requests are same-origin.
if (FRONTEND / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
else:
    logger.warning("frontend/ not found at %s; the dashboard is not served", FRONTEND)


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.environ.get("BIND_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )
