"""SQLite repository for persisted administrative policies."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from netos.persistence.database import Database
from netos.policies.model import Policy


class PolicyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, policy: Policy) -> Policy:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO policies(
                    id, name, description, enabled, priority, direction, action,
                    protocol, source_cidr, destination_cidr, source_port,
                    destination_port, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._parameters(policy),
            )
        return policy

    def get(self, policy_id: str) -> Policy | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM policies WHERE id = ?", (policy_id,)
            ).fetchone()
        return None if row is None else self._from_row(row)

    def list(self) -> list[Policy]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM policies ORDER BY priority ASC, created_at ASC, id ASC"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update(self, policy: Policy) -> Policy | None:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE policies SET
                    name = ?, description = ?, enabled = ?, priority = ?,
                    direction = ?, action = ?, protocol = ?, source_cidr = ?,
                    destination_cidr = ?, source_port = ?, destination_port = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    policy.name,
                    policy.description,
                    int(policy.enabled),
                    policy.priority,
                    policy.direction.value,
                    policy.action.value,
                    policy.protocol.value,
                    policy.source_cidr,
                    policy.destination_cidr,
                    policy.source_port,
                    policy.destination_port,
                    policy.updated_at.isoformat(),
                    policy.id,
                ),
            )
            if cursor.rowcount == 0:
                return None
        return policy

    def delete(self, policy_id: str) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM policies WHERE id = ?", (policy_id,)
            )
        return cursor.rowcount == 1

    @staticmethod
    def _parameters(policy: Policy) -> tuple[Any, ...]:
        return (
            policy.id,
            policy.name,
            policy.description,
            int(policy.enabled),
            policy.priority,
            policy.direction.value,
            policy.action.value,
            policy.protocol.value,
            policy.source_cidr,
            policy.destination_cidr,
            policy.source_port,
            policy.destination_port,
            policy.created_at.isoformat(),
            policy.updated_at.isoformat(),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Policy:
        return Policy(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            priority=row["priority"],
            direction=row["direction"],
            action=row["action"],
            protocol=row["protocol"],
            source_cidr=row["source_cidr"],
            destination_cidr=row["destination_cidr"],
            source_port=row["source_port"],
            destination_port=row["destination_port"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
