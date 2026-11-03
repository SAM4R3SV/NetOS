import pytest

from netos.config import Settings


def test_defaults_are_local_and_safe(monkeypatch):
    monkeypatch.delenv("NETOS_API_HOST", raising=False)
    monkeypatch.delenv("NETOS_DATABASE_PATH", raising=False)
    settings = Settings.from_env()
    assert settings.api_host == "127.0.0.1"
    assert settings.database_path.as_posix() == "data/netos.sqlite3"
    assert settings.log_retention_days == 30
    assert settings.audit_retention_days == 30


def test_invalid_boolean_is_rejected(monkeypatch):
    monkeypatch.setenv("NETOS_API_RELOAD", "maybe")
    with pytest.raises(ValueError, match="boolean"):
        Settings.from_env()
