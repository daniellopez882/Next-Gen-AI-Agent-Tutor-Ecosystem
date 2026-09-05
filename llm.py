"""
The one place models are built, and the seam the tests use.

``llm_config.py`` built three near-identical LangChain clients, each hardcoding
``claude-3-5-sonnet-20240620`` (retired) and ``gpt-4o``, and returned
``ChatOpenAI(openai_api_key="mock_key")`` when no key was configured -- so a
run with no credentials failed deep inside crewai instead of at the edge with
a clear message.

Two kinds of client are needed. The graph's own nodes call ``model.invoke()``
directly, so they need a LangChain chat model. The crewai agents need crewai's
own ``LLM`` with the key passed explicitly -- crewai unwraps a LangChain object
and rebuilds its client from ``os.environ``, which a key that lives only in the
process settings never reaches.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from config import settings

# role -> temperature
TEMPERATURE = {"orchestrator": 0.2, "reasoning": 0.4, "creative": 0.7}

_langchain_factory: Callable[[str], Any] | None = None
_crew_factory: Callable[[str], Any] | None = None


class LLMNotConfigured(RuntimeError):
    pass


def set_langchain_factory(factory: Callable[[str], Any] | None) -> None:
    global _langchain_factory
    _langchain_factory = factory


def set_crew_factory(factory: Callable[[str], Any] | None) -> None:
    global _crew_factory
    _crew_factory = factory


def _provider_and_key() -> tuple[str, str, str]:
    """(provider, model, key), preferring OpenAI, then Anthropic."""
    if settings.OPENAI_API_KEY.strip():
        return "openai", settings.OPENAI_MODEL, settings.OPENAI_API_KEY.strip()
    if settings.ANTHROPIC_API_KEY.strip():
        return "anthropic", settings.ANTHROPIC_MODEL, settings.ANTHROPIC_API_KEY.strip()
    raise LLMNotConfigured(
        "No model provider key is set. Add OPENAI_API_KEY or ANTHROPIC_API_KEY to .env."
    )


def get_langchain_model(role: str = "orchestrator") -> Any:
    """A LangChain chat model for a graph node that calls ``.invoke()``."""
    if _langchain_factory is not None:
        return _langchain_factory(role)
    provider, model, key = _provider_and_key()
    temperature = TEMPERATURE.get(role, 0.2)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=key,
            temperature=temperature,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model_name=model,
        api_key=key,
        temperature=temperature,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def get_crew_llm(role: str = "creative") -> Any:
    """A crewai ``LLM`` for a crewai Agent, with the key passed explicitly."""
    if _crew_factory is not None:
        return _crew_factory(role)
    provider, model, key = _provider_and_key()
    temperature = TEMPERATURE.get(role, 0.7)
    from crewai import LLM

    crew_model = model if provider == "openai" else f"anthropic/{model}"
    return LLM(model=crew_model, api_key=key, temperature=temperature)
