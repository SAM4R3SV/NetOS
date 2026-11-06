"""Notification contracts and validated filter values."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class NotificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Notification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    event_type: str
    title: str
    message: str
    severity: NotificationSeverity
    created_at: datetime
    is_read: bool
    device_id: str | None = None
    deduplication_key: str
