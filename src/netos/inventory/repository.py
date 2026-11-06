"""SQLite repository for persistent observed devices."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from netos.inventory.model import DeviceMetadataPatch, DeviceRecord
from netos.persistence.database import Database


class InventoryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, device: DeviceRecord) -> DeviceRecord:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO devices(
                    id, mac_address, hostname, display_name, vendor,
                    first_seen, last_seen, last_ip, last_interface, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._parameters(device),
            )
        return device

    def get_by_mac(self, mac_address: str) -> DeviceRecord | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM devices WHERE mac_address = ?",
                (mac_address,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    def get(self, device_id: str) -> DeviceRecord | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM devices WHERE id = ?", (device_id,)
            ).fetchone()
        return None if row is None else self._from_row(row)

    def list(self) -> list[DeviceRecord]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM devices ORDER BY last_seen DESC, id ASC"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update_observation(
        self,
        device_id: str,
        observed_at: datetime,
        ip_address: str | None,
        interface_name: str | None,
    ) -> DeviceRecord | None:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE devices SET
                    last_seen = ?, last_ip = ?, last_interface = ?, status = 'observed'
                WHERE id = ?
                """,
                (
                    observed_at.isoformat(),
                    ip_address,
                    interface_name,
                    device_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
        return self.get(device_id)

    def update_metadata(
        self, device_id: str, patch: DeviceMetadataPatch
    ) -> DeviceRecord | None:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE devices SET display_name = ? WHERE id = ?",
                (patch.display_name, device_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get(device_id)

    @staticmethod
    def _parameters(device: DeviceRecord) -> tuple[object, ...]:
        return (
            device.id,
            device.mac_address,
            device.hostname,
            device.display_name,
            device.vendor,
            device.first_seen.isoformat(),
            device.last_seen.isoformat(),
            device.last_ip,
            device.last_interface,
            device.status,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> DeviceRecord:
        return DeviceRecord(
            id=row["id"],
            mac_address=row["mac_address"],
            hostname=row["hostname"],
            display_name=row["display_name"],
            vendor=row["vendor"],
            first_seen=datetime.fromisoformat(row["first_seen"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
            last_ip=row["last_ip"],
            last_interface=row["last_interface"],
            status=row["status"],
        )
