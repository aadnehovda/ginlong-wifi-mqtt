"""Decoder for second-generation Ginlong/Solis WiFi stick reports."""

from __future__ import annotations

import struct
from typing import Any

HEADCODE = 0x68
DATA_LENGTH = 0x59
INVERTER_SERIAL_OFFSET = 15
INVERTER_DATA_OFFSET = 31
INVERTER_VALUES = struct.Struct(">20HL9H")
MIN_FRAME_SIZE = INVERTER_DATA_OFFSET + INVERTER_VALUES.size

FIELD_NAMES = (
    "temp",
    "dc_volts1",
    "dc_volts2",
    "dc_volts3",
    "dc_amps1",
    "dc_amps2",
    "dc_amps3",
    "ac_amps1",
    "ac_amps2",
    "ac_amps3",
    "ac_volts1",
    "ac_volts2",
    "ac_volts3",
    "ac_freq",
    "watt_now",
    "unknown1",
    "fw_slave",
    "fw_master",
    "kwh_yesterday",
    "kwh_day",
    "kwh_total",
    "unknown2",
    "unknown3",
    "unknown4",
    "unknown5",
    "unknown6",
    "unknown7",
    "kwh_month",
    "unknown9",
    "kwh_lastmonth",
)


class DecodeError(ValueError):
    """Raised when a received payload is not a supported inverter report."""


def decode_inverter_data(raw_data: bytes) -> dict[str, Any]:
    """Decode one inverter report while preserving the legacy raw-value schema."""
    if len(raw_data) < 4:
        raise DecodeError(f"frame is too short: {len(raw_data)} bytes")

    headcode, data_length, control_code = struct.unpack_from("!BBH", raw_data)
    if headcode != HEADCODE:
        raise DecodeError(f"unknown headcode 0x{headcode:02x}")
    if data_length != DATA_LENGTH:
        raise DecodeError(f"unknown data length {data_length}")
    if len(raw_data) < MIN_FRAME_SIZE:
        raise DecodeError(
            f"incomplete frame: received {len(raw_data)} bytes, need at least {MIN_FRAME_SIZE}"
        )

    serial_bytes = raw_data[
        INVERTER_SERIAL_OFFSET : INVERTER_SERIAL_OFFSET + 16
    ]
    inverter_serial = serial_bytes.decode("ascii", errors="replace").rstrip("\x00 ")
    values = INVERTER_VALUES.unpack_from(raw_data, INVERTER_DATA_OFFSET)

    status: dict[str, Any] = {
        "raw_length": len(raw_data[INVERTER_SERIAL_OFFSET:]),
        "raw": raw_data.hex(),
        "headcode": headcode,
        "datalength": data_length,
        "ctrlcode": control_code,
        "inverter_serial": inverter_serial,
    }
    status.update(zip(FIELD_NAMES, values, strict=True))
    return status


def decode_hex_string(hex_string: str) -> dict[str, Any]:
    """Decode a hexadecimal report supplied on the command line."""
    try:
        raw_data = bytes.fromhex(hex_string)
    except ValueError as error:
        raise DecodeError(f"invalid hexadecimal input: {error}") from error
    return decode_inverter_data(raw_data)
