"""
The LangGraph workflow: an orchestrator that classifies a task and routes it
to one of five specialists.

Changes:

* The orchestrator, progress and parent nodes each did their own
  ``.replace('```json','')`` + ``json.loads``; all three go through the one
  extractor now, so a reply with prose around its JSON no longer silently
  falls back to the doubt resolver.
* Models come from ``llm`` (the seam the tests use), not from three copies of
  a hardcoded-model factory.
* The graph is built once via ``get_graph()`` rather than at import, so
  importing this module does not require a model provider.
* ``route_task`` returns a node that is always in the conditional-edge map;
  an unrecognised classification maps to the doubt resolver rather than
  raising inside LangGraph.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

import rag_pipeline
from crew_agents import run_doubt_resolver, run_lesson_personalizer, run_quiz_generator
from education_tutor_prompts import (
    ORCHESTRATOR_PROMPT,
    PARENT_REPORTER_PROMPT,
    PROGRESS_TRACKER_PROMPT,
    build_agent_prompt_with_student,
)
from json_extraction import extract_json
from llm import get_langchain_model

logger = logging.getLogger("lumina.graph")

SPECIALISTS = (
    "lesson_personalizer",
    "quiz_generator",
    "doubt_resolver",
    "progress_tracker",
    "parent_reporter",
)
FALLBACK = "doubt_resolver"

# substring in the model's task_type -> node
TASK_TYPE_TO_NODE = {
    "lesson": "lesson_personalizer",
    "quiz": "quiz_generator",
    "progress": "progress_tracker",
    "report": "parent_reporter",
    "doubt": "doubt_resolver",
}


class TutorState(TypedDict, total=False):
    task_input: str
    student_profile: dict[str, Any]
    classification: dict[str, Any]
    final_response: dict[str, Any]


def _classify(task_type: str) -> str:
    for needle, node in TASK_TYPE_TO_NODE.items():
        if needle in (task_type or "").lower():
            return node
    return FALLBACK


def orchestrator_node(state: TutorState) -> dict:
    task = state.get("task_input", "")
    messages = [
        SystemMessage(content=ORCHESTRATOR_PROMPT),
        HumanMessage(
            content=f"Classify this task and return the required JSON: '{task}'"
        ),
    ]
    try:
        reply = get_langchain_model("orchestrator").invoke(messages)
        classification = extract_json(getattr(reply, "content", "") or "")
    except Exception:
        logger.exception("orchestrator failed; routing to the doubt resolver")
        classification = {}
    classification["next_agent"] = _classify(str(classification.get("task_type", "")))
    return {"classification": classification}


def lesson_personalizer_node(state: TutorState) -> dict:
    output = run_lesson_personalizer(
        state.get("student_profile", {}), state.get("task_input", "")
    )
    return {"final_response": {"agent": "LessonPersonalizer", "output": output}}


def quiz_generator_node(state: TutorState) -> dict:
    output = run_quiz_generator(
        state.get("student_profile", {}), state.get("task_input", "")
    )
    return {"final_response": {"agent": "QuizGenerator", "output": output}}


def doubt_resolver_node(state: TutorState) -> dict:
    task = state.get("task_input", "")
    retrieval = rag_pipeline.retrieve(task, n_results=2)
    output = run_doubt_resolver(
        state.get("student_profile", {}), task, retrieval.documents
    )
    return {
        "final_response": {
            "agent": "DoubtResolver",
            "output": output,
            "rag_context_used": retrieval.documents,
            "rag_source": retrieval.source,
        }
    }


def _reasoning_node(state: TutorState, prompt: str, agent_name: str) -> dict:
    profile = state.get("student_profile", {})
    task = state.get("task_input", "")
    messages = [
        SystemMessage(content=build_agent_prompt_with_student(prompt, profile)),
        HumanMessage(
            content=f"Process this request and return the structured JSON: '{task}'"
        ),
    ]
    try:
        reply = get_langchain_model("reasoning").invoke(messages)
        output = extract_json(getattr(reply, "content", "") or "")
    except Exception as error:
        logger.exception("%s failed", agent_name)
        output = {"error": f"{agent_name} failed", "details": type(error).__name__}
    return {"final_response": {"agent": agent_name, "output": output}}


def progress_tracker_node(state: TutorState) -> dict:
    return _reasoning_node(state, PROGRESS_TRACKER_PROMPT, "ProgressTracker")


def parent_reporter_node(state: TutorState) -> dict:
    return _reasoning_node(state, PARENT_REPORTER_PROMPT, "ParentReporter")


def route_task(state: TutorState) -> str:
    node = state.get("classification", {}).get("next_agent", FALLBACK)
    return node if node in SPECIALISTS else FALLBACK


def build_graph():
    workflow = StateGraph(TutorState)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("lesson_personalizer", lesson_personalizer_node)
    workflow.add_node("quiz_generator", quiz_generator_node)
    workflow.add_node("doubt_resolver", doubt_resolver_node)
    workflow.add_node("progress_tracker", progress_tracker_node)
    workflow.add_node("parent_reporter", parent_reporter_node)

    workflow.set_entry_point("orchestrator")
    workflow.add_conditional_edges(
        "orchestrator", route_task, {name: name for name in SPECIALISTS}
    )
    for name in SPECIALISTS:
        workflow.add_edge(name, END)
    return workflow.compile()


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()
