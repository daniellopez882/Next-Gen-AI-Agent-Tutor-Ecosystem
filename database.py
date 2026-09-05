"""
SQLite persistence for students, mastery and session logs.

``init_db()`` ran at import, so importing this module -- for a test, a linter,
an IDE -- created ``tutor.db`` in the working directory. The path was hardcoded
and every function opened its own connection to that literal. The path is
configuration now, connections come from one helper, and nothing runs at
import; ``init_db()`` is called from the application's startup.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from typing import Any

from config import settings

logger = logging.getLogger("lumina.db")


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY, name TEXT, grade_level TEXT,
                age INTEGER, learning_style TEXT, language TEXT
            );
            CREATE TABLE IF NOT EXISTS mastery (
                student_id TEXT, topic TEXT, score INTEGER, last_reviewed TEXT,
                PRIMARY KEY (student_id, topic)
            );
            CREATE TABLE IF NOT EXISTS session_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT,
                session_date TEXT DEFAULT CURRENT_TIMESTAMP,
                agent_invoked TEXT, task TEXT, response_json TEXT
            );
            """
        )


def upsert_student(profile: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            "REPLACE INTO students (student_id, name, grade_level, age, learning_style, language) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                profile.get("student_id"),
                profile.get("name"),
                profile.get("grade_level"),
                profile.get("age"),
                profile.get("learning_style"),
                profile.get("language"),
            ),
        )


def update_topic_mastery(student_id: str, topic: str, score: int) -> None:
    with _connect() as conn:
        conn.execute(
            "REPLACE INTO mastery (student_id, topic, score, last_reviewed) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (student_id, topic, score),
        )


def get_student_mastery(student_id: str) -> dict[str, int]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT topic, score FROM mastery WHERE student_id = ?", (student_id,)
        ).fetchall()
    return {topic: score for topic, score in rows}


def log_session(student_id: str, agent_invoked: str, task: str, response: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO session_logs (student_id, agent_invoked, task, response_json) VALUES (?, ?, ?, ?)",
            (student_id, agent_invoked, task, json.dumps(response, default=str)),
        )
