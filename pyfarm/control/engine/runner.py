from __future__ import annotations

import asyncio
import math
from datetime import datetime

from pyfarm.core.models import EventKind
from pyfarm.control.spec.schema import GrowSpec
from .context import ControlContext
from .evaluator import SafeExpressionEvaluator
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
      5. Evaluate alert conditions -> maybe fire notifications
      6. Persist context snapshot
      7. Sleep until next tick
    """

    def __init__(
        self,
        spec: GrowSpec,
        sensors: list,
        actuators: dict,
        notifier=None,
        store=None,
        tick_seconds: float = 10.0,
    ):
        self.spec = spec
        self.sensors = sensors
        self.actuators = actuators
        self.notifier = notifier
        self.store = store
        self.tick = tick_seconds
        self.ctx = ControlContext.new(spec)
        self._stage_machine = StageMachine()
        self._evaluator = SafeExpressionEvaluator()
        self._alert_cooldowns: dict[str, datetime] = {}
        self._running = False

    async def run(self) -> None:
        self._running = True
        self.ctx.log(EventKind.SYSTEM, f"ControlRunner started — spec: {self.spec.metadata.name}")
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                self.ctx.log(EventKind.SENSOR_FAILURE, f"Tick error: {e}")
            await asyncio.sleep(self.tick)

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
        stage = self.ctx.current_stage
        disabled = set(stage.controls_disabled)
        for name, actuator_spec in self.spec.actuators.items():
            actuator = self.actuators.get(name)
            if actuator is None:
                continue
            if name in disabled:
                await actuator.off()
                continue
            interlock_clear = True
            if actuator_spec.interlock:
                try:
                    interlock_clear = self._evaluator.evaluate(
                        actuator_spec.interlock, self.ctx.as_flat_dict()
                    )
                except Exception as e:
                    self.ctx.log(EventKind.SYSTEM, f"Interlock eval error for '{name}': {e}")
                    interlock_clear = False
            if interlock_clear:
                await actuator.on()
            else:
                await actuator.off()

        # 5. alerts
        await self._evaluate_alerts()

        # 6. persist
        if self.store:
            await self.store.write_snapshot(self.ctx)

    async def _evaluate_alerts(self) -> None:
        now = datetime.utcnow()
        flat = self.ctx.as_flat_dict()
        for alert in self.spec.alerts:
            try:
                fired = self._evaluator.evaluate(alert.condition, flat)
            except Exception:
                continue
            if not fired:
                continue
            last = self._alert_cooldowns.get(alert.condition)
            if last and (now - last).total_seconds() < alert.cooldown_minutes * 60:
                continue
            self._alert_cooldowns[alert.condition] = now
            self.ctx.log(EventKind.ALERT_FIRED, alert.message, severity=alert.severity)
            if self.notifier:
                await self.notifier.send(alert, alert.message)
