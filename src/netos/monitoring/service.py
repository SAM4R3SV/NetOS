"""Non-privileged monitor service and safe rate calculations."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import monotonic

import psutil

from netos.events.monitoring import EventStore
from netos.network.models import (
    DeviceObservation,
    InterfaceInfo,
    InterfaceStatistics,
)
from netos.network.system import (
    discover_interfaces,
    read_arp_cache,
    read_interface_statistics,
)


@dataclass(frozen=True)
class Rate:
    bytes_received_per_second: float
    bytes_transmitted_per_second: float


class MonitorService:
    def __init__(self, interval_seconds: int, discovery_enabled: bool) -> None:
        self.interval_seconds = interval_seconds
        self.discovery_enabled = discovery_enabled
        self.events = EventStore()
        self._interfaces: tuple[InterfaceInfo, ...] = ()
        self._statistics: dict[str, InterfaceStatistics] = {}
        self._devices: tuple[DeviceObservation, ...] = ()
        self._rates: dict[str, Rate] = {}
        self._previous_statistics: dict[str, tuple[InterfaceStatistics, float]] = {}
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.collect_once()
        self._thread = Thread(target=self._run, name="netos-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval_seconds + 1)
            self._thread = None

    def collect_once(self) -> None:
        if not self.discovery_enabled:
            return
        try:
            interfaces = discover_interfaces()
            devices = read_arp_cache()
            statistics = read_interface_statistics()
        except (OSError, RuntimeError, psutil.Error) as exc:
            self.events.add_error("network", str(exc), "system")
            return
        now = monotonic()
        with self._lock:
            self._interfaces = interfaces
            self._devices = devices
            self._update_rates(statistics, now)
            self._statistics = statistics
        self.events.observe_interfaces(interfaces)

    def snapshot(self):
        with self._lock:
            return self._interfaces, dict(self._statistics), self._devices, dict(self._rates)

    def _update_rates(self, statistics: dict[str, InterfaceStatistics], now: float) -> None:
        rates: dict[str, Rate] = {}
        for name, current in statistics.items():
            previous = self._previous_statistics.get(name)
            self._previous_statistics[name] = (current, now)
            if not previous:
                continue
            old, old_time = previous
            elapsed = now - old_time
            received = current.bytes_received - old.bytes_received
            transmitted = current.bytes_transmitted - old.bytes_transmitted
            if elapsed <= 0 or received < 0 or transmitted < 0:
                continue
            rates[name] = Rate(received / elapsed, transmitted / elapsed)
        self._rates = rates

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.collect_once()
