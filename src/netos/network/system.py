"""Read-only network data acquisition using psutil and Linux system files."""

from __future__ import annotations

import ipaddress
import platform
import re
import socket
from datetime import datetime, timezone
from pathlib import Path

import psutil

from netos.network.models import (
    DeviceObservation,
    InterfaceAddress,
    InterfaceInfo,
    InterfaceStatistics,
)


def _prefix_length(address: object) -> int | None:
    netmask = getattr(address, "netmask", None)
    if not netmask:
        return None
    try:
        return ipaddress.ip_network(
            f"{address.address}/{netmask}", strict=False
        ).prefixlen
    except ValueError:
        return None


def _is_loopback(name: str, addresses: list[object]) -> bool:
    return name.lower() in {"lo", "loopback"} or any(
        getattr(address, "family", None) == socket.AF_INET
        and getattr(address, "address", "").startswith("127.")
        for address in addresses
    )


def _linux_virtual(name: str) -> bool | None:
    if platform.system() != "Linux":
        return None
    device = Path("/sys/class/net") / name
    try:
        return not (device / "device").exists()
    except OSError:
        return None


def _linux_interface_type(name: str) -> str | None:
    if platform.system() != "Linux":
        return None
    type_path = Path("/sys/class/net") / name / "type"
    try:
        value = type_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return None
    return {"1": "ethernet", "772": "loopback", "801": "tunnel"}.get(
        value, f"linux_type_{value}"
    )


def discover_interfaces() -> tuple[InterfaceInfo, ...]:
    addresses = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    result: list[InterfaceInfo] = []
    for name in sorted(addresses):
        current_addresses = addresses.get(name, [])
        normalized: list[InterfaceAddress] = []
        mac_address: str | None = None
        for address in current_addresses:
            family = "ipv4" if address.family == socket.AF_INET else (
                "ipv6" if address.family == socket.AF_INET6 else "mac"
            )
            if family == "mac":
                mac_address = address.address or None
                continue
            normalized.append(
                InterfaceAddress(
                    address=address.address,
                    family=family,
                    prefix_length=_prefix_length(address),
                )
            )
        interface_stats = stats.get(name)
        result.append(
            InterfaceInfo(
                name=name,
                index=_interface_index(name),
                mac_address=mac_address,
                addresses=tuple(normalized),
                is_up=interface_stats.isup if interface_stats else None,
                mtu=interface_stats.mtu if interface_stats else None,
                interface_type=_linux_interface_type(name),
                is_loopback=_is_loopback(name, current_addresses),
                is_virtual=_linux_virtual(name),
            )
        )
    return tuple(result)


def _interface_index(name: str) -> int | None:
    try:
        return socket.if_nametoindex(name)
    except (AttributeError, OSError):
        return None


def read_interface_statistics() -> dict[str, InterfaceStatistics]:
    counters = psutil.net_io_counters(pernic=True)
    return {
        name: InterfaceStatistics(
            name=name,
            bytes_received=value.bytes_recv,
            bytes_transmitted=value.bytes_sent,
            packets_received=value.packets_recv,
            packets_transmitted=value.packets_sent,
            receive_errors=value.errin,
            transmit_errors=value.errout,
            receive_drops=value.dropin,
            transmit_drops=value.dropout,
        )
        for name, value in counters.items()
    }


def read_arp_cache() -> tuple[DeviceObservation, ...]:
    if platform.system() != "Linux":
        return ()
    path = Path("/proc/net/arp")
    lines = path.read_text(encoding="ascii").splitlines()[1:]
    observed_at = datetime.now(timezone.utc)
    observations: list[DeviceObservation] = []
    for line in lines:
        fields = line.split()
        if len(fields) < 6:
            continue
        ip_address, _, flags, mac_address, _, interface_name = fields[:6]
        if flags == "0x0" or mac_address == "00:00:00:00:00:00":
            continue
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            continue
        if not re.fullmatch(
            r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", mac_address
        ):
            continue
        observations.append(
            DeviceObservation(
                ip_address=ip_address,
                mac_address=mac_address.lower(),
                interface_name=interface_name or None,
                source="linux_arp_cache",
                observed_at=observed_at,
                identification="observed",
            )
        )
    return tuple(observations)
