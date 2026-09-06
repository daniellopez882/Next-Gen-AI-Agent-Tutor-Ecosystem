"""
The HTTP surface.

The endpoint runs LangGraph + crewai on every call and was unauthenticated
with an unbounded ``task`` and ``allow_origins=["*"]``.
"""

from __future__ import annotations

import pytest

from config import settings
from tests.conftest import AUTH, PROFILE

VALID = {"task": "teach me fractions", "student": PROFILE}


class TestAuthentication:
    def test_solve_is_rejected_without_a_key(self, client):
        client.install_graph({"final_response": {}})
        assert client.post("/api/v1/tutor/solve", json=VALID).status_code == 401

    def test_solve_is_rejected_with_a_wrong_key(self, client):
        client.install_graph({"final_response": {}})
        r = client.post(
            "/api/v1/tutor/solve", json=VALID, headers={"X-API-Key": "nope"}
        )
        assert r.status_code == 401
        assert r.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_the_configured_key_is_not_echoed(self, client):
        r = client.post(
            "/api/v1/tutor/solve", json=VALID, headers={"X-API-Key": "nope"}
        )
        assert AUTH["X-API-Key"] not in r.text

    def test_health_and_ready_need_no_key(self, client):
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code in (200, 503)


class TestInputLimits:
    def test_an_oversized_task_is_rejected(self, client):
        body = {"task": "x" * (settings.MAX_TASK_CHARS + 1), "student": PROFILE}
        assert (
            client.post("/api/v1/tutor/solve", json=body, headers=AUTH).status_code
            == 422
        )

    def test_an_empty_task_is_rejected(self, client):
        assert (
            client.post(
                "/api/v1/tutor/solve",
                json={"task": "", "student": PROFILE},
                headers=AUTH,
            ).status_code
            == 422
        )

    @pytest.mark.parametrize("student_id", ["has space", "a/b", "x" * 65, ""])
    def test_a_malformed_student_id_is_rejected(self, client, student_id):
        body = {"task": "hi", "student": {**PROFILE, "student_id": student_id}}
        assert (
            client.post("/api/v1/tutor/solve", json=body, headers=AUTH).status_code
            == 422
        )

    def test_an_out_of_range_age_is_rejected(self, client):
        body = {"task": "hi", "student": {**PROFILE, "age": 500}}
        assert (
            client.post("/api/v1/tutor/solve", json=body, headers=AUTH).status_code
            == 422
        )


class TestSolve:
    def test_a_successful_task_returns_the_agent_and_response(self, client):
        graph = client.install_graph(
            {
                "classification": {"next_agent": "quiz_generator"},
                "final_response": {"agent": "QuizGenerator", "output": {"q": 1}},
            }
        )
        r = client.post("/api/v1/tutor/solve", json=VALID, headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["agent_invoked"] == "quiz_generator"
        assert body["response"]["output"] == {"q": 1}
        assert graph.seen[0]["task_input"] == "teach me fractions"

    def test_a_graph_failure_returns_a_request_id_not_the_exception(
        self, client, monkeypatch
    ):
        import agent_graph
        import main

        class Boom:
            def invoke(self, state):
                raise RuntimeError("sk-live-SECRET leaked from a provider")

        monkeypatch.setattr(agent_graph, "get_graph", lambda: Boom())
        monkeypatch.setattr(main, "get_graph", lambda: Boom(), raising=False)
        r = client.post("/api/v1/tutor/solve", json=VALID, headers=AUTH)
        assert r.status_code == 500
        assert "SECRET" not in r.text
        assert r.json()["detail"]["request_id"]

    def test_progress_tracker_output_updates_mastery(self, client):
        import database

        client.install_graph(
            {
                "classification": {"next_agent": "progress_tracker"},
                "final_response": {
                    "output": {"mastery_map": {"Math": {"fractions": {"score": 88}}}}
                },
            }
        )
        client.post(
            "/api/v1/tutor/solve",
            json={"task": "how am I doing", "student": PROFILE},
            headers=AUTH,
        )
        assert database.get_student_mastery("STU_1").get("fractions") == 88


class TestReadiness:
    def test_ready_reports_each_check(self, client):
        checks = client.get("/ready").json()["checks"]
        assert set(checks) == {"model_provider", "api_key", "frontend"}

    def test_the_dashboard_is_served(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "<title>" in r.text
