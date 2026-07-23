"""Async TCP/UDP to MQTT bridge."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

import aiomqtt

from .decoder import DecodeError, decode_hex_string, decode_inverter_data
from .discovery import discovery_messages
from .lan_discovery import (
    discover_loggers,
    normalize_mac_address,
    select_logger,
)
from .v4 import request_v4_status

LOGGER = logging.getLogger("ginlong_wifi_mqtt")
MAX_FRAME_SIZE = 4096


@dataclass(frozen=True)
class Settings:
    listen_enabled: bool
    listen_address: str
    listen_port: int
    client_id: str
    mqtt_address: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    homeassistant: bool
    protocol: str
    reconnect_delay: float
    poll_host: str | None
    poll_port: int
    logger_serial: int | None
    poll_interval: float
    discover: bool
    logger_mac: str | None
    discovery_broadcast: str
    discovery_bind_address: str
    discovery_timeout: float

    @property
    def mqtt_topic(self) -> str:
        return f"ginlong/inverter_{self.client_id}"


def environment_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish Ginlong/Solis WiFi stick reports to MQTT."
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default=os.getenv("LOG_LEVEL", "INFO"),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="receive and publish inverter reports")
    serve.add_argument(
        "--listen",
        action=argparse.BooleanOptionalAction,
        default=environment_flag("GINLONG_LISTEN", True),
        help="enable the passive TCP/UDP listener",
    )
    serve.add_argument(
        "--listen-address",
        default=os.getenv("GINLONG_LISTEN_ADDRESS", "0.0.0.0"),
        help="address on which to receive inverter reports (default: %(default)s)",
    )
    serve.add_argument(
        "--listen-port",
        type=int,
        default=int(os.getenv("GINLONG_LISTEN_PORT", "9999")),
        help="port on which to receive inverter reports (default: %(default)s)",
    )
    serve.add_argument(
        "--client-id",
        default=os.getenv("GINLONG_CLIENT_ID", "solis"),
        help="identifier used in MQTT topics (default: %(default)s)",
    )
    serve.add_argument(
        "--mqtt-address",
        default=os.getenv("MQTT_HOST", "127.0.0.1"),
        help="MQTT broker hostname or address (default: %(default)s)",
    )
    serve.add_argument(
        "--mqtt-port",
        type=int,
        default=int(os.getenv("MQTT_PORT", "1883")),
        help="MQTT broker port (default: %(default)s)",
    )
    serve.add_argument("--mqtt-username", default=os.getenv("MQTT_USERNAME"))
    credentials = serve.add_mutually_exclusive_group()
    credentials.add_argument("--mqtt-password", default=os.getenv("MQTT_PASSWORD"))
    credentials.add_argument(
        "--mqtt-password-file",
        type=Path,
        default=(
            Path(os.environ["MQTT_PASSWORD_FILE"])
            if "MQTT_PASSWORD_FILE" in os.environ
            else None
        ),
        help="read the MQTT password from a file, such as a Swarm secret",
    )
    serve.add_argument(
        "--homeassistant",
        action=argparse.BooleanOptionalAction,
        default=environment_flag("HOMEASSISTANT"),
        help="publish Home Assistant discovery on every MQTT connection",
    )
    serve.add_argument(
        "--protocol",
        choices=("tcp", "udp"),
        default=os.getenv("GINLONG_PROTOCOL", "tcp"),
        help="inverter transport protocol (default: %(default)s)",
    )
    serve.add_argument(
        "--reconnect-delay",
        type=float,
        default=float(os.getenv("MQTT_RECONNECT_DELAY", "5")),
        help="seconds between MQTT reconnection attempts (default: %(default)s)",
    )
    serve.add_argument(
        "--poll-host",
        default=os.getenv("GINLONG_POLL_HOST"),
        help="actively poll a legacy V4 logger at this address",
    )
    serve.add_argument(
        "--poll-port",
        type=int,
        default=int(os.getenv("GINLONG_POLL_PORT", "8899")),
        help="legacy V4 logger port (default: %(default)s)",
    )
    serve.add_argument(
        "--logger-serial",
        type=int,
        default=(
            int(os.environ["GINLONG_LOGGER_SERIAL"])
            if "GINLONG_LOGGER_SERIAL" in os.environ
            else None
        ),
        help="numeric WiFi logger serial required for active polling",
    )
    serve.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("GINLONG_POLL_INTERVAL", "60")),
        help="seconds between active status polls (default: %(default)s)",
    )
    serve.add_argument(
        "--discover",
        action=argparse.BooleanOptionalAction,
        default=environment_flag("GINLONG_DISCOVER"),
        help="discover the active poll target by UDP broadcast at startup",
    )
    serve.add_argument(
        "--logger-mac",
        default=os.getenv("GINLONG_LOGGER_MAC"),
        help="select this logger MAC when LAN discovery finds multiple devices",
    )
    serve.add_argument(
        "--discovery-broadcast",
        default=os.getenv("GINLONG_DISCOVERY_BROADCAST", "255.255.255.255"),
        help="broadcast address used for logger discovery (default: %(default)s)",
    )
    serve.add_argument(
        "--discovery-bind-address",
        default=os.getenv("GINLONG_DISCOVERY_BIND_ADDRESS", "0.0.0.0"),
        help="local address from which to send discovery (default: %(default)s)",
    )
    serve.add_argument(
        "--discovery-timeout",
        type=float,
        default=float(os.getenv("GINLONG_DISCOVERY_TIMEOUT", "3")),
        help="seconds to collect discovery responses (default: %(default)s)",
    )
    decode = commands.add_parser(
        "decode", help="decode one hexadecimal inverter report"
    )
    decode.add_argument("hex_report", metavar="HEX")
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    password = args.mqtt_password
    if args.mqtt_password_file is not None:
        password = args.mqtt_password_file.read_text(encoding="utf-8").strip()
    if args.poll_host and args.logger_serial is None and not args.discover:
        raise ValueError("--logger-serial is required with --poll-host")
    if not args.listen and not args.poll_host and not args.discover:
        raise ValueError(
            "enable --listen, configure --poll-host or --discover, or both"
        )
    if args.poll_interval <= 0:
        raise ValueError("--poll-interval must be greater than zero")
    if args.discovery_timeout <= 0:
        raise ValueError("--discovery-timeout must be greater than zero")
    logger_mac = (
        normalize_mac_address(args.logger_mac) if args.logger_mac else None
    )

    return Settings(
        listen_enabled=args.listen,
        listen_address=args.listen_address,
        listen_port=args.listen_port,
        client_id=args.client_id,
        mqtt_address=args.mqtt_address,
        mqtt_port=args.mqtt_port,
        mqtt_username=args.mqtt_username or None,
        mqtt_password=password or None,
        homeassistant=args.homeassistant,
        protocol=args.protocol,
        reconnect_delay=args.reconnect_delay,
        poll_host=args.poll_host,
        poll_port=args.poll_port,
        logger_serial=args.logger_serial,
        poll_interval=args.poll_interval,
        discover=args.discover,
        logger_mac=logger_mac,
        discovery_broadcast=args.discovery_broadcast,
        discovery_bind_address=args.discovery_bind_address,
        discovery_timeout=args.discovery_timeout,
    )


def enqueue_latest(
    queue: asyncio.Queue[dict[str, object]], status: dict[str, object]
) -> None:
    """Keep only the latest report while MQTT is unavailable."""
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(status)


async def process_payload(
    raw_data: bytes,
    queue: asyncio.Queue[dict[str, object]],
    peer: object,
) -> None:
    try:
        status = decode_inverter_data(raw_data)
    except DecodeError as error:
        LOGGER.warning("Rejected report from %s: %s", peer, error)
        return

    LOGGER.info(
        "Received report from %s: inverter=%s power=%sW bytes=%d",
        peer,
        status["inverter_serial"],
        status["watt_now"],
        len(raw_data),
    )
    enqueue_latest(queue, status)


async def handle_tcp_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    queue: asyncio.Queue[dict[str, object]],
) -> None:
    peer = writer.get_extra_info("peername")
    raw_data = bytearray()
    try:
        while len(raw_data) < MAX_FRAME_SIZE:
            timeout = 10 if not raw_data else 1
            try:
                chunk = await asyncio.wait_for(
                    reader.read(MAX_FRAME_SIZE - len(raw_data)), timeout
                )
            except TimeoutError:
                break
            if not chunk:
                break
            raw_data.extend(chunk)

            # Known reports are data-length + 14 bytes including framing/trailer.
            if len(raw_data) >= 2 and len(raw_data) >= raw_data[1] + 14:
                break

        if raw_data:
            await process_payload(bytes(raw_data), queue, peer)
    except Exception:
        LOGGER.exception("Unhandled TCP client error from %s", peer)
    finally:
        writer.close()
        await writer.wait_closed()


class InverterDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        self.queue = queue

    def datagram_received(self, data: bytes, addr: object) -> None:
        asyncio.create_task(process_payload(data, self.queue, addr))

    def error_received(self, exc: Exception) -> None:
        LOGGER.warning("UDP receive error: %s", exc)


async def poll_v4_logger(
    settings: Settings,
    queue: asyncio.Queue[dict[str, object]],
) -> None:
    assert settings.poll_host is not None
    assert settings.logger_serial is not None

    while True:
        started = asyncio.get_running_loop().time()
        try:
            raw_data = await request_v4_status(
                settings.poll_host,
                settings.poll_port,
                settings.logger_serial,
            )
            await process_payload(
                raw_data,
                queue,
                f"poll {settings.poll_host}:{settings.poll_port}",
            )
        except (OSError, TimeoutError, asyncio.IncompleteReadError) as error:
            LOGGER.warning(
                "Legacy V4 poll of %s:%d failed: %s",
                settings.poll_host,
                settings.poll_port,
                error,
            )

        elapsed = asyncio.get_running_loop().time() - started
        await asyncio.sleep(max(0, settings.poll_interval - elapsed))


async def resolve_poll_target(settings: Settings) -> Settings:
    if not settings.discover:
        return settings

    LOGGER.info(
        "Discovering WiFi loggers via UDP broadcast %s:48899",
        settings.discovery_broadcast,
    )
    try:
        advertisements = await discover_loggers(
            broadcast_address=settings.discovery_broadcast,
            bind_address=settings.discovery_bind_address,
            timeout=settings.discovery_timeout,
        )
        selected = select_logger(
            advertisements,
            mac_address=settings.logger_mac,
            serial=settings.logger_serial,
        )
    except (OSError, ValueError) as error:
        LOGGER.warning("WiFi logger discovery failed: %s", error)
        selected = None

    if selected is not None:
        logger_serial = selected.serial or settings.logger_serial
        if logger_serial is None:
            raise ValueError(
                "discovered logger did not report a serial; configure "
                "--logger-serial"
            )
        LOGGER.info(
            "Discovered WiFi logger ip=%s mac=%s serial=%s",
            selected.ip_address,
            selected.mac_address,
            selected.serial if selected.serial is not None else "not reported",
        )
        if selected.serial is None:
            LOGGER.info("Using configured logger serial %d", logger_serial)
        return replace(
            settings,
            poll_host=selected.ip_address,
            logger_serial=logger_serial,
        )

    if settings.poll_host is not None and settings.logger_serial is not None:
        LOGGER.warning(
            "No matching logger discovered; using static poll target %s:%d",
            settings.poll_host,
            settings.poll_port,
        )
        return settings

    raise ValueError(
        "no matching logger discovered and no usable static poll target exists"
    )


async def publish_discovery(
    client: aiomqtt.Client, settings: Settings
) -> None:
    count = 0
    for topic, payload in discovery_messages(
        settings.client_id, settings.mqtt_topic
    ):
        await client.publish(topic, payload=payload, qos=1, retain=True)
        count += 1
    LOGGER.info("Published %d retained Home Assistant discovery topics", count)


async def mqtt_publisher(
    settings: Settings,
    queue: asyncio.Queue[dict[str, object]],
) -> None:
    client = aiomqtt.Client(
        hostname=settings.mqtt_address,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
    )
    pending: dict[str, object] | None = None

    while True:
        try:
            async with client:
                LOGGER.info(
                    "Connected to MQTT broker %s:%d",
                    settings.mqtt_address,
                    settings.mqtt_port,
                )
                if settings.homeassistant:
                    await publish_discovery(client, settings)

                while True:
                    if pending is None:
                        pending = await queue.get()
                    await client.publish(
                        settings.mqtt_topic,
                        payload=json.dumps(pending, separators=(",", ":")),
                        qos=1,
                        retain=False,
                    )
                    LOGGER.info(
                        "Published inverter state to %s",
                        settings.mqtt_topic,
                    )
                    pending = None
        except aiomqtt.MqttError as error:
            LOGGER.warning(
                "MQTT connection failed or was lost: %s; retrying in %.1fs",
                error,
                settings.reconnect_delay,
            )
            await asyncio.sleep(settings.reconnect_delay)


async def run_listener(
    settings: Settings,
    queue: asyncio.Queue[dict[str, object]],
) -> None:
    if settings.protocol == "tcp":
        server = await asyncio.start_server(
            lambda reader, writer: handle_tcp_client(reader, writer, queue),
            settings.listen_address,
            settings.listen_port,
        )
        LOGGER.info(
            "Listening on TCP %s:%d",
            settings.listen_address,
            settings.listen_port,
        )
        async with server:
            await server.serve_forever()

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: InverterDatagramProtocol(queue),
        local_addr=(settings.listen_address, settings.listen_port),
    )
    LOGGER.info(
        "Listening on UDP %s:%d",
        settings.listen_address,
        settings.listen_port,
    )
    try:
        await asyncio.Future()
    finally:
        transport.close()


async def run_bridge(settings: Settings) -> None:
    settings = await resolve_poll_target(settings)
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1)
    tasks = [
        asyncio.create_task(
            mqtt_publisher(settings, queue), name="mqtt-publisher"
        )
    ]
    if settings.listen_enabled:
        tasks.append(
            asyncio.create_task(
                run_listener(settings, queue), name="inverter-listener"
            )
        )
    if settings.poll_host:
        tasks.append(
            asyncio.create_task(
                poll_v4_logger(settings, queue), name="legacy-v4-poller"
            )
        )

    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def cli() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        if args.command == "decode":
            status = decode_hex_string(args.hex_report)
            print(json.dumps(status, indent=2, sort_keys=True))
            return
        settings = settings_from_args(args)
        asyncio.run(run_bridge(settings))
    except (DecodeError, ValueError) as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        LOGGER.info("Stopped")
