from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone

from pyfarm.core.models import EventKind, ActuatorState
from pyfarm.observability.event_bus import EventBus, EventSink
from pyfarm.control.spec.schema import GrowSpec
from .context import ControlContext
from .evaluator import ExpressionError, SafeExpressionEvaluator
from .stage_machine import StageMachine


def _compute_vpd(temp_c: float, rh: float) -> float:
    svp = 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))
    return svp * (1.0 - rh)


class ControlRunner:
    """
    Main loop. Intentionally boring.

    Each tick:
      1. Read sensors -> update context
      2. Compute derived metrics (VPD etc)
      3. Evaluate stage exit condition -> maybe advance stage
      4. For each actuator: evaluate interlock -> command on/off
      5. Evaluate alert conditions -> log events
      6. Drain the event bus -> fan out to sinks (notifications etc.)
      7. Persist context snapshot
      8. Sleep until next tick
    """

    def __init__(
        self,
        spec: GrowSpec,
        sensors: list,
        actuators: dict,
        notifier: EventSink | None = None,
        store=None,
        tick_seconds: float = 10.0,
        api_port: int | None = None,
        sinks: list[EventSink] | None = None,
    ):
        self.spec = spec
        self.sensors = sensors
        self.actuators = actuators
        self.notifier = notifier
        self.store = store
        self.tick = tick_seconds
        self.api_port = api_port
        self.ctx = ControlContext.new(spec)
        self._stage_machine = StageMachine()
        self._evaluator = SafeExpressionEvaluator()
        self._alert_cooldowns: dict[str, datetime] = {}
        self._running = False
        self._api_task: asyncio.Task | None = None

        # Event spine: producers emit via ctx.log; sinks consume on drain().
        self._bus = EventBus()
        self.ctx.bus = self._bus
        if notifier is not None:
            self._bus.subscribe(notifier)
        for sink in sinks or []:
            self._bus.subscribe(sink)

    async def run(self) -> None:
        self._running = True
        self.ctx.log(EventKind.SYSTEM, f"ControlRunner started — spec: {self.spec.metadata.name}")
        if self.api_port and (self._api_task is None or self._api_task.done()):
            self._api_task = asyncio.create_task(self._serve_api())
        try:
            while self._running:
                try:
                    await self._tick()
                except ExpressionError as e:
                    self.ctx.log(EventKind.SYSTEM, f"Expression evaluation error in tick: {e}")
                except (OSError, RuntimeError) as e:
                    self.ctx.log(EventKind.SENSOR_FAILURE, f"Sensor/actuator error: {e}")
                except Exception as e:
                    self.ctx.log(EventKind.SENSOR_FAILURE, f"Unexpected tick error: {type(e).__name__}: {e}")
                await asyncio.sleep(self.tick)
        finally:
            if self._api_task and not self._api_task.done():
                self._api_task.cancel()
                await asyncio.gather(self._api_task, return_exceptions=True)

    async def _serve_api(self) -> None:
        import uvicorn
        from pyfarm.control.api import make_app
        app = make_app(self.ctx)
        config = uvicorn.Config(app, host="127.0.0.1", port=self.api_port, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()

    def stop(self) -> None:
        self._running = False

    async def _tick(self) -> None:
        # 1. read sensors
        for sensor in self.sensors:
            reading = await sensor.read()
            self.ctx.readings[sensor.metric] = reading

        # 2. derive VPD
        temp = self.ctx.readings.get("temperature")
        rh = self.ctx.readings.get("humidity_rh")
        if temp and rh:
            self.ctx.derived["vpd"] = _compute_vpd(temp.value, rh.value)

        # 3. stage transitions
        await self._stage_machine.evaluate(self.ctx)

        # 4. actuators
        now = datetime.now(timezone.utc)
        flat = self.ctx.as_flat_dict()
        stage = self.ctx.current_stage
        disabled = set(stage.controls_disabled)
        for name, actuator_spec in self.spec.actuators.items():
            actuator = self.actuators.get(name)
            if actuator is None:
                continue
            if name in disabled:
                await self._set_actuator(name, actuator, False, now)
                continue
            interlock_clear = True
            if actuator_spec.interlock:
                try:
                    interlock_clear = self._evaluator.evaluate(actuator_spec.interlock, flat)
                except ExpressionError as e:
                    self.ctx.log(EventKind.SYSTEM, f"Interlock eval error for '{name}': {e}")
                    interlock_clear = False
            should_be_on = interlock_clear
            # Safety overrides
            prev = self.ctx.actuator_states.get(name)
            safety = actuator_spec.safety
            if safety and prev and prev.last_toggled_at:
                on_seconds_limit = None
                if safety.max_on_seconds is not None:
                    on_seconds_limit = safety.max_on_seconds
                elif safety.max_on_minutes is not None:
                    on_seconds_limit = safety.max_on_minutes * 60
                elapsed = (now - prev.last_toggled_at).total_seconds()
                if should_be_on and prev.state and on_seconds_limit is not None and elapsed > on_seconds_limit:
                    self.ctx.log(EventKind.SYSTEM, f"Safety: '{name}' max-on exceeded ({elapsed:.0f}s), forcing off")
                    should_be_on = False
                if should_be_on and not prev.state and safety.min_off_seconds and elapsed < safety.min_off_seconds:
                    self.ctx.log(EventKind.SYSTEM, f"Safety: '{name}' min-off not met ({elapsed:.0f}s), holding off")
                    should_be_on = False
            await self._set_actuator(name, actuator, should_be_on, now)

        # 5. alerts
        await self._evaluate_alerts(flat)

        # 6. fan out buffered events to sinks (notifications etc.)
        await self._bus.drain()

        # 7. persist
        if self.store:
            await self.store.write_snapshot(self.ctx)

    async def _set_actuator(self, name: str, actuator, state: bool, now: datetime) -> None:
        prev = self.ctx.actuator_states.get(name)
        toggled = prev is None or prev.state != state
        if state:
            await actuator.on()
        else:
            await actuator.off()
        toggled_at = now if toggled else prev.last_toggled_at
        self.ctx.actuator_states[name] = ActuatorState(
            name=name, state=state, timestamp=now, last_toggled_at=toggled_at
        )

    async def _evaluate_alerts(self, flat: dict) -> None:
        now = datetime.now(timezone.utc)
        for alert in self.spec.alerts:
            try:
                fired = self._evaluator.evaluate(alert.condition, flat)
            except ExpressionError as e:
                self.ctx.log(EventKind.SYSTEM, f"Alert evaluation error: {e}")
                continue
            if not fired:
                continue
            last = self._alert_cooldowns.get(alert.condition)
            if last and (now - last).total_seconds() < alert.cooldown_minutes * 60:
                continue
            self._alert_cooldowns[alert.condition] = now
            # Notification flows event -> bus -> NotifierSink, not an inline call.
            # channels carries the alert's target channels for the sink to route on.
            self.ctx.log(
                EventKind.ALERT_FIRED,
                alert.message,
                severity=alert.severity,
                channels=alert.channels,
            )
