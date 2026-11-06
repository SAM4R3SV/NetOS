"""Persistent device inventory contracts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from netos.network.models import DeviceObservation

_MAC_PATTERN = re.compile(r"^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$")


def normalize_mac(value: str | None) -> str | None:
    """Return canonical lowercase colon notation for a valid MAC address."""
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", ":")
    if not _MAC_PATTERN.fullmatch(normalized):
        return None
    if normalized == "00:00:00:00:00:00" or normalized == "ff:ff:ff:ff:ff:ff":
        return None
    return normalized


class DeviceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    mac_address: str
    hostname: str | None = None
    display_name: str | None = Field(default=None, max_length=200)
    vendor: str | None = None
    first_seen: datetime
    last_seen: datetime
    last_ip: str | None = None
    last_interface: str | None = None
    status: str = "observed"


class DeviceMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=200)


class DeviceObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mac_address: str
    ip_address: str | None = None
    interface_name: str | None = None
    observed_at: datetime

    @model_validator(mode="after")
    def normalize(self) -> Self:
        mac = normalize_mac(self.mac_address)
        if mac is None:
            raise ValueError("observation does not contain a valid MAC address")
        object.__setattr__(self, "mac_address", mac)
        return self

    @classmethod
    def from_observation(cls, observation: DeviceObservation) -> "DeviceObservationInput":
        return cls(
            mac_address=observation.mac_address or "",
            ip_address=observation.ip_address,
            interface_name=observation.interface_name,
            observed_at=observation.observed_at,
        )
