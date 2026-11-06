from datetime import datetime, timezone

import pytest

from netos.events.monitoring import EventStore
from netos.notifications.model import NotificationSeverity
from netos.notifications.service import (
    NotificationNotFoundError,
    NotificationService,
)
from netos.persistence.database import Database


def event(
    event_type: str = "interface_disappeared",
    resource: str = "eth0",
    description: str = "Interface eth0 disappeared",
):
    from netos.network.models import MonitorEvent

    return MonitorEvent(
        event_type=event_type,
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        resource=resource,
        description=description,
        source="pytest",
    )


def test_notification_persists_deduplicates_and_survives_reopen(tmp_path):
    path = tmp_path / "netos.sqlite3"
    database = Database(path)
    database.initialize()
    service = NotificationService(database)

    created = service.process_event(event())
    assert created is not None
    assert service.process_event(event()) is None
    assert len(service.list()) == 1

    reopened = NotificationService(Database(path))
    assert reopened.get(created.id).id == created.id


def test_irrelevant_events_do_not_create_notifications(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = NotificationService(database)

    assert service.process_event(event("interface_detected")) is None
    assert service.list() == []


def test_notification_filters_and_idempotent_read(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = NotificationService(database)
    created = service.process_event(event())
    assert created is not None

    assert service.list(is_read=False, severity=NotificationSeverity.WARNING)
    marked = service.mark_read(created.id)
    assert marked.is_read is True
    assert service.mark_read(created.id).is_read is True
    assert service.list(is_read=False) == []
    assert service.list(is_read=True)[0].id == created.id


def test_missing_notification_is_explicit(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = NotificationService(database)

    with pytest.raises(NotificationNotFoundError):
        service.get("missing")
    with pytest.raises(NotificationNotFoundError):
        service.mark_read("missing")


def test_event_store_sink_persists_only_supported_events(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = NotificationService(database)
    store = EventStore()
    store.set_event_sink(service.process_event)

    store.add_error("network", "source unavailable", "system")

    notifications = service.list()
    assert len(notifications) == 1
    assert notifications[0].event_type == "source_error"


def test_persistence_error_is_isolated_from_event_processing(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = NotificationService(database)

    class BrokenRepository:
        def create_from_event(self, *args, **kwargs):
            import sqlite3

            raise sqlite3.OperationalError("database unavailable")

    service.repository = BrokenRepository()
    store = EventStore()
    store.set_event_sink(service.process_event)

    store.add_error("network", "source unavailable", "system")

    assert len(store.list()) == 1


def test_migration_from_schema_four_and_new_database(tmp_path):
    fresh = Database(tmp_path / "fresh.sqlite3")
    fresh.initialize()
    fresh.initialize()
    with fresh.connection() as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0] == 6

    previous_path = tmp_path / "previous.sqlite3"
    previous = Database(previous_path)
    previous.initialize()
    service = NotificationService(previous)
    persisted = service.process_event(event("source_error", "network", "old error"))
    assert persisted is not None
    with previous.connection() as connection:
        connection.execute("DELETE FROM schema_version WHERE version = 5")
    previous.initialize()
    with previous.connection() as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0] == 6
    assert (
        NotificationService(Database(previous_path)).get(persisted.id).message
        == "old error"
    )
