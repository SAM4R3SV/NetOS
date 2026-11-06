"""Delivery job and provider result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Protocol


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    RETRY = "retry"
    FAILED = "failed"


@dataclass(frozen=True)
class DeliveryJob:
    id: str
    notification_id: str | None
    provider: str
    destination: str
    payload: Mapping[str, Any]
    status: DeliveryStatus
    attempt_count: int
    next_attempt_at: datetime
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    last_attempt_at: datetime | None
    http_status: int | None
    error: str | None


@dataclass(frozen=True)
class DeliveryResult:
    success: bool
    retryable: bool = False
    http_status: int | None = None
    retry_after_seconds: int | None = None
    error_code: str | None = None


class DeliveryProvider(Protocol):
    def send(self, job: DeliveryJob) -> DeliveryResult:
        """Deliver a job without exposing provider credentials to the engine."""
