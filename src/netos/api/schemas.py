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
