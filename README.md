# Ginlong WiFi MQTT Bridge

Receives reports from a second-generation Ginlong/Solis inverter WiFi stick
over TCP or UDP and publishes the decoded state to MQTT.

The bridge can passively accept inverter reports, actively poll compatible
legacy WiFi sticks, or do both. It keeps accepting reports while MQTT is
unavailable, keeps only the latest report in memory, reconnects every five
seconds by default, and republishes retained Home Assistant discovery whenever
a broker connection is established. Inverter state is live telemetry and is
therefore published without MQTT retention.

## Development

Install the locked development environment and run the tests:

```console
uv sync --locked
uv run pytest
```

Decode a captured hexadecimal report without starting network listeners:

```console
uv run ginlong-wifi-mqtt decode 6859...
```

Run the bridge:

```console
uv run ginlong-wifi-mqtt serve \
  --client-id solis \
  --mqtt-address 127.0.0.1 \
  --discover \
  --logger-mac AA1122334455 \
  --poll-host 192.0.2.10 \
  --logger-serial 123456789 \
  --homeassistant
```

Run `uv run ginlong-wifi-mqtt serve --help` for all options.

## Configuration

Options can be supplied on the `serve` command or through environment
variables:

| Setting | Option | Environment variable | Default |
| --- | --- | --- | --- |
| Listen address | `--listen-address` | `GINLONG_LISTEN_ADDRESS` | `0.0.0.0` |
| Listen port | `--listen-port` | `GINLONG_LISTEN_PORT` | `9999` |
| Transport | `--protocol` | `GINLONG_PROTOCOL` | `tcp` |
| Inverter ID | `--client-id` | `GINLONG_CLIENT_ID` | `solis` |
| MQTT broker | `--mqtt-address` | `MQTT_HOST` | `127.0.0.1` |
| MQTT port | `--mqtt-port` | `MQTT_PORT` | `1883` |
| MQTT username | `--mqtt-username` | `MQTT_USERNAME` | unset |
| MQTT password | `--mqtt-password` | `MQTT_PASSWORD` | unset |
| MQTT password file | `--mqtt-password-file` | `MQTT_PASSWORD_FILE` | unset |
| Home Assistant | `--homeassistant` | `HOMEASSISTANT` | disabled |
| Retry delay | `--reconnect-delay` | `MQTT_RECONNECT_DELAY` | `5` |
| Passive listener | `--listen` / `--no-listen` | `GINLONG_LISTEN` | enabled |
| Poll target | `--poll-host` | `GINLONG_POLL_HOST` | unset |
| Poll port | `--poll-port` | `GINLONG_POLL_PORT` | `8899` |
| Logger serial | `--logger-serial` | `GINLONG_LOGGER_SERIAL` | unset |
| Poll interval | `--poll-interval` | `GINLONG_POLL_INTERVAL` | `60` |
| Startup discovery | `--discover` / `--no-discover` | `GINLONG_DISCOVER` | disabled |
| Logger MAC | `--logger-mac` | `GINLONG_LOGGER_MAC` | unset |
| Discovery broadcast | `--discovery-broadcast` | `GINLONG_DISCOVERY_BROADCAST` | `255.255.255.255` |
| Discovery bind address | `--discovery-bind-address` | `GINLONG_DISCOVERY_BIND_ADDRESS` | `0.0.0.0` |
| Discovery timeout | `--discovery-timeout` | `GINLONG_DISCOVERY_TIMEOUT` | `3` |

Use `--mqtt-password-file /run/secrets/<name>` with Docker Swarm secrets
instead of placing a password in task arguments.

The active poller implements the legacy Solarman/Ginlong V4 read-only
information request used by this stick. It is not native Modbus/TCP: port 502
is not exposed, and the newer Solarman V5 Modbus wrapper is not accepted.
Specify `--no-listen` for polling-only operation.

At startup, `--discover` sends the read-only
`WIFIKIT-214028-READ` UDP broadcast to port 48899 and uses the reply to
resolve the logger's current IP address. Use `--logger-mac` to identify the
intended logger if more than one can answer. Some older firmware does not
include its logger serial in the reply, so keep `--logger-serial` configured.
If discovery times out, a configured `--poll-host` is used as a static
fallback.

## Docker Swarm

Build the locked image:

```console
docker build -t ahovda/ginlong-wifi-mqtt:0.2.1 .
```

The included `compose.yml` is an environment-driven host-network deployment.
Copy `.env.example` to `.env`, replace the example logger and node values, and
make the image available to every eligible node. Render the Compose
environment before handing it to Swarm:

```console
cp .env.example .env
docker compose --env-file .env config |
  docker stack deploy --compose-file - solarman-mqtt
```

The WiFi stick sends an update about every six minutes. Configure its secondary
remote server to the reachable address of the selected Docker node, TCP port
`9999`.
