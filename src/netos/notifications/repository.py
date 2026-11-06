"""SQLite repository for internal notifications."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from uuid import uuid4

from netos.events.monitoring import MonitorEvent
from netos.notifications.model import Notification, NotificationSeverity
from netos.persistence.database import Database


class NotificationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_from_event(
        self,
        event: MonitorEvent,
        title: str,
        severity: NotificationSeverity,
        deduplication_key: str,
        device_id: str | None = None,
    ) -> Notification | None:
        notification_id = str(uuid4())
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO notifications(
                    id, event_type, title, message, severity, created_at,
                    is_read, device_id, deduplication_key
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    notification_id,
                    event.event_type,
                    title,
                    event.description,
                    severity.value,
                    event.occurred_at.isoformat(),
                    device_id,
                    deduplication_key,
                ),
            )
            if cursor.rowcount == 0:
                return None
        return self.get(notification_id)

    def get(self, notification_id: str) -> Notification | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM notifications WHERE id = ?",
                (notification_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    def list(
        self,
        limit: int,
        is_read: bool | None = None,
        severity: NotificationSeverity | None = None,
    ) -> list[Notification]:
        clauses: list[str] = []
        parameters: list[object] = []
        if is_read is not None:
            clauses.append("is_read = ?")
            parameters.append(int(is_read))
        if severity is not None:
            clauses.append("severity = ?")
            parameters.append(severity.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        with self.database.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM notifications
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def mark_read(self, notification_id: str) -> Notification | None:
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )
        return self.get(notification_id)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Notification:
        return Notification(
            id=row["id"],
            event_type=row["event_type"],
            title=row["title"],
            message=row["message"],
            severity=row["severity"],
            created_at=datetime.fromisoformat(row["created_at"]),
            is_read=bool(row["is_read"]),
            device_id=row["device_id"],
            deduplication_key=row["deduplication_key"],
        )
