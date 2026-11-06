from datetime import datetime, timezone

from netos.inventory.model import normalize_mac
from netos.inventory.service import InventoryService
from netos.network.models import DeviceObservation
from netos.persistence.database import Database


def observation(
    mac: str | None,
    ip: str | None = "192.168.1.10",
    when: datetime | None = None,
) -> DeviceObservation:
    return DeviceObservation(
        ip_address=ip,
        mac_address=mac,
        interface_name="eth0",
        source="arp",
        observed_at=when or datetime.now(timezone.utc),
        identification="mac",
    )


def test_normalize_mac_accepts_common_notations_and_rejects_invalid_values():
    assert normalize_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac("not-a-mac") is None
    assert normalize_mac("00:00:00:00:00:00") is None
    assert normalize_mac(None) is None


def test_inventory_deduplicates_by_mac_and_preserves_first_seen(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = InventoryService(database)
    first = datetime(2025, 1, 1, tzinfo=timezone.utc)
    second = datetime(2025, 1, 2, tzinfo=timezone.utc)

    assert service.ingest((observation("AA:BB:CC:DD:EE:FF", when=first),)) == 1
    assert service.ingest(
        (observation("aa-bb-cc-dd-ee-ff", ip="192.168.1.20", when=second),)
    ) == 1

    devices = service.list()
    assert len(devices) == 1
    assert devices[0].first_seen == first
    assert devices[0].last_seen == second
    assert devices[0].last_ip == "192.168.1.20"
    service.ingest(
        (observation("aa:bb:cc:dd:ee:ff", ip="192.168.1.5", when=first),)
    )
    assert service.list()[0].last_seen == second
    assert service.list()[0].last_ip == "192.168.1.20"


def test_inventory_skips_unidentified_observations_and_allows_shared_ip(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = InventoryService(database)

    service.ingest(
        (
            observation(None),
            observation("aa:bb:cc:dd:ee:01", ip="192.168.1.30"),
            observation("aa:bb:cc:dd:ee:02", ip="192.168.1.30"),
        )
    )

    devices = service.list()
    assert len(devices) == 2
    assert {device.mac_address for device in devices} == {
        "aa:bb:cc:dd:ee:01",
        "aa:bb:cc:dd:ee:02",
    }


def test_inventory_survives_service_recreation(tmp_path):
    path = tmp_path / "netos.sqlite3"
    database = Database(path)
    database.initialize()
    InventoryService(database).ingest((observation("aa:bb:cc:dd:ee:10"),))

    recreated = InventoryService(Database(path))
    assert len(recreated.list()) == 1
