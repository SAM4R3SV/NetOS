"""SQLite repository for administrative device identities."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from netos.identity.model import DeviceIdentity, DeviceIdentityData
from netos.persistence.database import Database


class IdentityRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def device_exists(self, device_id: str) -> bool:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM devices WHERE id = ?", (device_id,)
            ).fetchone()
        return row is not None

    def get(self, device_id: str) -> DeviceIdentity | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM device_identities WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    def list(self) -> list[DeviceIdentity]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM device_identities ORDER BY updated_at DESC, device_id ASC"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def replace(
        self,
        device_id: str,
        data: DeviceIdentityData,
        now: datetime,
    ) -> DeviceIdentity:
        with self.database.transaction() as connection:
            existing = connection.execute(
                "SELECT created_at FROM device_identities WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            created_at = (
                existing["created_at"] if existing is not None else now.isoformat()
            )
            connection.execute(
                """
                INSERT INTO device_identities(
                    device_id, category, role, confidence, owner, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    category = excluded.category,
                    role = excluded.role,
                    confidence = excluded.confidence,
                    owner = excluded.owner,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    device_id,
                    data.category.value,
                    data.role,
                    data.confidence.value,
                    data.owner,
                    data.notes,
                    created_at,
                    now.isoformat(),
                ),
            )
        identity = self.get(device_id)
        if identity is None:
            raise RuntimeError("identity was not persisted")
        return identity

    def delete(self, device_id: str) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM device_identities WHERE device_id = ?",
                (device_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _from_row(row: sqlite3.Row) -> DeviceIdentity:
        return DeviceIdentity(
            device_id=row["device_id"],
            category=row["category"],
            role=row["role"],
            confidence=row["confidence"],
            owner=row["owner"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
