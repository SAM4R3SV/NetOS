from datetime import datetime, timezone

from fastapi.testclient import TestClient

from netos.api.app import create_app
from netos.config import Settings
from netos.inventory.service import InventoryService
from netos.network.models import DeviceObservation
from netos.persistence.database import Database


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


def test_network_read_only_endpoints(tmp_path):
    settings = Settings(
        database_path=tmp_path / "netos.sqlite3",
        log_directory=tmp_path / "logs",
        monitoring_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/network/interfaces").status_code == 200
        assert client.get("/api/v1/network/summary").json()["interface_count"] == 0
        assert client.get("/api/v1/network/devices").json() == []
        assert client.get("/api/v1/network/events").json() == []
        assert client.get("/api/v1/network/interfaces/missing").status_code == 404
        assert client.get(
            "/api/v1/network/interfaces/missing/statistics"
        ).status_code == 404
        assert client.get("/api/v1/network/events?limit=501").status_code == 422


def test_policy_endpoints_crud_and_validation(tmp_path):
    settings = Settings(
        database_path=tmp_path / "netos.sqlite3",
        log_directory=tmp_path / "logs",
        monitoring_enabled=False,
    )
    payload = {
        "name": "allow-https",
        "description": "HTTPS access",
        "enabled": True,
        "priority": 10,
        "direction": "inbound",
        "action": "allow",
        "protocol": "tcp",
        "source_cidr": "192.168.1.10",
        "destination_port": 443,
    }
    with TestClient(create_app(settings)) as client:
        created = client.post("/api/v1/policies", json=payload)
        assert created.status_code == 201
        policy = created.json()
        assert policy["source_cidr"] == "192.168.1.10/32"
        policy_id = policy["id"]
        assert client.get("/api/v1/policies").json()[0]["id"] == policy_id
        assert client.get(f"/api/v1/policies/{policy_id}").status_code == 200
        replacement = {**payload, "enabled": False}
        updated = client.put(
            f"/api/v1/policies/{policy_id}", json=replacement
        )
        assert updated.status_code == 200
        assert updated.json()["enabled"] is False
        assert client.post("/api/v1/policies", json=payload).status_code == 409
        invalid = {**payload, "protocol": "any", "destination_port": 53}
        assert client.post("/api/v1/policies", json=invalid).status_code == 422
        assert client.delete(f"/api/v1/policies/{policy_id}").status_code == 204
        assert client.get(f"/api/v1/policies/{policy_id}").status_code == 404
        assert client.delete(f"/api/v1/policies/{policy_id}").status_code == 404


def test_inventory_endpoints_and_protected_fields(tmp_path):
    database_path = tmp_path / "netos.sqlite3"
    database = Database(database_path)
    database.initialize()
    InventoryService(database).ingest(
        (
            DeviceObservation(
                ip_address="192.168.1.40",
                mac_address="aa:bb:cc:dd:ee:40",
                interface_name="eth0",
                source="arp",
                observed_at=datetime.now(timezone.utc),
                identification="mac",
            ),
        )
    )
    settings = Settings(
        database_path=database_path,
        log_directory=tmp_path / "logs",
        monitoring_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        listed = client.get("/api/v1/inventory")
        assert listed.status_code == 200
        device_id = listed.json()[0]["id"]
        assert client.get(f"/api/v1/inventory/{device_id}").status_code == 200
        updated = client.patch(
            f"/api/v1/inventory/{device_id}",
            json={"display_name": "Office device"},
        )
        assert updated.status_code == 200
        assert updated.json()["display_name"] == "Office device"
        assert client.patch(
            f"/api/v1/inventory/{device_id}",
            json={"last_ip": "10.0.0.1"},
        ).status_code == 422
        assert client.get("/api/v1/inventory/missing").status_code == 404


def test_identity_endpoints(tmp_path):
    database_path = tmp_path / "netos.sqlite3"
    database = Database(database_path)
    database.initialize()
    InventoryService(database).ingest(
        (
            DeviceObservation(
                ip_address="192.168.1.60",
                mac_address="aa:bb:cc:dd:ee:60",
                interface_name="eth0",
                source="arp",
                observed_at=datetime.now(timezone.utc),
                identification="mac",
            ),
        )
    )
    device_id = InventoryService(database).list()[0].id
    settings = Settings(
        database_path=database_path,
        log_directory=tmp_path / "logs",
        monitoring_enabled=False,
    )
    payload = {
        "category": "printer",
        "role": "office printer",
        "confidence": "trusted",
        "owner": "Operations",
        "notes": "Manually reviewed",
    }
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/identity").json() == []
        created = client.put(f"/api/v1/identity/{device_id}", json=payload)
        assert created.status_code == 200
        assert created.json()["category"] == "printer"
        assert client.get(f"/api/v1/identity/{device_id}").status_code == 200
        replacement = {**payload, "category": "iot"}
        assert client.put(
            f"/api/v1/identity/{device_id}", json=replacement
        ).json()["category"] == "iot"
        assert client.put(
            f"/api/v1/identity/{device_id}", json={"category": "invalid"}
        ).status_code == 422
        assert client.put(
            "/api/v1/identity/missing", json=payload
        ).status_code == 404
        assert client.delete(f"/api/v1/identity/{device_id}").status_code == 204
        assert client.get(f"/api/v1/identity/{device_id}").status_code == 404
        assert client.delete(f"/api/v1/identity/{device_id}").status_code == 404


def test_notification_endpoints_and_filters(tmp_path):
    settings = Settings(
        database_path=tmp_path / "netos.sqlite3",
        log_directory=tmp_path / "logs",
        monitoring_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        monitor = client.app.state.monitor
        monitor.events.add_error("network", "source unavailable", "system")
        created = client.get("/api/v1/notifications?is_read=false")
        assert created.status_code == 200
        assert len(created.json()) == 1
        notification_id = created.json()[0]["id"]
        assert client.get(
            f"/api/v1/notifications/{notification_id}"
        ).status_code == 200
        assert client.get(
            "/api/v1/notifications?severity=critical"
        ).json() == []
        marked = client.patch(
            f"/api/v1/notifications/{notification_id}/read"
        )
        assert marked.status_code == 200
        assert marked.json()["is_read"] is True
        assert client.patch(
            f"/api/v1/notifications/{notification_id}/read"
        ).status_code == 200
        assert client.get("/api/v1/notifications?is_read=false").json() == []
        assert client.get(
            "/api/v1/notifications/missing"
        ).status_code == 404
        assert client.patch(
            "/api/v1/notifications/missing/read"
        ).status_code == 404


def test_secret_manager_is_initialized_without_secret_api_exposure(tmp_path):
    settings = Settings(
        database_path=tmp_path / "netos.sqlite3",
        log_directory=tmp_path / "logs",
        secrets_directory=tmp_path / "secrets",
        monitoring_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        assert client.app.state.secret_manager is not None
        assert (tmp_path / "secrets").is_dir()
        assert "/api/v1/secrets" not in {
            route.path for route in client.app.routes
        }
