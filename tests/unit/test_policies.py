import pytest

from netos.persistence.database import Database
from netos.policies.service import (
    PolicyConflictError,
    PolicyNotFoundError,
    PolicyService,
    PolicyValidationError,
)


def valid_policy(name: str = "allow-web") -> dict[str, object]:
    return {
        "name": name,
        "description": "web access",
        "enabled": True,
        "priority": 100,
        "direction": "inbound",
        "action": "allow",
        "protocol": "tcp",
        "source_cidr": "192.168.1.10",
        "destination_cidr": "10.0.0.0/24",
        "source_port": 1024,
        "destination_port": 443,
    }


def test_policy_crud_survives_service_recreation(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    first = PolicyService(database)
    created = first.create(valid_policy())
    assert created.source_cidr == "192.168.1.10/32"
    assert created.updated_at == created.created_at

    second = PolicyService(Database(tmp_path / "netos.sqlite3"))
    loaded = second.get(created.id)
    assert loaded.name == "allow-web"
    updated = second.update(created.id, {**valid_policy(), "enabled": False})
    assert updated.enabled is False
    assert updated.created_at == created.created_at
    assert updated.updated_at >= created.updated_at
    second.delete(created.id)
    with pytest.raises(PolicyNotFoundError):
        second.get(created.id)


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"source_cidr": "not-a-network"},
        {"destination_cidr": "192.168.1.999"},
        {"source_port": 0},
        {"destination_port": 65536},
        {"protocol": "sctp"},
        {"protocol": "any", "destination_port": 53},
        {"protocol": "icmp", "source_port": 8},
        {"priority": -1},
    ],
)
def test_invalid_policy_data_is_rejected(tmp_path, changes):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    data = valid_policy()
    data.update(changes)
    with pytest.raises(PolicyValidationError):
        PolicyService(database).create(data)


def test_duplicate_names_and_missing_updates_are_rejected(tmp_path):
    database = Database(tmp_path / "netos.sqlite3")
    database.initialize()
    service = PolicyService(database)
    service.create(valid_policy())
    with pytest.raises(PolicyConflictError):
        service.create(valid_policy())
    with pytest.raises(PolicyNotFoundError):
        service.update("missing", valid_policy())
