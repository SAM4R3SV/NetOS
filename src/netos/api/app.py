"""FastAPI composition root for the local control-plane API."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse, Response

from netos.api.schemas import (
    DeviceResponse,
    EventResponse,
    HealthResponse,
    InterfaceResponse,
    NetworkSummaryResponse,
    PublicConfigResponse,
    StatisticsResponse,
    StatusResponse,
)
from netos.config import Settings
from netos.delivery.engine import DeliveryEngine
from netos.identity.model import DeviceIdentity, DeviceIdentityData
from netos.identity.service import (
    DeviceNotFoundError as IdentityDeviceNotFoundError,
    IdentityNotFoundError,
    IdentityService,
)
from netos.inventory.model import DeviceMetadataPatch, DeviceRecord
from netos.inventory.service import DeviceNotFoundError, InventoryService
from netos.monitoring.service import MonitorService
from netos.network.models import InterfaceInfo
from netos.observability.logging import configure_logging
from netos.notifications.model import Notification, NotificationSeverity
from netos.notifications.service import (
    NotificationNotFoundError,
    NotificationService,
)
from netos.persistence.database import Database
from netos.persistence.repositories import AuditRepository
from netos.policies.model import Policy, PolicyData
from netos.policies.service import (
    PolicyConflictError,
    PolicyNotFoundError,
    PolicyService,
    PolicyValidationError,
)
from netos.security.secrets.manager import SecretManager


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    database = Database(runtime.database_path)
    delivery = DeliveryEngine(database)
    identities = IdentityService(database)
    inventory = InventoryService(database)
    notifications = NotificationService(database)
    policies = PolicyService(database)
    secret_manager = (
        SecretManager(runtime.secrets_directory)
        if runtime.secrets_directory is not None
        else None
    )
    monitor = MonitorService(
        runtime.monitoring_interval_seconds,
        runtime.network_discovery_enabled,
    )
    monitor.set_observation_sink(inventory.ingest)
    monitor.events.set_event_sink(notifications.process_event)
    logger = logging.getLogger("netos.api")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        configure_logging(
            runtime.log_directory,
            runtime.log_level,
            runtime.log_retention_days,
        )
        if secret_manager is not None:
            secret_manager.initialize()
        database.initialize()
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=runtime.audit_retention_days)
        ).isoformat()
        AuditRepository(database).purge_older_than(cutoff)
        if runtime.monitoring_enabled:
            monitor.start()
        delivery.start()
        logger.info("NetOS control plane started")
        try:
            yield
        finally:
            monitor.stop()
            delivery.stop()
            if secret_manager is not None:
                secret_manager.close()
            logger.info("NetOS control plane stopped")

    app = FastAPI(title=runtime.api_title, version=runtime.version, lifespan=lifespan)
    app.state.monitor = monitor
    app.state.delivery = delivery
    app.state.secret_manager = secret_manager

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Internal server error"},
        )

    @app.exception_handler(PolicyValidationError)
    async def policy_validation_error(
        _: Request, exc: PolicyValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "invalid_policy", "message": str(exc)},
        )

    @app.exception_handler(PolicyNotFoundError)
    async def policy_not_found_error(
        _: Request, exc: PolicyNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=http_status.HTTP_404_NOT_FOUND,
            content={"error": "policy_not_found", "message": str(exc)},
        )

    @app.exception_handler(PolicyConflictError)
    async def policy_conflict_error(
        _: Request, exc: PolicyConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=http_status.HTTP_409_CONFLICT,
            content={"error": "policy_conflict", "message": str(exc)},
        )

    @app.exception_handler(DeviceNotFoundError)
    async def device_not_found_error(
        _: Request, exc: DeviceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=http_status.HTTP_404_NOT_FOUND,
            content={"error": "device_not_found", "message": str(exc)},
        )

    @app.exception_handler(IdentityDeviceNotFoundError)
    async def identity_device_not_found_error(
        _: Request, exc: IdentityDeviceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=http_status.HTTP_404_NOT_FOUND,
            content={"error": "device_not_found", "message": str(exc)},
        )

    @app.exception_handler(IdentityNotFoundError)
    async def identity_not_found_error(
        _: Request, exc: IdentityNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=http_status.HTTP_404_NOT_FOUND,
            content={"error": "identity_not_found", "message": str(exc)},
        )

    @app.exception_handler(NotificationNotFoundError)
    async def notification_not_found_error(
        _: Request, exc: NotificationNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=http_status.HTTP_404_NOT_FOUND,
            content={"error": "notification_not_found", "message": str(exc)},
        )

    @app.get("/health", response_model=HealthResponse, tags=["service"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=runtime.version)

    @app.get("/api/v1/version", response_model=HealthResponse, tags=["service"])
    async def version() -> HealthResponse:
        return HealthResponse(status="ok", version=runtime.version)

    @app.get("/api/v1/status", response_model=StatusResponse, tags=["service"])
    async def status() -> StatusResponse:
        audit = AuditRepository(database)
        try:
            database.initialize()
            count = audit.count()
        except Exception as exc:
            logger.exception("Database status check failed")
            raise RuntimeError("database_unavailable") from exc
        return StatusResponse(
            status="ready",
            environment=runtime.environment,
            database="ok",
            audit_events=count,
        )

    @app.get(
        "/api/v1/configuration",
        response_model=PublicConfigResponse,
        tags=["configuration"],
    )
    async def configuration() -> PublicConfigResponse:
        return PublicConfigResponse(**runtime.public_dict())

    @app.get(
        "/api/v1/policies",
        response_model=list[Policy],
        tags=["policies"],
        summary="List stored network policies",
    )
    async def list_policies() -> list[Policy]:
        return policies.list()

    @app.get(
        "/api/v1/policies/{policy_id}",
        response_model=Policy,
        tags=["policies"],
        summary="Get a stored network policy",
    )
    async def get_policy(
        policy_id: str = Path(min_length=1, max_length=128),
    ) -> Policy:
        return policies.get(policy_id)

    @app.post(
        "/api/v1/policies",
        response_model=Policy,
        status_code=http_status.HTTP_201_CREATED,
        tags=["policies"],
        summary="Store a network policy without applying it",
    )
    async def create_policy(policy: PolicyData) -> Policy:
        return policies.create(policy)

    @app.put(
        "/api/v1/policies/{policy_id}",
        response_model=Policy,
        tags=["policies"],
        summary="Replace a stored network policy",
    )
    async def update_policy(
        policy: PolicyData,
        policy_id: str = Path(min_length=1, max_length=128),
    ) -> Policy:
        return policies.update(policy_id, policy)

    @app.delete(
        "/api/v1/policies/{policy_id}",
        status_code=http_status.HTTP_204_NO_CONTENT,
        tags=["policies"],
        summary="Delete a stored network policy",
    )
    async def delete_policy(
        policy_id: str = Path(min_length=1, max_length=128),
    ) -> Response:
        policies.delete(policy_id)
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    @app.get(
        "/api/v1/inventory",
        response_model=list[DeviceRecord],
        tags=["inventory"],
        summary="List persistently observed devices",
    )
    async def list_inventory() -> list[DeviceRecord]:
        return inventory.list()

    @app.get(
        "/api/v1/inventory/{device_id}",
        response_model=DeviceRecord,
        tags=["inventory"],
        summary="Get a persistently observed device",
    )
    async def get_inventory_device(
        device_id: str = Path(min_length=1, max_length=128),
    ) -> DeviceRecord:
        return inventory.get(device_id)

    @app.patch(
        "/api/v1/inventory/{device_id}",
        response_model=DeviceRecord,
        tags=["inventory"],
        summary="Update administrative inventory metadata",
    )
    async def update_inventory_device(
        patch: DeviceMetadataPatch,
        device_id: str = Path(min_length=1, max_length=128),
    ) -> DeviceRecord:
        return inventory.update_metadata(device_id, patch)

    @app.get(
        "/api/v1/identity",
        response_model=list[DeviceIdentity],
        tags=["identity"],
        summary="List administrative device classifications",
    )
    async def list_identities() -> list[DeviceIdentity]:
        return identities.list()

    @app.get(
        "/api/v1/identity/{device_id}",
        response_model=DeviceIdentity,
        tags=["identity"],
        summary="Get a device classification",
    )
    async def get_identity(
        device_id: str = Path(min_length=1, max_length=128),
    ) -> DeviceIdentity:
        return identities.get(device_id)

    @app.put(
        "/api/v1/identity/{device_id}",
        response_model=DeviceIdentity,
        tags=["identity"],
        summary="Create or replace a device classification",
    )
    async def replace_identity(
        data: DeviceIdentityData,
        device_id: str = Path(min_length=1, max_length=128),
    ) -> DeviceIdentity:
        return identities.replace(device_id, data)

    @app.delete(
        "/api/v1/identity/{device_id}",
        status_code=http_status.HTTP_204_NO_CONTENT,
        tags=["identity"],
        summary="Remove a device classification",
    )
    async def delete_identity(
        device_id: str = Path(min_length=1, max_length=128),
    ) -> Response:
        identities.delete(device_id)
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)

    @app.get(
        "/api/v1/notifications",
        response_model=list[Notification],
        tags=["notifications"],
        summary="List internal notifications",
    )
    async def list_notifications(
        is_read: bool | None = Query(default=None),
        severity: NotificationSeverity | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[Notification]:
        return notifications.list(limit, is_read, severity)

    @app.get(
        "/api/v1/notifications/{notification_id}",
        response_model=Notification,
        tags=["notifications"],
        summary="Get an internal notification",
    )
    async def get_notification(
        notification_id: str = Path(min_length=1, max_length=128),
    ) -> Notification:
        return notifications.get(notification_id)

    @app.patch(
        "/api/v1/notifications/{notification_id}/read",
        response_model=Notification,
        tags=["notifications"],
        summary="Mark an internal notification as read",
    )
    async def mark_notification_read(
        notification_id: str = Path(min_length=1, max_length=128),
    ) -> Notification:
        return notifications.mark_read(notification_id)

    @app.get(
        "/api/v1/network/interfaces",
        response_model=list[InterfaceResponse],
        tags=["network"],
    )
    async def network_interfaces() -> list[InterfaceResponse]:
        interfaces, _, _, _ = monitor.snapshot()
        return [_interface_response(interface) for interface in interfaces]

    @app.get(
        "/api/v1/network/interfaces/{interface_name}",
        response_model=InterfaceResponse,
        tags=["network"],
    )
    async def network_interface(interface_name: str = Path(min_length=1, max_length=128)) -> InterfaceResponse:
        interfaces, _, _, _ = monitor.snapshot()
        for interface in interfaces:
            if interface.name == interface_name:
                return _interface_response(interface)
        raise HTTPException(status_code=404, detail="interface_not_found")

    @app.get(
        "/api/v1/network/interfaces/{interface_name}/statistics",
        response_model=StatisticsResponse,
        tags=["network"],
    )
    async def network_statistics(interface_name: str = Path(min_length=1, max_length=128)) -> StatisticsResponse:
        _, statistics, _, rates = monitor.snapshot()
        current = statistics.get(interface_name)
        if current is None:
            raise HTTPException(status_code=404, detail="interface_not_found")
        rate = rates.get(interface_name)
        return StatisticsResponse(
            **current.__dict__,
            bytes_received_per_second=rate.bytes_received_per_second if rate else None,
            bytes_transmitted_per_second=rate.bytes_transmitted_per_second if rate else None,
        )

    @app.get(
        "/api/v1/network/summary",
        response_model=NetworkSummaryResponse,
        tags=["network"],
    )
    async def network_summary() -> NetworkSummaryResponse:
        interfaces, _, devices, _ = monitor.snapshot()
        return NetworkSummaryResponse(
            interface_count=len(interfaces),
            up_interface_count=sum(interface.is_up is True for interface in interfaces),
            device_count=len(devices),
            event_count=len(monitor.events.list()),
        )

    @app.get(
        "/api/v1/network/devices",
        response_model=list[DeviceResponse],
        tags=["network"],
    )
    async def network_devices() -> list[DeviceResponse]:
        _, _, devices, _ = monitor.snapshot()
        return [DeviceResponse(**_device_response(device)) for device in devices]

    @app.get(
        "/api/v1/network/events",
        response_model=list[EventResponse],
        tags=["network"],
    )
    async def network_events(
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[EventResponse]:
        return [
            EventResponse(
                event_type=event.event_type,
                occurred_at=event.occurred_at.isoformat(),
                resource=event.resource,
                description=event.description,
                source=event.source,
            )
            for event in monitor.events.list(limit)
        ]

    return app


def _interface_response(interface: InterfaceInfo) -> InterfaceResponse:
    return InterfaceResponse(
        name=interface.name,
        index=interface.index,
        mac_address=interface.mac_address,
        addresses=[
            {
                "address": address.address,
                "family": address.family,
                "prefix_length": address.prefix_length,
            }
            for address in interface.addresses
        ],
        is_up=interface.is_up,
        mtu=interface.mtu,
        interface_type=interface.interface_type,
        is_loopback=interface.is_loopback,
        is_virtual=interface.is_virtual,
    )


def _device_response(device) -> dict[str, str | None]:
    return {
        "ip_address": device.ip_address,
        "mac_address": device.mac_address,
        "interface_name": device.interface_name,
        "source": device.source,
        "observed_at": device.observed_at.isoformat(),
        "identification": device.identification,
    }
