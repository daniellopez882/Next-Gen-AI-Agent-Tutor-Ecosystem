"""
Shared fixtures. No test reaches a network, a model, or a real vector store.

Environment is set before ``config`` is imported: settings are built at import.
The database and Chroma paths point into a temp directory so a test run leaves
nothing behind.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp())
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("API_KEY", "test-key-not-real")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-real")
os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://localhost:8000")
os.environ.setdefault("DB_PATH", str(_TMP / "tutor.db"))
os.environ.setdefault("CHROMA_PATH", str(_TMP / "chroma"))

import database  # noqa: E402

AUTH = {"X-API-Key": os.environ["API_KEY"]}
PROFILE = {"student_id": "STU_1", "name": "Alex", "grade_level": "Grade 8", "age": 13}


@pytest.fixture(scope="session", autouse=True)
def _db():
    database.init_db()


@pytest.fixture
def client(monkeypatch):
    """A TestClient whose graph is replaced, so no model is ever called."""
    import agent_graph
    from fastapi.testclient import TestClient

    import main

    class FakeGraph:
        def __init__(self, result):
            self.result = result
            self.seen = []

        def invoke(self, state):
            self.seen.append(state)
            return {**state, **self.result}

    def install(result):
        graph = FakeGraph(result)
        monkeypatch.setattr(agent_graph, "get_graph", lambda: graph)
        monkeypatch.setattr(main, "get_graph", lambda: graph, raising=False)
        # main imports get_graph lazily inside the handler, from agent_graph.
        return graph

    with TestClient(main.app) as test_client:
        test_client.install_graph = install  # type: ignore[attr-defined]
        yield test_client


@pytest.fixture
def fake_langchain(monkeypatch):
    """Install a LangChain-style model that returns a fixed reply for graph-node tests."""
    import llm

    class Reply:
        def __init__(self, content):
            self.content = content

    class Model:
        def __init__(self, content):
            self.content = content
            self.seen = []

        def invoke(self, messages):
            self.seen.append(messages)
            return Reply(self.content)

    def install(content):
        model = Model(content)
        llm.set_langchain_factory(lambda role: model)
        return model

    yield install
    llm.set_langchain_factory(None)


@pytest.fixture(autouse=True)
def _reset_llm():
    yield
    import llm

    llm.set_langchain_factory(None)
    llm.set_crew_factory(None)
