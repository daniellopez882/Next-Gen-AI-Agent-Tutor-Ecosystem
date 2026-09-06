"""
The three crewai specialist agents.

Each built a crewai ``Agent`` with a LangChain model and did its own
``.replace('```json', '')`` + ``json.loads`` on the result. The model comes
from ``llm.get_crew_llm`` now (crewai's own LLM with an explicit key), and the
parsing goes through the one extractor in ``json_extraction``.
"""

from __future__ import annotations

from typing import Any

from education_tutor_prompts import (
    DOUBT_RESOLVER_PROMPT,
    LESSON_PERSONALIZER_PROMPT,
    QUIZ_GENERATOR_PROMPT,
    build_agent_prompt_with_student,
)
from json_extraction import extract_json
from llm import get_crew_llm


def _run_agent(
    role: str, goal: str, prompt: str, description: str, llm_role: str
) -> dict:
    from crewai import Agent, Crew, Process, Task

    agent = Agent(
        role=role,
        goal=goal,
        backstory=prompt,
        verbose=False,
        allow_delegation=False,
        llm=get_crew_llm(llm_role),
    )
    task = Task(
        description=description,
        expected_output="A single JSON object matching the OUTPUT FORMAT in the instructions, no markdown fences.",
        agent=agent,
    )
    result = Crew(
        agents=[agent], tasks=[task], process=Process.sequential, verbose=False
    ).kickoff()
    return extract_json(str(getattr(result, "raw", result)))


def run_lesson_personalizer(student_profile: dict, task_input: str) -> dict[str, Any]:
    return _run_agent(
        "Lesson Personalizer",
        "Design a personalized lesson for the student's profile.",
        build_agent_prompt_with_student(LESSON_PERSONALIZER_PROMPT, student_profile),
        f"Create a personalized lesson for this request: '{task_input}'. Follow the adaptive lesson protocol.",
        "creative",
    )


def run_quiz_generator(student_profile: dict, task_input: str) -> dict[str, Any]:
    return _run_agent(
        "Quiz Generator",
        "Create a quiz that measures mastery and surfaces misconceptions.",
        build_agent_prompt_with_student(QUIZ_GENERATOR_PROMPT, student_profile),
        f"Generate a quiz for this request: '{task_input}', following Bloom's Taxonomy.",
        "reasoning",
    )


def run_doubt_resolver(
    student_profile: dict, task_input: str, retrieved_context: list | None = None
) -> dict[str, Any]:
    context = (
        "\n".join(str(c) for c in retrieved_context)
        if retrieved_context
        else "No curriculum context provided."
    )
    return _run_agent(
        "Doubt Resolver",
        "Resolve the student's question using the provided curriculum context.",
        build_agent_prompt_with_student(DOUBT_RESOLVER_PROMPT, student_profile),
        f"Resolve this doubt: '{task_input}'.\n\nCurriculum context:\n{context}",
        "creative",
    )
