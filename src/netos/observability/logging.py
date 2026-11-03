"""Structured logging with bounded local rotation."""

from __future__ import annotations

import json
import logging
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = correlation_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(directory: Path, level: str, retention_days: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("netos")
    for existing in root.handlers:
        existing.close()
    root.handlers.clear()
    handler = TimedRotatingFileHandler(
        directory / "netos.log",
        when="midnight",
        backupCount=retention_days,
        encoding="utf-8",
        utc=True,
    )
    handler.setFormatter(JsonFormatter())
    cutoff = time.time() - retention_days * 24 * 60 * 60
    for candidate in directory.glob("netos.log.*"):
        if candidate.is_file() and candidate.stat().st_mtime < cutoff:
            candidate.unlink()
    root.setLevel(level)
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler())
