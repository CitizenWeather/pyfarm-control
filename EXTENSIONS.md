# Extending PyFarm

Guide to adding custom hardware drivers to pyfarm-control.

## Architecture

Hardware is injected into `ControlRunner` at start-up — the engine never
imports `RPi.GPIO`, `adafruit_dht`, or anything hardware-specific directly.
This keeps the engine testable and replay-safe on any machine.

```
ControlRunner(
    spec     = load_spec("grow.yaml"),
    sensors  = [DHT22TemperatureSensor(gpio=4), ...],   # ← your hardware
    actuators = build_actuator_map(spec),               # ← GPIO relays etc.
    store    = SQLiteStore("pyfarm.db"),                 # ← persistence
    ...
)
```

## Custom Actuator

Subclass `pyfarm.control.actuators.base.Actuator` and implement `apply()`.
A *command* is `bool` for on/off or `float` in `[0, 1]` for PWM.

```python
from pyfarm.control.actuators.base import Actuator, Command

class ModbusRelay(Actuator):
    """On/off relay via Modbus TCP."""

    def __init__(self, name: str, host: str, register: int) -> None:
        super().__init__(name)
        self._host = host
        self._register = register

    async def apply(self, command: Command) -> None:
        from pymodbus.client import ModbusTcpClient
        level = self.is_on(command)
        client = ModbusTcpClient(self._host)
        client.write_register(self._register, int(level))
        client.close()
```

Pass it directly when building the runner — no factory registration needed:

```python
actuators = {"exhaust_fan": ModbusRelay("exhaust_fan", "192.168.1.10", register=5)}
runner = ControlRunner(spec, sensors, actuators)
```

### Injectable backend pattern

For testability, prefer separating the I/O callable from the actuator, like
the built-in `RelayActuator` does:

```python
from typing import Callable
RelayBackend = Callable[[int, bool], None]

class RelayActuator(Actuator):
    def __init__(self, name, gpio, *, backend: RelayBackend | None = None):
        super().__init__(name)
        self.gpio = gpio
        self._backend = backend  # None → resolve lazily from RPi.GPIO

    async def apply(self, command: Command) -> None:
        level = self.is_on(command)
        (self._backend or self._default_backend())(self.gpio, level)
```

In tests, pass a recording lambda; in production, pass `None`.

## Custom Sensor

Subclass `pyfarm.control.sensors.base.Sensor` and implement `async read()`.
Raise `SensorReadError` on failure — the runner degrades gracefully.

```python
from datetime import datetime, timezone
from pyfarm.control.engine.context import SensorReading
from pyfarm.control.engine.errors import SensorReadError
from pyfarm.control.sensors.base import Sensor

class MQTTSensor(Sensor):
    """Reads the latest value from an MQTT topic."""

    def __init__(self, metric: str, unit: str, topic: str) -> None:
        super().__init__(metric, unit=unit)
        self._topic = topic
        self._last: float | None = None

    async def read(self) -> SensorReading:
        # Subscribe once externally and update self._last via callback.
        if self._last is None:
            raise SensorReadError(f"No data on {self._topic} yet")
        return SensorReading(
            value=self._last,
            unit=self.unit,
            timestamp=datetime.now(timezone.utc),
        )
```

### DHT22 sensor (built-in)

`pyfarm.control.sensors.dht22` ships two sensors for the DHT22:

```python
from pyfarm.control.sensors.dht22 import DHT22TemperatureSensor, DHT22HumiditySensor

sensors = [
    DHT22TemperatureSensor(gpio=4),
    DHT22HumiditySensor(gpio=4),
]
```

Requires `pip install adafruit-circuitpython-dht`.

### Analog sensor (built-in)

`pyfarm.control.sensors.analog.AnalogSensor` takes an injectable backend:

```python
from pyfarm.control.sensors.analog import AnalogSensor

def mcp3008_ch0() -> float:
    # Return raw [0, 1] from your ADC
    ...

co2 = AnalogSensor("co2_ppm", "ppm", backend=mcp3008_ch0, scale=5000)
```

## Custom Notification Channel

Subclass `pyfarm.control.alerts.channels.base.Channel`:

```python
from pyfarm.control.alerts.channels.base import Channel, Notification
import httpx

class DiscordChannel(Channel):
    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    async def send(self, notification: Notification) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(self._url, json={"content": notification.message})
```

Register it via the `channels` dict passed to `Notifier`:

```python
from pyfarm.control.alerts.channels.base import Notifier

channels = {"discord": DiscordChannel("https://discord.com/api/webhooks/...")}
notifier = Notifier(channels)
alert_evaluator = AlertEvaluator(notifier)
```

## Custom Persistence

`SQLiteStore` in `pyfarm.control.persist` implements
`pyfarm.control.engine.store.SnapshotStore`.  To write your own:

```python
from pyfarm.control.engine.store import SnapshotStore
from pyfarm.control.engine.context import ControlContext

class InfluxStore(SnapshotStore):
    async def write_snapshot(self, ctx: ControlContext) -> None:
        # Push readings to InfluxDB
        ...

    def restore(self, ctx: ControlContext) -> bool:
        # Rehydrate stage position — return False if no snapshot
        return False
```

## Testing Without Hardware

Use `FakeSensor` from `pyfarm.control.sensors.fake` and `LoggingActuator`
from `pyfarm.control.actuators.logging` — they're the same interfaces, no
GPIO required:

```python
from pyfarm.control.sensors.fake import FakeSensor
from pyfarm.control.actuators.logging import LoggingActuator
from pyfarm.control.alerts.channels.base import RecordingChannel, Notifier
from pyfarm.control.alerts.evaluator import AlertEvaluator

sensors = [FakeSensor("temperature", 22.0, unit="celsius")]
actuators = {"misting": LoggingActuator("misting")}
recording = RecordingChannel()
evaluator = AlertEvaluator(Notifier({"push": recording}))

runner = ControlRunner(spec, sensors, actuators, alert_evaluator=evaluator)
```

Or use the CSV replay mode for deterministic integration tests:

```bash
pyfarm grow replay grow.yaml data/sensor_log.csv --metrics temperature,humidity_rh,co2_ppm
```
