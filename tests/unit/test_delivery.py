from datetime import datetime, timedelta, timezone

import pytest

from netos.delivery.engine import DeliveryEngine
from netos.delivery.model import DeliveryResult, DeliveryStatus
from netos.delivery.repository import DeliveryRepository
from netos.persistence.database import Database


class FakeProvider:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def send(self, job):
        self.calls += 1
        return self.results.pop(0)


def setup(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    return database, DeliveryRepository(database)


def test_job_persists_and_payload_rejects_secret_fields(tmp_path):
    database, repository = setup(tmp_path)
    engine = DeliveryEngine(database, repository)
    job = engine.enqueue("fake", "test-destination", {"message": "hello"})
    assert DeliveryRepository(database).get(job.id).status is DeliveryStatus.PENDING
    with pytest.raises(ValueError):
        engine.enqueue("fake", "destination", {"bot_token": "secret"})


def test_success_transitions_pending_sending_sent(tmp_path):
    database, repository = setup(tmp_path)
    engine = DeliveryEngine(database, repository)
    provider = FakeProvider([DeliveryResult(success=True, http_status=200)])
    engine.register_provider("fake", provider)
    job = engine.enqueue("fake", "destination", {"message": "hello"})

    processed = engine.process_once()

    assert processed is not None
    assert processed.status is DeliveryStatus.SENT
    assert processed.attempt_count == 1
    assert provider.calls == 1


def test_retry_backoff_then_success(tmp_path):
    database, repository = setup(tmp_path)
    engine = DeliveryEngine(
        database, repository, base_backoff_seconds=10, max_backoff_seconds=20
    )
    engine.register_provider(
        "fake",
        FakeProvider(
            [
                DeliveryResult(success=False, retryable=True, error_code="busy"),
                DeliveryResult(success=True),
            ]
        ),
    )
    job = engine.enqueue("fake", "destination", {"message": "hello"})
    first = engine.process_once()
    assert first.status is DeliveryStatus.RETRY
    assert first.next_attempt_at >= datetime.now(timezone.utc) + timedelta(seconds=9)

    with repository.database.transaction() as connection:
        connection.execute(
            "UPDATE delivery_jobs SET next_attempt_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), job.id),
        )
    second = engine.process_once()
    assert second.status is DeliveryStatus.SENT


def test_retry_after_and_attempt_limit(tmp_path):
    database, repository = setup(tmp_path)
    engine = DeliveryEngine(database, repository, max_attempts=2)
    engine.register_provider(
        "fake",
        FakeProvider(
            [
                DeliveryResult(
                    success=False, retryable=True, retry_after_seconds=30
                ),
                DeliveryResult(success=False, retryable=True),
            ]
        ),
    )
    job = engine.enqueue("fake", "destination", {"message": "hello"})
    first = engine.process_once()
    assert first.status is DeliveryStatus.RETRY
    assert first.http_status is None
    with repository.database.transaction() as connection:
        connection.execute(
            "UPDATE delivery_jobs SET next_attempt_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), job.id),
        )
    assert engine.process_once().status is DeliveryStatus.FAILED


def test_missing_provider_is_per_job_failure_and_other_provider_continues(tmp_path):
    database, repository = setup(tmp_path)
    engine = DeliveryEngine(database, repository)
    provider = FakeProvider([DeliveryResult(success=True)])
    engine.register_provider("working", provider)
    missing = engine.enqueue("missing", "destination", {"message": "one"})
    working = engine.enqueue("working", "destination", {"message": "two"})

    assert engine.process_once().status is DeliveryStatus.FAILED
    assert engine.process_once().status is DeliveryStatus.SENT
    assert repository.get(missing.id).status is DeliveryStatus.FAILED
    assert repository.get(working.id).status is DeliveryStatus.SENT


def test_stale_sending_job_is_recovered_after_restart(tmp_path):
    database, repository = setup(tmp_path)
    engine = DeliveryEngine(database, repository, sending_timeout_seconds=1)
    job = engine.enqueue("fake", "destination", {"message": "hello"})
    claimed = repository.claim_due(
        datetime.now(timezone.utc),
        datetime.now(timezone.utc) - timedelta(seconds=10),
    )
    assert claimed.status is DeliveryStatus.SENDING
    with repository.database.transaction() as connection:
        connection.execute(
            "UPDATE delivery_jobs SET updated_at = ? WHERE id = ?",
            (
                (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(),
                job.id,
            ),
        )
    restarted = DeliveryEngine(database, repository)
    restarted.repository.recover_sending(
        datetime.now(timezone.utc), datetime.now(timezone.utc)
    )
    assert repository.get(job.id).status is DeliveryStatus.RETRY


def test_timeout_is_retryable_and_does_not_escape_engine(tmp_path):
    database, repository = setup(tmp_path)
    engine = DeliveryEngine(database, repository)

    class TimeoutProvider:
        def send(self, job):
            raise TimeoutError

    engine.register_provider("timeout", TimeoutProvider())
    job = engine.enqueue("timeout", "destination", {"message": "hello"})

    processed = engine.process_once()

    assert processed.status is DeliveryStatus.RETRY
    assert processed.error == "provider_timeout"


def test_eventual_provider_error_does_not_log_secret(caplog, tmp_path):
    database, repository = setup(tmp_path)
    engine = DeliveryEngine(database, repository, max_attempts=1)

    class BrokenProvider:
        def send(self, job):
            raise RuntimeError("secret-token-value")

    engine.register_provider("broken", BrokenProvider())
    engine.enqueue("broken", "destination", {"message": "hello"})
    engine.process_once()

    assert "secret-token-value" not in caplog.text


def test_migration_reaches_version_six_from_previous_schema(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    with database.connection() as connection:
        connection.execute("DELETE FROM schema_version WHERE version = 6")
        connection.execute(
            "INSERT OR IGNORE INTO notifications("
            "id, event_type, title, message, severity, created_at, "
            "is_read, deduplication_key"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "notification-1",
                "source_error",
                "Source error",
                "old error",
                "warning",
                datetime.now(timezone.utc).isoformat(),
                0,
                "source_error:network:old error",
            ),
        )
    database.initialize()
    with database.connection() as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0] == 6
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'delivery_jobs'"
        ).fetchone()[0] == "delivery_jobs"
