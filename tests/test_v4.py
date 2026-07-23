import pytest

from ginlong_wifi_mqtt.v4 import create_v4_status_request


def test_builds_observed_legacy_status_request() -> None:
    request = create_v4_status_request(123456789)

    assert request.hex() == "680241b115cd5b0715cd5b0701007d16"


@pytest.mark.parametrize("serial", [-1, 0x1_0000_0000])
def test_rejects_out_of_range_logger_serial(serial: int) -> None:
    with pytest.raises(ValueError, match="unsigned 32-bit"):
        create_v4_status_request(serial)
