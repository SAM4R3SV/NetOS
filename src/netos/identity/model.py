"""Administrative device identity contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class IdentityCategory(str, Enum):
    COMPUTER = "computer"
    SERVER = "server"
    ROUTER = "router"
    SWITCH = "switch"
    CAMERA = "camera"
    IOT = "iot"
    MOBILE = "mobile"
    PRINTER = "printer"
    UNKNOWN = "unknown"


class IdentityConfidence(str, Enum):
    TRUSTED = "trusted"
    UNKNOWN = "unknown"
    RESTRICTED = "restricted"


class DeviceIdentityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: IdentityCategory
    role: str | None = Field(default=None, max_length=200)
    confidence: IdentityConfidence = IdentityConfidence.UNKNOWN
    owner: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class DeviceIdentity(DeviceIdentityData):
    device_id: str
    created_at: datetime
    updated_at: datetime
