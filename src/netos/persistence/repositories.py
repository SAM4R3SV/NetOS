"""Repositories for bounded control-plane data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from netos.persistence.database import Database


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def set(self, key: str, value: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO app_state(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                updated_at=excluded.updated_at
                """,
                (key, value, utc_now()),
            )

    def get(self, key: str) -> str | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT value FROM app_state WHERE key = ?", (key,)
            ).fetchone()
        return None if row is None else str(row["value"])


class AuditRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def record(
        self,
        action: str,
        actor: str,
        outcome: str,
        correlation_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if outcome not in {"success", "failure"}:
            raise ValueError("outcome must be success or failure")
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO audit_events(
                    action, actor, outcome, correlation_id, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    action,
                    actor,
                    outcome,
                    correlation_id,
                    json.dumps(details or {}, sort_keys=True),
                    utc_now(),
                ),
            )

    def count(self) -> int:
        with self.database.connection() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            )

    def purge_older_than(self, cutoff: str) -> int:
        """Delete only audit events older than the supplied UTC cutoff."""
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM audit_events WHERE created_at < ?", (cutoff,)
            )
            return cursor.rowcount
