"""SQLite repository for durable delivery jobs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping

from netos.delivery.model import DeliveryJob, DeliveryResult, DeliveryStatus
from netos.persistence.database import Database


class DeliveryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        job_id: str,
        notification_id: str | None,
        provider: str,
        destination: str,
        payload: Mapping[str, Any],
        now: datetime,
    ) -> DeliveryJob:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO delivery_jobs(
                    id, notification_id, provider, destination, payload, status,
                    attempt_count, next_attempt_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)
                """,
                (
                    job_id,
                    notification_id,
                    provider,
                    destination,
                    encoded,
                    now.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> DeliveryJob:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM delivery_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError("delivery job not found")
        return self._from_row(row)

    def list(self, status: DeliveryStatus | None = None) -> list[DeliveryJob]:
        clause = "WHERE status = ?" if status else ""
        parameters = (status.value,) if status else ()
        with self.database.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM delivery_jobs {clause} ORDER BY created_at ASC",
                parameters,
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def recover_sending(self, now: datetime, stale_before: datetime) -> int:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE delivery_jobs
                SET status = 'retry', next_attempt_at = ?, updated_at = ?,
                    error = 'recovered_after_restart'
                WHERE status = 'sending' AND updated_at <= ?
                """,
                (now.isoformat(), now.isoformat(), stale_before.isoformat()),
            )
        return cursor.rowcount

    def claim_due(
        self, now: datetime, stale_before: datetime
    ) -> DeliveryJob | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM delivery_jobs
                WHERE (
                    status IN ('pending', 'retry') AND next_attempt_at <= ?
                ) OR (
                    status = 'sending' AND updated_at <= ?
                )
                ORDER BY next_attempt_at ASC, created_at ASC
                LIMIT 1
                """,
                (now.isoformat(), stale_before.isoformat()),
            ).fetchone()
            if row is None:
                return None
            cursor = connection.execute(
                """
                UPDATE delivery_jobs
                SET status = 'sending', attempt_count = attempt_count + 1,
                    last_attempt_at = ?, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'retry', 'sending')
                """,
                (now.isoformat(), now.isoformat(), row["id"]),
            )
            if cursor.rowcount != 1:
                return None
            updated = connection.execute(
                "SELECT * FROM delivery_jobs WHERE id = ?", (row["id"],)
            ).fetchone()
        return self._from_row(updated)

    def complete(
        self,
        job_id: str,
        result: DeliveryResult,
        status: DeliveryStatus,
        next_attempt_at: datetime | None,
        now: datetime,
    ) -> None:
        sent_at = now.isoformat() if status is DeliveryStatus.SENT else None
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE delivery_jobs
                SET status = ?, next_attempt_at = ?, updated_at = ?,
                    sent_at = ?, http_status = ?, error = ?
                WHERE id = ? AND status = 'sending'
                """,
                (
                    status.value,
                    (next_attempt_at or now).isoformat(),
                    now.isoformat(),
                    sent_at,
                    result.http_status,
                    result.error_code,
                    job_id,
                ),
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> DeliveryJob:
        payload = json.loads(row["payload"])
        if not isinstance(payload, dict):
            raise ValueError("delivery payload is not an object")
        return DeliveryJob(
            id=row["id"],
            notification_id=row["notification_id"],
            provider=row["provider"],
            destination=row["destination"],
            payload=payload,
            status=DeliveryStatus(row["status"]),
            attempt_count=row["attempt_count"],
            next_attempt_at=datetime.fromisoformat(row["next_attempt_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            sent_at=(
                datetime.fromisoformat(row["sent_at"])
                if row["sent_at"]
                else None
            ),
            last_attempt_at=(
                datetime.fromisoformat(row["last_attempt_at"])
                if row["last_attempt_at"]
                else None
            ),
            http_status=row["http_status"],
            error=row["error"],
        )
