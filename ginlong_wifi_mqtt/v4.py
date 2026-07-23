"""Legacy Solarman/Ginlong V4 status polling."""

from __future__ import annotations

import asyncio

V4_REQUEST_HEADER = bytes.fromhex("680241b1")
V4_REQUEST_COMMAND = bytes.fromhex("0100")
V4_END_CODE = 0x16
MAX_LOGGER_SERIAL = 0xFFFFFFFF


def create_v4_status_request(logger_serial: int) -> bytes:
    """Build the legacy read-only information request used on TCP port 8899."""
    if not 0 <= logger_serial <= MAX_LOGGER_SERIAL:
        raise ValueError("logger serial must fit in an unsigned 32-bit integer")

    encoded_serial = logger_serial.to_bytes(4, byteorder="little")
    frame = bytearray(
        V4_REQUEST_HEADER
        + encoded_serial
        + encoded_serial
        + V4_REQUEST_COMMAND
        + b"\x00"
        + bytes((V4_END_CODE,))
    )
    frame[-2] = sum(frame[1:-2]) & 0xFF
    return bytes(frame)


async def request_v4_status(
    host: str,
    port: int,
    logger_serial: int,
    timeout: float = 10,
) -> bytes:
    """Request one status frame from a legacy logger."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout
    )
    try:
        writer.write(create_v4_status_request(logger_serial))
        await asyncio.wait_for(writer.drain(), timeout)

        header = await asyncio.wait_for(reader.readexactly(2), timeout)
        expected_size = header[1] + 14
        remainder = await asyncio.wait_for(
            reader.readexactly(expected_size - len(header)), timeout
        )
        return header + remainder
    finally:
        writer.close()
        await writer.wait_closed()
