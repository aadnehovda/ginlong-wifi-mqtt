import pytest

from ginlong_wifi_mqtt.lan_discovery import (
    LoggerAdvertisement,
    normalize_mac_address,
    parse_discovery_response,
    select_logger,
)


def test_parses_old_firmware_response_without_serial() -> None:
    advertisement = parse_discovery_response(
        b"192.0.2.35,AA1122334455,"
    )

    assert advertisement == LoggerAdvertisement(
        ip_address="192.0.2.35",
        mac_address="AA1122334455",
        serial=None,
    )


def test_parses_response_with_serial() -> None:
    advertisement = parse_discovery_response(
        b"192.0.2.40,aa:bb:cc:dd:ee:ff,123456789"
    )

    assert advertisement.mac_address == "AABBCCDDEEFF"
    assert advertisement.serial == 123456789


def test_selects_logger_by_mac_when_serial_is_not_reported() -> None:
    selected = select_logger(
        [
            LoggerAdvertisement("192.0.2.35", "AA1122334455", None),
            LoggerAdvertisement("192.0.2.40", "AABBCCDDEEFF", 123),
        ],
        mac_address="aa:11:22:33:44:55",
        serial=123456789,
    )

    assert selected is not None
    assert selected.ip_address == "192.0.2.35"


@pytest.mark.parametrize("value", ["", "xyz", "AA112233445Z"])
def test_rejects_invalid_mac(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_mac_address(value)
