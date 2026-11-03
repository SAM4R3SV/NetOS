"""Validated API response contracts."""

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    version: str


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    environment: str
    database: str
    audit_events: int


class PublicConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment: str
    log_level: str
    log_retention_days: int
    audit_retention_days: int
    api_host: str
    api_port: int
    api_reload: bool
    version: str
    monitoring_enabled: bool
    monitoring_interval_seconds: int
    network_discovery_enabled: bool


class AddressResponse(BaseModel):
    address: str
    family: str
    prefix_length: int | None


class InterfaceResponse(BaseModel):
    name: str
    index: int | None
    mac_address: str | None
    addresses: list[AddressResponse]
    is_up: bool | None
    mtu: int | None
    interface_type: str | None
    is_loopback: bool
    is_virtual: bool | None


class StatisticsResponse(BaseModel):
    name: str
    bytes_received: int
    bytes_transmitted: int
    packets_received: int
    packets_transmitted: int
    receive_errors: int
    transmit_errors: int
    receive_drops: int
    transmit_drops: int
    bytes_received_per_second: float | None = None
    bytes_transmitted_per_second: float | None = None


class DeviceResponse(BaseModel):
    ip_address: str | None
    mac_address: str | None
    interface_name: str | None
    source: str
    observed_at: str
    identification: str


class EventResponse(BaseModel):
    event_type: str
    occurred_at: str
    resource: str
    description: str
    source: str


class NetworkSummaryResponse(BaseModel):
    interface_count: int
    up_interface_count: int
    device_count: int
    event_count: int
