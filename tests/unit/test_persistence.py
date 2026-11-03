from netos.persistence.database import Database
from netos.persistence.repositories import AuditRepository, StateRepository


def test_migrations_are_idempotent_and_repositories_persist(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    database.initialize()
    state = StateRepository(database)
    state.set("mode", "monitor")
    assert state.get("mode") == "monitor"
    audit = AuditRepository(database)
    audit.record("test", "pytest", "success", "corr-1")
    assert audit.count() == 1
    assert audit.purge_older_than("9999-01-01T00:00:00+00:00") == 1
    assert audit.count() == 0
