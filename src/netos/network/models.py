"""Immutable contracts for network monitoring data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InterfaceAddress:
    address: str
    family: str
    prefix_length: int | None


@dataclass(frozen=True)
class InterfaceInfo:
    name: str
    index: int | None
    mac_address: str | None
    addresses: tuple[InterfaceAddress, ...]
    is_up: bool | None
    mtu: int | None
    interface_type: str | None
    is_loopback: bool
    is_virtual: bool | None


@dataclass(frozen=True)
class InterfaceStatistics:
    name: str
    bytes_received: int
    bytes_transmitted: int
    packets_received: int
    packets_transmitted: int
    receive_errors: int
    transmit_errors: int
    receive_drops: int
    transmit_drops: int


@dataclass(frozen=True)
class DeviceObservation:
    ip_address: str | None
    mac_address: str | None
    interface_name: str | None
    source: str
    observed_at: datetime
    identification: str


@dataclass(frozen=True)
class MonitorEvent:
    event_type: str
    occurred_at: datetime
    resource: str
    description: str
    source: str
