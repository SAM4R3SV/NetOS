"""FastAPI composition root for the local control-plane API."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse

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
from netos.monitoring.service import MonitorService
from netos.network.models import InterfaceInfo
from netos.observability.logging import configure_logging
from netos.persistence.database import Database
from netos.persistence.repositories import AuditRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    database = Database(runtime.database_path)
    monitor = MonitorService(
        runtime.monitoring_interval_seconds,
        runtime.network_discovery_enabled,
    )
    logger = logging.getLogger("netos.api")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        configure_logging(
            runtime.log_directory,
            runtime.log_level,
            runtime.log_retention_days,
        )
        database.initialize()
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=runtime.audit_retention_days)
        ).isoformat()
        AuditRepository(database).purge_older_than(cutoff)
        if runtime.monitoring_enabled:
            monitor.start()
        logger.info("NetOS control plane started")
        yield
        monitor.stop()
        logger.info("NetOS control plane stopped")

    app = FastAPI(title=runtime.api_title, version=runtime.version, lifespan=lifespan)
    app.state.monitor = monitor

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
