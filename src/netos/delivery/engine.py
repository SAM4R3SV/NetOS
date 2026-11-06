"""Durable provider-agnostic delivery engine."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread
from uuid import uuid4
from typing import Any

from netos.delivery.model import (
    DeliveryJob,
    DeliveryProvider,
    DeliveryResult,
    DeliveryStatus,
)
from netos.delivery.repository import DeliveryRepository
from netos.persistence.database import Database

logger = logging.getLogger("netos.delivery")
_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "cookie",
    "authorization",
    "api_key",
)


class DeliveryEngine:
    def __init__(
        self,
        database: Database,
        repository: DeliveryRepository | None = None,
        max_attempts: int = 3,
        base_backoff_seconds: int = 5,
        max_backoff_seconds: int = 300,
        sending_timeout_seconds: int = 300,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.repository = repository or DeliveryRepository(database)
        self.max_attempts = max_attempts
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.sending_timeout_seconds = sending_timeout_seconds
        self._providers: dict[str, DeliveryProvider] = {}
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()

    def register_provider(self, name: str, provider: DeliveryProvider) -> None:
        if not name or not name.strip():
            raise ValueError("provider name must not be empty")
        with self._lock:
            self._providers[name] = provider

    def enqueue(
        self,
        provider: str,
        destination: str,
        payload: Mapping[str, Any],
        notification_id: str | None = None,
    ) -> DeliveryJob:
        sanitized = self._sanitize_payload(payload)
        encoded = json.dumps(sanitized, sort_keys=True)
        if len(encoded.encode("utf-8")) > 256 * 1024:
            raise ValueError("delivery payload is too large")
        if not provider.strip() or not destination.strip():
            raise ValueError("provider and destination must not be empty")
        now = datetime.now(timezone.utc)
        return self.repository.create(
            str(uuid4()),
            notification_id,
            provider,
            destination,
            sanitized,
            now,
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        now = datetime.now(timezone.utc)
        self.repository.recover_sending(
            now, now - timedelta(seconds=self.sending_timeout_seconds)
        )
        self._stop.clear()
        self._thread = Thread(target=self._run, name="netos-delivery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def process_once(self) -> DeliveryJob | None:
        now = datetime.now(timezone.utc)
        job = self.repository.claim_due(
            now, now - timedelta(seconds=self.sending_timeout_seconds)
        )
        if job is None:
            return None
        provider = self._providers.get(job.provider)
        if provider is None:
            self._finish(
                job,
                DeliveryResult(success=False, retryable=False, error_code="provider_unavailable"),
            )
            return self.repository.get(job.id)
        try:
            result = provider.send(job)
            if not isinstance(result, DeliveryResult):
                result = DeliveryResult(
                    success=False, retryable=False, error_code="invalid_provider_result"
                )
        except TimeoutError:
            result = DeliveryResult(
                success=False, retryable=True, error_code="provider_timeout"
            )
        except Exception:
            logger.error("Delivery provider failed for job %s", job.id)
            result = DeliveryResult(
                success=False, retryable=True, error_code="provider_error"
            )
        self._finish(job, result)
        return self.repository.get(job.id)

    def _finish(self, job: DeliveryJob, result: DeliveryResult) -> None:
        now = datetime.now(timezone.utc)
        if result.success:
            status = DeliveryStatus.SENT
            next_attempt = now
        elif not result.retryable or job.attempt_count >= self.max_attempts:
            status = DeliveryStatus.FAILED
            next_attempt = now
        else:
            status = DeliveryStatus.RETRY
            delay = result.retry_after_seconds or (
                self.base_backoff_seconds * (2 ** (job.attempt_count - 1))
            )
            next_attempt = now + timedelta(
                seconds=min(delay, self.max_backoff_seconds)
            )
        self.repository.complete(job.id, result, status, next_attempt, now)

    def _run(self) -> None:
        while not self._stop.wait(0.1):
            try:
                self.process_once()
            except Exception:
                logger.error("Delivery worker iteration failed")

    @staticmethod
    def _sanitize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise ValueError("delivery payload must be an object")
        sanitized = dict(payload)
        for key, value in sanitized.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                raise ValueError("delivery payload contains a prohibited field")
            if isinstance(value, Mapping):
                DeliveryEngine._sanitize_payload(value)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, Mapping):
                        DeliveryEngine._sanitize_payload(item)
        try:
            json.dumps(sanitized)
        except (TypeError, ValueError) as exc:
            raise ValueError("delivery payload is not JSON serializable") from exc
        return sanitized
