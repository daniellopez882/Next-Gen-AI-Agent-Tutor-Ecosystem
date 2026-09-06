"""
Routing, the JSON extractor, the frontend, and configuration.
"""

from __future__ import annotations

import pathlib

import pytest

import agent_graph
from agent_graph import SPECIALISTS, _classify, route_task
from config import Settings
from json_extraction import extract_json

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestClassification:
    @pytest.mark.parametrize(
        "task_type,node",
        [
            ("lesson", "lesson_personalizer"),
            ("quiz", "quiz_generator"),
            ("progress_report", "progress_tracker"),
            ("parent_report", "parent_reporter"),
            ("doubt", "doubt_resolver"),
            ("", "doubt_resolver"),
            ("something unknown", "doubt_resolver"),
        ],
    )
    def test_task_type_maps_to_a_node(self, task_type, node):
        assert _classify(task_type) == node

    def test_route_task_only_returns_a_known_node(self):
        assert (
            route_task({"classification": {"next_agent": "nonsense"}})
            == "doubt_resolver"
        )
        assert route_task({}) == "doubt_resolver"
        for name in SPECIALISTS:
            assert route_task({"classification": {"next_agent": name}}) == name


class TestOrchestratorNode:
    def test_it_parses_json_with_prose_around_it(self, fake_langchain):
        fake_langchain('Sure! Here is the classification: {"task_type": "quiz"}')
        out = agent_graph.orchestrator_node({"task_input": "test me"})
        assert out["classification"]["next_agent"] == "quiz_generator"

    def test_a_model_failure_falls_back_to_the_doubt_resolver(self, monkeypatch):
        import llm

        def boom(role):
            raise RuntimeError("provider down")

        llm.set_langchain_factory(boom)
        out = agent_graph.orchestrator_node({"task_input": "x"})
        assert out["classification"]["next_agent"] == "doubt_resolver"
        llm.set_langchain_factory(None)


class TestJsonExtraction:
    def test_a_bare_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_prose_before_and_after(self):
        assert extract_json('Here you go: {"a": 1} hope that helps') == {"a": 1}

    def test_a_fenced_block(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_a_case_insensitive_fence(self):
        assert extract_json('```JSON\n{"a": 1}\n```') == {"a": 1}

    def test_a_brace_in_a_string_does_not_end_the_object(self):
        assert extract_json('{"note": "use { and }"}') == {"note": "use { and }"}

    @pytest.mark.parametrize("bad", ["", "   ", "no json", None])
    def test_unparseable_input_returns_an_error_dict_not_a_raise(self, bad):
        result = extract_json(bad)
        assert "error" in result

    def test_a_default_is_returned_when_given(self):
        assert extract_json("nope", default={"fallback": True}) == {"fallback": True}


class TestFrontend:
    PAGE = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    # Strip `//` line comments before asserting: the comments explain the old
    # behaviour, so they legitimately contain the very strings these guards
    # forbid in the executable code.
    _RAW_JS = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    JS = "\n".join(line.split("//", 1)[0] for line in _RAW_JS.splitlines())

    def test_the_page_calls_the_api_same_origin(self):
        assert "127.0.0.1:8000" not in self.JS
        assert '"/api/v1/tutor/solve"' in self.JS

    def test_the_page_sends_the_api_key(self):
        assert '"X-API-Key"' in self.JS
        assert 'id="api-key"' in self.PAGE

    def test_user_text_is_escaped(self):
        """The old code did `<p>${text}</p>` unescaped for user and system text."""
        assert "escapeHtml(text)" in self.JS
        assert "${text}" not in self.JS  # nothing interpolated without escaping

    def test_the_key_lives_in_session_storage(self):
        assert "sessionStorage" in self.JS
        assert "localStorage" not in self.JS


class TestSettings:
    def build(self, **kw):
        base = {
            "_env_file": None,
            "API_KEY": "k",
            "OPENAI_API_KEY": "x",
            "CORS_ALLOW_ORIGINS": "http://a",
        }
        base.update(kw)
        return Settings(**base)

    def test_the_placeholder_key_is_flagged(self):
        assert self.build(API_KEY="changeme-in-production").has_insecure_api_key is True

    def test_production_validation_lists_every_gap(self):
        with pytest.raises(ValueError) as exc:
            self.build(
                API_KEY="changeme-in-production",
                OPENAI_API_KEY="",
                ANTHROPIC_API_KEY="",
                CORS_ALLOW_ORIGINS="",
            ).validate_production()
        message = str(exc.value)
        assert "API_KEY" in message and "provider" in message and "CORS" in message

    def test_a_complete_configuration_passes(self):
        self.build().validate_production()

    def test_cors_origins_are_split(self):
        assert self.build(CORS_ALLOW_ORIGINS="http://a, http://b").cors_origins == [
            "http://a",
            "http://b",
        ]
