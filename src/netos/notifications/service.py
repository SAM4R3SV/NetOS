"""Notification rules and persistence service."""

from __future__ import annotations

import logging
import sqlite3

from netos.events.monitoring import MonitorEvent
from netos.notifications.model import Notification, NotificationSeverity
from netos.notifications.repository import NotificationRepository
from netos.persistence.database import Database

logger = logging.getLogger("netos.notifications")


class NotificationNotFoundError(LookupError):
    """Raised when a notification does not exist."""


class NotificationService:
    def __init__(
        self,
        database: Database,
        repository: NotificationRepository | None = None,
    ) -> None:
        self.repository = repository or NotificationRepository(database)

    def process_event(self, event: MonitorEvent) -> Notification | None:
        rule = self._rule_for(event)
        if rule is None:
            return None
        title, severity = rule
        deduplication_key = (
            f"{event.event_type}:{event.resource}:{event.description}"
        )
        try:
            return self.repository.create_from_event(
                event,
                title,
                severity,
                deduplication_key,
            )
        except sqlite3.Error:
            logger.exception(
                "Could not persist notification for event %s",
                event.event_type,
            )
            return None

    def list(
        self,
        limit: int = 100,
        is_read: bool | None = None,
        severity: NotificationSeverity | None = None,
    ) -> list[Notification]:
        return self.repository.list(limit, is_read, severity)

    def get(self, notification_id: str) -> Notification:
        notification = self.repository.get(notification_id)
        if notification is None:
            raise NotificationNotFoundError("notification not found")
        return notification

    def mark_read(self, notification_id: str) -> Notification:
        notification = self.repository.mark_read(notification_id)
        if notification is None:
            raise NotificationNotFoundError("notification not found")
        return notification

    @staticmethod
    def _rule_for(
        event: MonitorEvent,
    ) -> tuple[str, NotificationSeverity] | None:
        if event.event_type == "interface_disappeared":
            return "Network interface disappeared", NotificationSeverity.WARNING
        if event.event_type == "source_error":
            return "Monitoring source error", NotificationSeverity.WARNING
        return None
