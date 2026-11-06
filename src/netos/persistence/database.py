"""SQLite connection management and versioned migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL,
            is_sensitive INTEGER NOT NULL DEFAULT 0 CHECK (is_sensitive IN (0, 1)),
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK (outcome IN ('success', 'failure')),
            correlation_id TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_audit_events_created_at
            ON audit_events (created_at);
        """,
    ),
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY NOT NULL,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            description TEXT,
            enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
            priority INTEGER NOT NULL CHECK (priority >= 0),
            direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
            action TEXT NOT NULL CHECK (action IN ('allow', 'deny')),
            protocol TEXT NOT NULL CHECK (
                protocol IN ('any', 'tcp', 'udp', 'icmp')
            ),
            source_cidr TEXT,
            destination_cidr TEXT,
            source_port INTEGER CHECK (source_port BETWEEN 1 AND 65535),
            destination_port INTEGER CHECK (
                destination_port BETWEEN 1 AND 65535
            ),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_policies_priority
            ON policies (priority, id);
        CREATE INDEX IF NOT EXISTS idx_policies_enabled
            ON policies (enabled);
        """,
    ),
    (
        3,
        """
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY NOT NULL,
            mac_address TEXT NOT NULL COLLATE NOCASE UNIQUE,
            hostname TEXT,
            display_name TEXT,
            vendor TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            last_ip TEXT,
            last_interface TEXT,
            status TEXT NOT NULL CHECK (status IN ('observed'))
        );
        CREATE INDEX IF NOT EXISTS idx_devices_last_seen
            ON devices (last_seen);
        CREATE INDEX IF NOT EXISTS idx_devices_last_ip
            ON devices (last_ip);
        """,
    ),
    (
        4,
        """
        CREATE TABLE IF NOT EXISTS device_identities (
            device_id TEXT PRIMARY KEY NOT NULL,
            category TEXT NOT NULL CHECK (
                category IN (
                    'computer', 'server', 'router', 'switch', 'camera',
                    'iot', 'mobile', 'printer', 'unknown'
                )
            ),
            role TEXT,
            confidence TEXT NOT NULL CHECK (
                confidence IN ('trusted', 'unknown', 'restricted')
            ),
            owner TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_device_identities_category
            ON device_identities (category);
        CREATE INDEX IF NOT EXISTS idx_device_identities_confidence
            ON device_identities (confidence);
        """,
    ),
    (
        5,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT NOT NULL CHECK (
                severity IN ('info', 'warning', 'critical')
            ),
            created_at TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
            device_id TEXT,
            deduplication_key TEXT NOT NULL UNIQUE,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_notifications_created_at
            ON notifications (created_at);
        CREATE INDEX IF NOT EXISTS idx_notifications_read
            ON notifications (is_read);
        CREATE INDEX IF NOT EXISTS idx_notifications_severity
            ON notifications (severity);
        """,
    ),
    (
        6,
        """
        CREATE TABLE IF NOT EXISTS delivery_jobs (
            id TEXT PRIMARY KEY NOT NULL,
            notification_id TEXT,
            provider TEXT NOT NULL,
            destination TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'sending', 'sent', 'retry', 'failed')
            ),
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            next_attempt_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            sent_at TEXT,
            last_attempt_at TEXT,
            http_status INTEGER,
            error TEXT,
            FOREIGN KEY (notification_id) REFERENCES notifications(id)
                ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_delivery_jobs_due
            ON delivery_jobs (status, next_attempt_at);
        CREATE INDEX IF NOT EXISTS idx_delivery_jobs_provider
            ON delivery_jobs (provider, status);
        """,
    ),
)


class Database:
    """Owns short-lived SQLite connections and migration state."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(version INTEGER PRIMARY KEY NOT NULL)"
            )
            current = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_version"
            ).fetchone()[0]
            versions = [version for version, _ in MIGRATIONS]
            if versions != sorted(set(versions)):
                raise ValueError("MIGRATIONS must contain unique sorted versions")
            for version, script in MIGRATIONS:
                if version > current:
                    migration = (
                        "BEGIN IMMEDIATE;\n"
                        f"{script}\n"
                        "INSERT INTO schema_version(version) VALUES "
                        f"({version});\n"
                        "COMMIT;"
                    )
                    try:
                        connection.executescript(migration)
                    except Exception:
                        connection.rollback()
                        raise

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(
            self.path,
            timeout=5,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        with self.connection() as connection:
            connection.execute("BEGIN")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()
