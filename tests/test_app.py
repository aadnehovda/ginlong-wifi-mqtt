import argparse
import asyncio

import pytest

import ginlong_wifi_mqtt.app as app
from ginlong_wifi_mqtt.app import (
    Settings,
    build_parser,
    enqueue_latest,
    mqtt_publisher,
    resolve_poll_target,
)
from ginlong_wifi_mqtt.lan_discovery import LoggerAdvertisement


def parse(parser: argparse.ArgumentParser, *arguments: str) -> argparse.Namespace:
    return parser.parse_args(arguments)


def test_serve_command_accepts_modern_options() -> None:
    args = parse(
        build_parser(),
        "serve",
        "--client-id",
        "solis",
        "--listen-port",
        "9999",
        "--mqtt-address",
        "127.0.0.1",
        "--homeassistant",
    )

    assert args.client_id == "solis"
    assert args.listen_port == 9999
    assert args.mqtt_address == "127.0.0.1"
    assert args.homeassistant is True


def test_decode_is_a_separate_command() -> None:
    args = parse(build_parser(), "decode", "6859ffff")

    assert args.command == "decode"
    assert args.hex_report == "6859ffff"


def test_queue_keeps_latest_report_during_mqtt_outage() -> None:
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1)

    enqueue_latest(queue, {"watt_now": 1})
    enqueue_latest(queue, {"watt_now": 2})

    assert queue.get_nowait() == {"watt_now": 2}


@pytest.mark.asyncio
async def test_mqtt_reconnect_republishes_discovery_and_pending_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_published = asyncio.Event()

    class FakeClient:
        def __init__(self) -> None:
            self.connections = 0
            self.failed_state_once = False
            self.published: list[tuple[int, str, bool]] = []

        async def __aenter__(self) -> "FakeClient":
            self.connections += 1
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def publish(
            self,
            topic: str,
            *,
            payload: str,
            qos: int,
            retain: bool,
        ) -> None:
            del payload, qos
            if topic == "ginlong/inverter_test" and not self.failed_state_once:
                self.failed_state_once = True
                raise app.aiomqtt.MqttError("simulated disconnect")
            self.published.append((self.connections, topic, retain))
            if topic == "ginlong/inverter_test":
                state_published.set()

    client = FakeClient()
    monkeypatch.setattr(app.aiomqtt, "Client", lambda **kwargs: client)
    settings = Settings(
        listen_enabled=True,
        listen_address="127.0.0.1",
        listen_port=9999,
        client_id="test",
        mqtt_address="broker",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        homeassistant=True,
        protocol="tcp",
        reconnect_delay=0,
        poll_host=None,
        poll_port=8899,
        logger_serial=None,
        poll_interval=60,
        discover=False,
        logger_mac=None,
        discovery_broadcast="255.255.255.255",
        discovery_bind_address="0.0.0.0",
        discovery_timeout=3,
    )
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1)
    queue.put_nowait({"watt_now": 123})

    task = asyncio.create_task(mqtt_publisher(settings, queue))
    await asyncio.wait_for(state_published.wait(), timeout=1)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert client.connections == 2
    discovery_connections = {
        connection
        for connection, topic, retained in client.published
        if topic.startswith("homeassistant/") and retained
    }
    assert discovery_connections == {1, 2}
    assert client.published[-1] == (2, "ginlong/inverter_test", False)


@pytest.mark.asyncio
async def test_discovery_overrides_static_poll_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_discover_loggers(**kwargs: object) -> list[LoggerAdvertisement]:
        assert kwargs["broadcast_address"] == "192.0.2.255"
        return [
            LoggerAdvertisement(
                ip_address="192.0.2.35",
                mac_address="AA1122334455",
                serial=None,
            )
        ]

    monkeypatch.setattr(app, "discover_loggers", fake_discover_loggers)
    settings = Settings(
        listen_enabled=True,
        listen_address="0.0.0.0",
        listen_port=9999,
        client_id="solis",
        mqtt_address="127.0.0.1",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        homeassistant=True,
        protocol="tcp",
        reconnect_delay=5,
        poll_host="192.0.2.99",
        poll_port=8899,
        logger_serial=123456789,
        poll_interval=60,
        discover=True,
        logger_mac="AA1122334455",
        discovery_broadcast="192.0.2.255",
        discovery_bind_address="0.0.0.0",
        discovery_timeout=3,
    )

    resolved = await resolve_poll_target(settings)

    assert resolved.poll_host == "192.0.2.35"
    assert resolved.logger_serial == 123456789
