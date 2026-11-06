"""Business service for persistent passive device observations."""

from __future__ import annotations

from uuid import uuid4

from netos.inventory.model import (
    DeviceMetadataPatch,
    DeviceObservationInput,
    DeviceRecord,
)
from netos.inventory.repository import InventoryRepository
from netos.persistence.database import Database


class DeviceNotFoundError(LookupError):
    """Raised when an inventory device does not exist."""


class InventoryService:
    def __init__(
        self,
        database: Database,
        repository: InventoryRepository | None = None,
    ) -> None:
        self.repository = repository or InventoryRepository(database)

    def ingest(self, observations: tuple[object, ...]) -> int:
        """Persist valid MAC observations and return the number accepted."""
        accepted = 0
        for raw_observation in observations:
            try:
                observation = DeviceObservationInput.from_observation(raw_observation)
            except (TypeError, ValueError):
                continue
            existing = self.repository.get_by_mac(observation.mac_address)
            if existing is None:
                self.repository.create(
                    DeviceRecord(
                        id=str(uuid4()),
                        mac_address=observation.mac_address,
                        first_seen=observation.observed_at,
                        last_seen=observation.observed_at,
                        last_ip=observation.ip_address,
                        last_interface=observation.interface_name,
                    )
                )
            elif observation.observed_at >= existing.last_seen:
                self.repository.update_observation(
                    existing.id,
                    observation.observed_at,
                    observation.ip_address,
                    observation.interface_name,
                )
            accepted += 1
        return accepted

    def list(self) -> list[DeviceRecord]:
        return self.repository.list()

    def get(self, device_id: str) -> DeviceRecord:
        device = self.repository.get(device_id)
        if device is None:
            raise DeviceNotFoundError("device not found")
        return device

    def update_metadata(
        self, device_id: str, patch: DeviceMetadataPatch
    ) -> DeviceRecord:
        self.get(device_id)
        updated = self.repository.update_metadata(device_id, patch)
        if updated is None:
            raise DeviceNotFoundError("device not found")
        return updated
