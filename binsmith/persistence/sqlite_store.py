from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Sequence

from pydantic_ai.messages import ModelMessage

from binsmith.core.messages import dump_messages, load_messages
from binsmith.core.session import SessionStore, ThreadState


class SQLiteSessionStore(SessionStore):
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def load_thread(
        self,
        session_id: str,
        thread_id: str,
        *,
        workspace: Path,
    ) -> ThreadState:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT messages FROM threads WHERE session_id = ? AND thread_id = ?",
                (session_id, thread_id),
            ).fetchone()
            if row:
                messages_blob = row[0]
                messages = load_messages(messages_blob)
                return ThreadState(
                    session_id=session_id,
                    thread_id=thread_id,
                    workspace=workspace,
                    messages=messages,
                )

            messages: list[ModelMessage] = []
            self._upsert_thread(conn, session_id, thread_id, messages)
            return ThreadState(
                session_id=session_id,
                thread_id=thread_id,
                workspace=workspace,
                messages=messages,
            )

    def save_thread(
        self,
        session_id: str,
        thread_id: str,
        *,
        workspace: Path,
        messages: Sequence[ModelMessage],
    ) -> None:
        with self._connect() as conn:
            self._upsert_thread(conn, session_id, thread_id, list(messages))

    def list_threads(self, session_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT thread_id FROM threads WHERE session_id = ? ORDER BY updated_at DESC",
                (session_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def list_sessions(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT session_id FROM sessions ORDER BY updated_at DESC").fetchall()
        return [row[0] for row in rows]

    def delete_thread(self, session_id: str, thread_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM threads WHERE session_id = ? AND thread_id = ?",
                (session_id, thread_id),
            )
            remaining = conn.execute(
                "SELECT 1 FROM threads WHERE session_id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
            if remaining is None:
                conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,),
                )

    def get_session_model(self, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT model FROM session_settings WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return row[0]

    def set_session_model(self, session_id: str, model: str | None) -> None:
        with self._connect() as conn:
            if model is None:
                conn.execute(
                    "DELETE FROM session_settings WHERE session_id = ?",
                    (session_id,),
                )
                return
            now = time.time()
            conn.execute(
                """
                INSERT INTO sessions (session_id, created_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (session_id, now, now),
            )
            conn.execute(
                """
                INSERT INTO session_settings (session_id, model, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    model = excluded.model,
                    updated_at = excluded.updated_at
                """,
                (session_id, model, now),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    session_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    messages BLOB,
                    PRIMARY KEY (session_id, thread_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_settings (
                    session_id TEXT PRIMARY KEY,
                    model TEXT,
                    updated_at REAL NOT NULL
                )
                """
            )

    def _upsert_thread(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        thread_id: str,
        messages: list[ModelMessage],
    ) -> None:
        now = time.time()
        conn.execute(
            """
            INSERT INTO sessions (session_id, created_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (session_id, now, now),
        )
        messages_blob = dump_messages(messages)
        conn.execute(
            """
            INSERT INTO threads (session_id, thread_id, created_at, updated_at, messages)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id, thread_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                messages = excluded.messages
            """,
            (session_id, thread_id, now, now, messages_blob),
        )
