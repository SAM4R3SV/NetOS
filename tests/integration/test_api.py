from fastapi.testclient import TestClient

from netos.api.app import create_app
from netos.config import Settings


def test_api_health_status_and_public_configuration(tmp_path):
    settings = Settings(
        database_path=tmp_path / "netos.sqlite3",
        log_directory=tmp_path / "logs",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["status"] == "ok"
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        assert status.json()["database"] == "ok"
        configuration = client.get("/api/v1/configuration").json()
        assert "database_path" not in configuration
        assert configuration["audit_retention_days"] == 30


def test_unknown_route_has_standard_error_shape(tmp_path):
    settings = Settings(
        database_path=tmp_path / "netos.sqlite3",
        log_directory=tmp_path / "logs",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/does-not-exist")
        assert response.status_code == 404
        assert "detail" in response.json()
