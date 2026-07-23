import json

from ginlong_wifi_mqtt.discovery import SENSORS, discovery_messages


def test_discovery_topics_are_unique_and_reference_state_topic() -> None:
    messages = list(discovery_messages("solis", "ginlong/inverter_solis"))
    topics = [topic for topic, _ in messages]

    assert len(messages) == len(SENSORS) == 20
    assert len(set(topics)) == len(topics)

    for topic, encoded_payload in messages:
        payload = json.loads(encoded_payload)
        assert topic.startswith(
            "homeassistant/sensor/ginlong_inverter_solis/"
        )
        assert payload["state_topic"] == "ginlong/inverter_solis"
        assert payload["unique_id"].startswith("ginlong_inverter_solis_")


def test_energy_scaling_matches_raw_decoder_values() -> None:
    payloads = {
        topic.rsplit("/", 2)[-2]: json.loads(payload)
        for topic, payload in discovery_messages(
            "solis", "ginlong/inverter_solis"
        )
    }

    assert payloads["kwh_day"]["value_template"].endswith("/ 100.0 }}")
    assert payloads["kwh_total"]["value_template"].endswith("/ 10.0 }}")
