"""Centralized, environment-backed runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _env_int(name: str, default: int, minimum: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return parsed


@dataclass(frozen=True)
class Settings:
    """Validated settings that contain no secrets."""

    environment: str = "development"
    database_path: Path = Path("data/netos.sqlite3")
    log_level: str = "INFO"
    log_directory: Path = Path("logs")
    log_retention_days: int = 30
    audit_retention_days: int = 30
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_reload: bool = False
    api_title: str = "NetOS API"
    monitoring_enabled: bool = True
    monitoring_interval_seconds: int = 5
    network_discovery_enabled: bool = True
    version: str = "0.1.0"

    @classmethod
    def from_env(cls) -> Settings:
        log_level = os.getenv("NETOS_LOG_LEVEL", "INFO").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("NETOS_LOG_LEVEL is not a supported log level")
        environment = os.getenv("NETOS_ENVIRONMENT", "development").strip()
        if not environment:
            raise ValueError("NETOS_ENVIRONMENT must not be empty")
        return cls(
            environment=environment,
            database_path=Path(
                os.getenv("NETOS_DATABASE_PATH", "data/netos.sqlite3")
            ),
            log_level=log_level,
            log_directory=Path(os.getenv("NETOS_LOG_DIRECTORY", "logs")),
            log_retention_days=_env_int("NETOS_LOG_RETENTION_DAYS", 30, 1),
            audit_retention_days=_env_int(
                "NETOS_AUDIT_RETENTION_DAYS", 30, 1
            ),
            api_host=os.getenv("NETOS_API_HOST", "127.0.0.1"),
            api_port=_env_int("NETOS_API_PORT", 8000, 1),
            api_reload=_env_bool("NETOS_API_RELOAD", False),
            api_title=os.getenv("NETOS_API_TITLE", "NetOS API"),
            monitoring_enabled=_env_bool("NETOS_MONITORING_ENABLED", True),
            monitoring_interval_seconds=_env_int(
                "NETOS_MONITORING_INTERVAL_SECONDS", 5, 1
            ),
            network_discovery_enabled=_env_bool(
                "NETOS_NETWORK_DISCOVERY_ENABLED", True
            ),
        )

    def public_dict(self) -> dict[str, str | int | bool]:
        """Return configuration safe to expose through the API."""
        return {
            "environment": self.environment,
            "log_level": self.log_level,
            "log_retention_days": self.log_retention_days,
            "audit_retention_days": self.audit_retention_days,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "api_reload": self.api_reload,
            "version": self.version,
            "monitoring_enabled": self.monitoring_enabled,
            "monitoring_interval_seconds": self.monitoring_interval_seconds,
            "network_discovery_enabled": self.network_discovery_enabled,
        }
