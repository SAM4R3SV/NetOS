from datetime import datetime, timezone

import pytest

from netos.identity.model import DeviceIdentityData
from netos.identity.service import (
    DeviceNotFoundError,
    IdentityNotFoundError,
    IdentityService,
)
from netos.inventory.service import InventoryService
from netos.network.models import DeviceObservation
from netos.persistence.database import Database


def create_device(database: Database, mac: str = "aa:bb:cc:dd:ee:50") -> str:
    InventoryService(database).ingest(
        (
            DeviceObservation(
                ip_address="192.168.1.50",
                mac_address=mac,
                interface_name="eth0",
                source="arp",
                observed_at=datetime.now(timezone.utc),
                identification="mac",
            ),
        )
    )
    return InventoryService(database).list()[0].id


def test_identity_replace_update_persist_and_remove(tmp_path):
    path = tmp_path / "netos.sqlite3"
    database = Database(path)
    database.initialize()
    device_id = create_device(database)
    service = IdentityService(database)
    data = DeviceIdentityData(
        category="camera",
        role="front door",
        confidence="trusted",
        owner="Facilities",
        notes="Manual classification",
    )

    created = service.replace(device_id, data)
    assert created.device_id == device_id
    assert created.category.value == "camera"
    assert service.replace(device_id, data).created_at == created.created_at
    assert IdentityService(Database(path)).get(device_id).owner == "Facilities"

    service.delete(device_id)
    with pytest.raises(IdentityNotFoundError):
        service.get(device_id)
    assert InventoryService(Database(path)).get(device_id).id == device_id


def test_identity_rejects_missing_devices_and_invalid_values(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = IdentityService(database)

    with pytest.raises(DeviceNotFoundError):
        service.replace(
            "missing",
            DeviceIdentityData(category="computer"),
        )
    with pytest.raises(ValueError):
        DeviceIdentityData(category="workstation")
    with pytest.raises(ValueError):
        DeviceIdentityData(category="computer", confidence="verified")


def test_identity_foreign_key_cascades_when_inventory_device_is_removed(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    device_id = create_device(database, "aa:bb:cc:dd:ee:51")
    service = IdentityService(database)
    service.replace(device_id, DeviceIdentityData(category="printer"))

    with database.transaction() as connection:
        connection.execute("DELETE FROM devices WHERE id = ?", (device_id,))

    assert service.list() == []
