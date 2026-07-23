"""Read-only LAN discovery for legacy Ginlong/Solarman WiFi loggers."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass

DISCOVERY_MESSAGE = b"WIFIKIT-214028-READ"
DISCOVERY_PORT = 48899


@dataclass(frozen=True)
class LoggerAdvertisement:
    ip_address: str
    mac_address: str
    serial: int | None


def normalize_mac_address(value: str) -> str:
    normalized = value.replace(":", "").replace("-", "").upper()
    if len(normalized) != 12:
        raise ValueError(f"invalid logger MAC address: {value!r}")
    try:
        int(normalized, 16)
    except ValueError as error:
        raise ValueError(f"invalid logger MAC address: {value!r}") from error
    return normalized


def parse_discovery_response(data: bytes) -> LoggerAdvertisement:
    try:
        fields = data.decode("ascii").strip().split(",")
    except UnicodeDecodeError as error:
        raise ValueError("discovery response is not ASCII") from error

    if len(fields) < 2:
        raise ValueError("discovery response has fewer than two fields")

    ip_address = str(ipaddress.ip_address(fields[0].strip()))
    mac_address = normalize_mac_address(fields[1].strip())
    serial_text = fields[2].strip() if len(fields) >= 3 else ""
    try:
        serial = int(serial_text) if serial_text else None
    except ValueError as error:
        raise ValueError("discovery response has a non-numeric serial") from error

    return LoggerAdvertisement(ip_address, mac_address, serial)


def select_logger(
    advertisements: list[LoggerAdvertisement],
    *,
    mac_address: str | None,
    serial: int | None,
) -> LoggerAdvertisement | None:
    candidates = advertisements
    if mac_address:
        normalized_mac = normalize_mac_address(mac_address)
        candidates = [
            item for item in candidates if item.mac_address == normalized_mac
        ]

    # Some older sticks, including the currently deployed one, leave the serial
    # field empty. A populated but different serial is still a definite mismatch.
    if serial is not None:
        candidates = [
            item
            for item in candidates
            if item.serial is None or item.serial == serial
        ]

    if not candidates:
        return None
    if len(candidates) > 1:
        raise ValueError(
            "multiple WiFi loggers answered discovery; configure --logger-mac"
        )
    return candidates[0]


def _discover_loggers(
    broadcast_address: str,
    timeout: float,
    bind_address: str,
    port: int,
) -> list[LoggerAdvertisement]:
    deadline = time.monotonic() + timeout
    advertisements: dict[str, LoggerAdvertisement] = {}

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind((bind_address, port))
        sock.sendto(DISCOVERY_MESSAGE, (broadcast_address, port))

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, _ = sock.recvfrom(1024)
            except TimeoutError:
                break
            try:
                advertisement = parse_discovery_response(data)
            except ValueError:
                continue
            advertisements[advertisement.mac_address] = advertisement

    return list(advertisements.values())


async def discover_loggers(
    *,
    broadcast_address: str = "255.255.255.255",
    timeout: float = 3,
    bind_address: str = "0.0.0.0",
    port: int = DISCOVERY_PORT,
) -> list[LoggerAdvertisement]:
    """Broadcast the read-only discovery message and collect logger replies."""
    return await asyncio.to_thread(
        _discover_loggers,
        broadcast_address,
        timeout,
        bind_address,
        port,
    )
