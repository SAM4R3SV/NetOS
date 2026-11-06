"""In-memory, de-duplicated monitoring events."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
import logging
from threading import Lock

from netos.network.models import InterfaceInfo, MonitorEvent

logger = logging.getLogger("netos.events")


class EventStore:
    def __init__(self, maximum_events: int = 500) -> None:
        self._events: deque[MonitorEvent] = deque(maxlen=maximum_events)
        self._last_states: dict[str, tuple[object, ...]] = {}
        self._lock = Lock()
        self._event_sink: Callable[[MonitorEvent], object] | None = None

    def set_event_sink(self, sink: Callable[[MonitorEvent], object]) -> None:
        self._event_sink = sink

    def observe_interfaces(self, interfaces: tuple[InterfaceInfo, ...]) -> None:
        current = {interface.name: interface for interface in interfaces}
        with self._lock:
            previous_names = set(self._last_states)
            for name, interface in current.items():
                ipv4_addresses = tuple(
                    address
                    for address in interface.addresses
                    if address.family == "ipv4"
                )
                state = (interface.is_up, ipv4_addresses)
                previous = self._last_states.get(name)
                if previous is None:
                    self._append("interface_detected", name, f"Interface {name} detected")
                elif previous[0] != state[0]:
                    self._append("interface_state_changed", name, f"Interface {name} state changed")
                elif previous[1] != state[1]:
                    self._append("interface_ipv4_changed", name, f"Interface {name} IPv4 addresses changed")
                self._last_states[name] = state
            for name in previous_names - set(current):
                self._append("interface_disappeared", name, f"Interface {name} disappeared")
                self._last_states.pop(name, None)

    def add_error(self, resource: str, description: str, source: str) -> None:
        with self._lock:
            self._append("source_error", resource, description, source)

    def list(self, limit: int = 100) -> tuple[MonitorEvent, ...]:
        with self._lock:
            return tuple(list(self._events)[-limit:][::-1])

    def _append(self, event_type: str, resource: str, description: str, source: str = "network_monitor") -> None:
        event = MonitorEvent(
            event_type=event_type,
            occurred_at=datetime.now(timezone.utc),
            resource=resource,
            description=description,
            source=source,
        )
        self._events.append(event)
        if self._event_sink is not None:
            try:
                self._event_sink(event)
            except Exception:
                logger.exception("Event sink failed for %s", event_type)
