"""Business service for manual administrative device classification."""

from __future__ import annotations

from datetime import datetime, timezone

from netos.identity.model import DeviceIdentity, DeviceIdentityData
from netos.identity.repository import IdentityRepository
from netos.persistence.database import Database


class DeviceNotFoundError(LookupError):
    """Raised when the target inventory device does not exist."""


class IdentityNotFoundError(LookupError):
    """Raised when a device has no administrative identity."""


class IdentityService:
    def __init__(
        self,
        database: Database,
        repository: IdentityRepository | None = None,
    ) -> None:
        self.repository = repository or IdentityRepository(database)

    def list(self) -> list[DeviceIdentity]:
        return self.repository.list()

    def get(self, device_id: str) -> DeviceIdentity:
        identity = self.repository.get(device_id)
        if identity is None:
            if not self.repository.device_exists(device_id):
                raise DeviceNotFoundError("device not found")
            raise IdentityNotFoundError("device identity not found")
        return identity

    def replace(
        self, device_id: str, data: DeviceIdentityData
    ) -> DeviceIdentity:
        if not self.repository.device_exists(device_id):
            raise DeviceNotFoundError("device not found")
        return self.repository.replace(device_id, data, datetime.now(timezone.utc))

    def delete(self, device_id: str) -> None:
        if not self.repository.device_exists(device_id):
            raise DeviceNotFoundError("device not found")
        if not self.repository.delete(device_id):
            raise IdentityNotFoundError("device identity not found")
