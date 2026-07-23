import pytest

from ginlong_wifi_mqtt.decoder import DecodeError, decode_hex_string


SAMPLE = (
    "685951b0154d5925154d592581030530303037353030313733323230303620"
    "00fb05db074a0000000000100000000600000000096e000000001384009000"
    "000000002a00aa01a40003d3380000000000030000be75040f003b0000010f"
    "0000000000000000af16"
)

POLLED_SAMPLE = (
    "685951b0154d5925154d592581030530303037353030313733323230303620"
    "01970c670c670000003b003a0000006900000000096b00000000138809e300"
    "000000002a0b7c0276000571660000000000030000be75040f02400000029c"
    "00000000000000003916"
)


def test_decodes_known_inverter_report() -> None:
    status = decode_hex_string(SAMPLE)

    assert status["inverter_serial"] == "000750017322006"
    assert status["temp"] == 251
    assert status["dc_volts1"] == 1499
    assert status["ac_freq"] == 4996
    assert status["watt_now"] == 144
    assert status["kwh_day"] == 420
    assert status["kwh_total"] == 250680
    assert status["raw_length"] == 88


def test_decodes_live_polled_report() -> None:
    status = decode_hex_string(POLLED_SAMPLE)

    assert status["inverter_serial"] == "000750017322006"
    assert status["temp"] == 407
    assert status["dc_volts1"] == 3175
    assert status["watt_now"] == 2531
    assert status["kwh_day"] == 630
    assert status["kwh_total"] == 356710


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("", "too short"),
        ("0059ffff", "unknown headcode"),
        ("6858ffff", "unknown data length"),
        ("6859ffff", "incomplete frame"),
        ("not-hex", "invalid hexadecimal"),
    ],
)
def test_rejects_invalid_reports(payload: str, message: str) -> None:
    with pytest.raises(DecodeError, match=message):
        decode_hex_string(payload)
