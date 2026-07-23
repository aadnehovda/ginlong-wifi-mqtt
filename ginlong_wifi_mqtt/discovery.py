"""Home Assistant MQTT discovery payload generation."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Sensor:
    key: str
    name: str
    device_class: str
    state_class: str
    unit: str
    value_template: str


SENSORS = (
    Sensor("watt_now", "Current Power", "power", "measurement", "W", "{{ value_json.watt_now }}"),
    Sensor("temp", "Temperature", "temperature", "measurement", "°C", "{{ (value_json.temp / 10.0) | round(1) }}"),
    Sensor("dc_volts1", "DC1 Voltage", "voltage", "measurement", "V", "{{ value_json.dc_volts1 / 10.0 }}"),
    Sensor("dc_amps1", "DC1 Current", "current", "measurement", "A", "{{ value_json.dc_amps1 / 10.0 }}"),
    Sensor("dc_volts2", "DC2 Voltage", "voltage", "measurement", "V", "{{ value_json.dc_volts2 / 10.0 }}"),
    Sensor("dc_amps2", "DC2 Current", "current", "measurement", "A", "{{ value_json.dc_amps2 / 10.0 }}"),
    Sensor("dc_volts3", "DC3 Voltage", "voltage", "measurement", "V", "{{ value_json.dc_volts3 / 10.0 }}"),
    Sensor("dc_amps3", "DC3 Current", "current", "measurement", "A", "{{ value_json.dc_amps3 / 10.0 }}"),
    Sensor("ac_volts1", "AC1 Voltage", "voltage", "measurement", "V", "{{ value_json.ac_volts1 / 10.0 }}"),
    Sensor("ac_amps1", "AC1 Current", "current", "measurement", "A", "{{ value_json.ac_amps1 / 10.0 }}"),
    Sensor("ac_volts2", "AC2 Voltage", "voltage", "measurement", "V", "{{ value_json.ac_volts2 / 10.0 }}"),
    Sensor("ac_amps2", "AC2 Current", "current", "measurement", "A", "{{ value_json.ac_amps2 / 10.0 }}"),
    Sensor("ac_volts3", "AC3 Voltage", "voltage", "measurement", "V", "{{ value_json.ac_volts3 / 10.0 }}"),
    Sensor("ac_amps3", "AC3 Current", "current", "measurement", "A", "{{ value_json.ac_amps3 / 10.0 }}"),
    Sensor("ac_freq", "AC Frequency", "frequency", "measurement", "Hz", "{{ value_json.ac_freq / 100.0 }}"),
    Sensor("kwh_day", "Daily Yield", "energy", "total_increasing", "kWh", "{{ value_json.kwh_day / 100.0 }}"),
    Sensor("kwh_yesterday", "Yesterday's Yield", "energy", "total_increasing", "kWh", "{{ value_json.kwh_yesterday / 100.0 }}"),
    Sensor("kwh_total", "Total Energy", "energy", "total_increasing", "kWh", "{{ value_json.kwh_total / 10.0 }}"),
    Sensor("kwh_month", "This Month's Yield", "energy", "total_increasing", "kWh", "{{ value_json.kwh_month }}"),
    Sensor("kwh_lastmonth", "Last Month's Yield", "energy", "total_increasing", "kWh", "{{ value_json.kwh_lastmonth }}"),
)


def discovery_messages(
    client_id: str, state_topic: str
) -> Iterator[tuple[str, str]]:
    """Yield retained Home Assistant discovery topic/payload pairs."""
    device_id = f"ginlong_inverter_{client_id}"
    device = {
        "identifiers": [device_id],
        "manufacturer": "Ginlong",
        "name": f"Ginlong Inverter {client_id}",
    }

    for sensor in SENSORS:
        topic = f"homeassistant/sensor/{device_id}/{sensor.key}/config"
        payload = {
            "device_class": sensor.device_class,
            "device": device,
            "expire_after": 3600,
            "name": sensor.name,
            "state_class": sensor.state_class,
            "state_topic": state_topic,
            "unique_id": f"{device_id}_{sensor.key}",
            "unit_of_measurement": sensor.unit,
            "value_template": sensor.value_template,
        }
        yield topic, json.dumps(payload, separators=(",", ":"), sort_keys=True)
