# Deploying PyFarm

How to run pyfarm-control in production on a Raspberry Pi or in Docker.

## Prerequisites

- Python 3.11+ (RPi OS Bookworm ships 3.11)
- `pyfarm-core` and `pyfarm-control` installed (`pip install -e .`)
- `pyfarm-cli` installed for the `pyfarm` command
- A validated GrowSpec YAML (run `pyfarm grow validate grow.yaml` first)

## Option 1 — Raspberry Pi bare metal (recommended)

### 1. Run the setup script (once)

```bash
git clone https://github.com/CitizenWeather/pyfarm-control
cd pyfarm-control
sudo bash scripts/setup.sh
```

This creates the `pyfarm` user, the `/var/lib/pyfarm` data directory, and
installs the systemd service.

### 2. Install pyfarm packages

```bash
# Install from the repo root
pip3 install -e ../pyfarm-core
pip3 install -e .
pip3 install -e ../pyfarm-cli

# Optional sensor hardware libraries
pip3 install adafruit-circuitpython-dht          # DHT22
pip3 install adafruit-circuitpython-mcp3xxx \    # MCP3008 ADC
             adafruit-circuitpython-busdevice
```

### 3. Write your GrowSpec

```bash
sudo cp examples/oyster_fruiting.pyfarm.yaml /etc/pyfarm/grow.yaml
sudo $EDITOR /etc/pyfarm/grow.yaml
```

Validate it first:

```bash
pyfarm grow validate /etc/pyfarm/grow.yaml
```

### 4. Start the service

```bash
sudo systemctl start pyfarm-control
sudo systemctl status pyfarm-control

# Follow logs
sudo journalctl -u pyfarm-control -f
```

### 5. Access the API

```bash
# Live status
curl http://localhost:8765/status

# List all runs
curl http://localhost:8765/runs

# Sensor history for current run
curl "http://localhost:8765/history/sensor-readings?metric=temperature"
```

---

## Option 2 — Docker

### 1. Create `grow.yaml`

Place your GrowSpec at `grow.yaml` in the directory with `docker-compose.yml`.

### 2. Set secrets in `.env`

```bash
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
EOF
```

### 3. Start

```bash
docker-compose up -d
docker-compose logs -f
```

The API is available at `http://localhost:8765/status`.

---

## Wiring sensors and actuators

The GrowSpec declares what actuators exist and on which GPIO pins.  The
runner builds them via `build_actuator()` (see `extensions.py`).

```yaml
actuators:
  misting:
    kind: relay
    gpio: 17
    interlock: "humidity_rh.current < 0.92"
    safety:
      max_on_seconds: 30
      min_off_seconds: 300

  exhaust_fan:
    kind: relay
    gpio: 27
```

For DHT22 sensors, construct them manually in your runner script and pass
them as the `sensors=` list — there is no YAML sensor spec yet:

```python
from pyfarm.control.sensors.dht22 import DHT22TemperatureSensor, DHT22HumiditySensor

sensors = [
    DHT22TemperatureSensor(gpio=4),
    DHT22HumiditySensor(gpio=4),
]
```

See [EXTENSIONS.md](EXTENSIONS.md) for the full sensor/actuator API.

---

## Persistence & history

`SQLiteStore` (`pyfarm.control.persist.SQLiteStore`) persists every tick's
sensor readings and all control events.  Pass it to `ControlRunner` as
`store=`:

```python
from pyfarm.control.persist import SQLiteStore

store = SQLiteStore("/var/lib/pyfarm/pyfarm.db")
runner = ControlRunner(spec, sensors, actuators, store=store, api_port=8765)
```

The CLI `pyfarm grow start` does this automatically when `--db` is given.

### Query historical data

```bash
# CLI summary
pyfarm grow history <run_id> --db /var/lib/pyfarm/pyfarm.db

# CSV export
pyfarm grow export <run_id> --db /var/lib/pyfarm/pyfarm.db --output run.csv

# HTTP API
curl "http://localhost:8765/history/sensor-readings?metric=temperature"
curl "http://localhost:8765/history/events?kind=alert"
```

---

## Monitoring

```bash
# Systemd status
sudo systemctl status pyfarm-control

# Live logs
sudo journalctl -u pyfarm-control -f

# Disk usage of the database (grows ~50 bytes/reading)
du -sh /var/lib/pyfarm/pyfarm.db
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: RPi.GPIO` | Install `RPi.GPIO` or inject a test backend |
| `SensorReadError: DHT22 … no reading` | Adafruit DHT22 sometimes misreads — the runner retries next tick automatically |
| `permission denied /dev/gpiomem` | Add user to `gpio` group: `sudo usermod -aG gpio $USER` |
| `database is locked` | Stop the service, then restart — SQLite only supports one writer |
| Service won't start | Check `journalctl -u pyfarm-control -n 50` for the error |

---

## Updating

```bash
git pull
pip3 install -e .
sudo systemctl restart pyfarm-control
```

For Docker:

```bash
docker-compose down
docker-compose build
docker-compose up -d
```
