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
