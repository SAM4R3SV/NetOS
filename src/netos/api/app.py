"""FastAPI composition root for the local control-plane API."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from netos.api.schemas import (
    HealthResponse,
    PublicConfigResponse,
    StatusResponse,
)
from netos.config import Settings
from netos.observability.logging import configure_logging
from netos.persistence.database import Database
from netos.persistence.repositories import AuditRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    database = Database(runtime.database_path)
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
        logger.info("NetOS control plane started")
        yield
        logger.info("NetOS control plane stopped")

    app = FastAPI(title=runtime.api_title, version=runtime.version, lifespan=lifespan)

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

    return app
