# pyfarm-control

The control engine for `pyfarm` GrowSpecs. It reads a validated spec (from
[`pyfarm-core`](../pyfarm-core)), reads sensors, decides what actuators do, and
emits events and alerts. Nothing else.

This package contributes into the shared `pyfarm.*` [PEP 420 namespace] — it
ships `pyfarm.control.engine`, `pyfarm.control.controllers`,
`pyfarm.control.actuators`, `pyfarm.control.sensors` and `pyfarm.control.alerts`
alongside `pyfarm.control.spec`/`pyfarm.control.expr` from `pyfarm-core`.

## What's inside

- **`engine`** — `ControlContext` (live state, snapshot-able), `ControlRunner`
  (the tick loop), `StageMachine` (biology-driven stage transitions),
  `SafetyGuard` (min-off / max-on limits), derived metrics (VPD, dew point) and
  a JSON snapshot store for crash recovery.
- **`controllers`** — `HysteresisController` (bang-bang with deadband),
  `PidController`, `ScheduleController` (photoperiod + duty cycle).
- **`actuators`** — `LoggingActuator` (records what it *would* have done),
  `RelayActuator`, `PwmActuator`, `MqttActuator`. Hardware/network backends are
  injected, so everything imports without `RPi.GPIO` or `paho-mqtt`.
- **`sensors`** — `ReplaySensor`/`replay_sensors_from_csv`, `FakeSensor`, and
  hardware drivers `DHT22TemperatureSensor`/`DHT22HumiditySensor` (gpio),
  `AnalogSensor` (injectable ADC backend).
- **`alerts`** — `AlertEvaluator` (cooldown-aware, reuses the core
  `SafeExpressionEvaluator`) and ntfy/telegram/webhook channels.
- **`persist`** — `SQLiteStore` (full run history: every sensor reading, event,
  and actuator state) implements `SnapshotStore` for crash recovery + audit.

## Quick start

```bash
# Validate a spec
pyfarm grow validate grow.yaml

# Run against hardware (persists to SQLite, exposes API)
pyfarm grow start grow.yaml --api-port 8765 --db pyfarm.db

# Live status
curl http://localhost:8765/status

# Query history (if --api-port is set)
curl "http://localhost:8765/history/sensor-readings?metric=temperature"
curl http://localhost:8765/runs

# Past run summary / export
pyfarm grow history <run_id> --db pyfarm.db
pyfarm grow export <run_id> --db pyfarm.db --output run.csv
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for systemd and Docker guides.
See [EXTENSIONS.md](EXTENSIONS.md) to add custom sensors, actuators, and channels.

## Replay mode

Because the runner takes sensors and actuators as injected dependencies, the
exact same engine runs against recorded data:

```python
runner = ControlRunner(
    spec,
    sensors=[ReplaySensor("temperature", temps), ...],
    actuators={"misting": LoggingActuator("misting"), ...},
    controllers={"misting": HysteresisController("humidity_rh", "raise"), ...},
    alert_evaluator=AlertEvaluator(notifier),
)
ticks = asyncio.run(runner.run_until_exhausted())
# inspect misting.transitions -> "would have fired misting at ..."
```

This is the contributor onramp, the demo, and the deterministic integration
test harness all at once (see `tests/control/engine/test_integration_replay.py`).

## Development

```bash
pip install -e ".[dev]"   # also needs pyfarm-core installed (sibling repo)
python -m pytest
```

[PEP 420 namespace]: https://peps.python.org/pep-0420/
