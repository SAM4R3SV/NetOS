"""Strict, non-applying network policy contracts."""

from __future__ import annotations

import ipaddress
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Action(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class Protocol(StrEnum):
    ANY = "any"
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


def _normalize_network(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        address = ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise ValueError(f"invalid network or IP address: {value}") from exc
    return str(address)


class PolicyData(BaseModel):
    """Validated policy fields shared by create and replacement operations."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    priority: int = Field(ge=0, le=2_147_483_647)
    direction: Direction
    action: Action
    protocol: Protocol
    source_cidr: str | None = None
    destination_cidr: str | None = None
    source_port: int | None = Field(default=None, ge=1, le=65535)
    destination_port: int | None = Field(default=None, ge=1, le=65535)

    @model_validator(mode="before")
    @classmethod
    def reject_blank_name(cls, values: object) -> object:
        if isinstance(values, dict) and isinstance(values.get("name"), str):
            values["name"] = values["name"].strip()
        if isinstance(values, dict):
            for field, enum_type in (
                ("direction", Direction),
                ("action", Action),
                ("protocol", Protocol),
            ):
                value = values.get(field)
                if isinstance(value, str):
                    try:
                        values[field] = enum_type(value)
                    except ValueError:
                        pass
        return values

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.source_cidr is not None:
            object.__setattr__(self, "source_cidr", _normalize_network(self.source_cidr))
        if self.destination_cidr is not None:
            object.__setattr__(
                self,
                "destination_cidr",
                _normalize_network(self.destination_cidr),
            )
        if self.protocol in {Protocol.ANY, Protocol.ICMP} and (
            self.source_port is not None or self.destination_port is not None
        ):
            raise ValueError("ports are not valid for protocol any or icmp")
        return self


class Policy(PolicyData):
    id: str
    created_at: datetime
    updated_at: datetime
