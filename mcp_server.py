"""
The Model Context Protocol server.

This is the genuine article: ``FastMCP`` exposes ``invoke_tutor`` as an MCP
tool a client such as Claude Desktop can call. It shares the LangGraph and the
database with the HTTP app.

The only change is startup order: the graph and the database used to be
initialised as import side effects of the modules this imports. ``init_db()``
now runs when the server starts, and the graph is built on first use.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

import database

mcp = FastMCP("Education_Tutor_MCP")


@mcp.tool()
async def invoke_tutor(
    task: str,
    student_id: str,
    student_name: str,
    grade_level: str,
    age: int,
    learning_style: str = "reading",
    language: str = "English",
) -> str:
    """
    Submit an educational task to the tutor orchestrator, which routes it to a
    specialist agent (lesson personalizer, quiz generator, progress tracker,
    doubt resolver or parent reporter).

    Args:
        task: The educational request, e.g. "teach me fractions".
        student_id: Unique identifier for the student.
        student_name: The student's first name.
        grade_level: e.g. "Grade 7".
        age: The student's age.
        learning_style: "visual", "auditory", "reading" or "kinesthetic".
        language: Language of instruction.
    """
    from agent_graph import get_graph

    profile = {
        "student_id": student_id,
        "name": student_name,
        "grade_level": grade_level,
        "age": age,
        "learning_style": learning_style,
        "language": language,
        "mastery_levels": database.get_student_mastery(student_id),
    }
    database.upsert_student(profile)

    state = {
        "task_input": task,
        "student_profile": profile,
        "classification": {},
        "final_response": None,
    }
    try:
        final_state = get_graph().invoke(state)
    except Exception as error:
        return json.dumps(
            {"status": "error", "message": type(error).__name__}, indent=2
        )

    agent_invoked = final_state.get("classification", {}).get("next_agent", "unknown")
    response = final_state.get("final_response") or {}
    database.log_session(student_id, agent_invoked, task, response)
    return json.dumps(
        {"status": "success", "agent_invoked": agent_invoked, "response": response},
        indent=2,
    )


def main() -> None:
    database.init_db()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
