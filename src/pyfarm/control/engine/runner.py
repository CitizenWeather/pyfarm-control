"""The main control loop. Intentionally boring.

Each tick:
  1. Read sensors -> update context (degrade gracefully on failure)
  2. Compute derived metrics (VPD, dew point)
  3. Evaluate stage exit condition -> maybe advance stage
  4. For each actuator: interlock + controls_disabled + controller + safety -> command
  5. Evaluate alert conditions -> maybe fire notifications
  6. Persist context snapshot
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable, Iterable, Mapping

from pyfarm.control.actuators.base import Actuator
from pyfarm.control.controllers.base import Controller
from pyfarm.control.engine.context import ActuatorState, ControlContext
from pyfarm.control.engine.derived import compute_dew_point, compute_vpd
from pyfarm.control.engine.errors import ReplayExhausted, SensorReadError
from pyfarm.control.engine.safety import SafetyGuard
from pyfarm.control.engine.stage_machine import StageMachine
from pyfarm.control.engine.store import NullStore, SnapshotStore
from pyfarm.control.exceptions import SpecValidationError
from pyfarm.control.expr.evaluator import SafeExpressionEvaluator
from pyfarm.control.sensors.base import Sensor
from pyfarm.control.spec.schema import GrowSpec

if TYPE_CHECKING:
    from pyfarm.control.alerts.evaluator import AlertEvaluator


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ControlRunner:
    def __init__(
        self,
        spec: GrowSpec,
        sensors: Iterable[Sensor],
        actuators: Mapping[str, Actuator],
        *,
        controllers: Mapping[str, Controller] | None = None,
        alert_evaluator: AlertEvaluator | None = None,
        stage_machine: StageMachine | None = None,
        safety_guard: SafetyGuard | None = None,
        store: SnapshotStore | None = None,
        tick_seconds: float = 10.0,
        clock: Callable[[], datetime] = _now,
        context: ControlContext | None = None,
        api_port: int | None = None,
    ) -> None:
        self.spec = spec
        self.sensors = list(sensors)
        self.actuators = dict(actuators)
        self.controllers = dict(controllers or {})
        self.stage_machine = stage_machine or StageMachine(clock=clock)
        self.safety_guard = safety_guard or SafetyGuard(clock=clock)
        self.alert_evaluator = alert_evaluator
        self.store = store or NullStore()
        self.tick_seconds = tick_seconds
        self._clock = clock
        self._expr = SafeExpressionEvaluator()
        self.ctx = context or ControlContext.new(spec)
        self.store.restore(self.ctx)
        self.api_port = api_port
        self._running = False
        self._api_task: asyncio.Task | None = None
        # Seed states as "off for a long time" so safety min-off-time limits
        # don't block the very first command after start-up.
        cold_start = self._clock() - timedelta(days=1)
        for name in self.actuators:
            self.ctx.actuator_states.setdefault(
                name, ActuatorState(name=name, last_changed=cold_start)
            )

    # -- public loops -----------------------------------------------------

    async def run(self) -> None:
        """Run until :meth:`stop` is called, ticking every ``tick_seconds``.

        Optionally starts a FastAPI ``/status`` endpoint on ``api_port`` as a
        background task.
        """
        self._running = True
        if self.api_port is not None:
            self._api_task = asyncio.create_task(self._serve_api())
        try:
            while self._running:
                await self.tick()
                await asyncio.sleep(self.tick_seconds)
        finally:
            if self._api_task is not None and not self._api_task.done():
                self._api_task.cancel()
                await asyncio.gather(self._api_task, return_exceptions=True)

    def stop(self) -> None:
        """Signal the :meth:`run` loop to exit after the current tick."""
        self._running = False

    async def _serve_api(self) -> None:
        import uvicorn
        from pyfarm.control.api import make_app

        from pyfarm.control.persist import SQLiteStore
        store = self.store if isinstance(self.store, SQLiteStore) else None
        app = make_app(self.ctx, store=store)
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.api_port, log_level="warning"
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def run_until_exhausted(self, max_ticks: int = 100_000) -> int:
        """Tick until a replay sensor runs out of data (or ``max_ticks``).

        Returns the number of completed ticks. This is the entry point for
        replay/CI: drive the engine over a recorded dataset, then inspect the
        actuator logs and event history.
        """
        ticks = 0
        while ticks < max_ticks:
            try:
                await self.tick()
            except ReplayExhausted:
                break
            ticks += 1
        return ticks

    # -- one tick ---------------------------------------------------------

    async def tick(self) -> None:
        await self._read_sensors()
        self._compute_derived()
        await self.stage_machine.evaluate(self.ctx)
        await self._drive_actuators()
        if self.alert_evaluator is not None:
            await self.alert_evaluator.evaluate(self.ctx)
        await self.store.write_snapshot(self.ctx)

    async def _read_sensors(self) -> None:
        for sensor in self.sensors:
            try:
                reading = await sensor.read()
            except ReplayExhausted:
                raise
            except SensorReadError as exc:
                self.ctx.log_event(
                    "sensor_failure",
                    f"Sensor {sensor.metric!r} read failed: {exc}; "
                    "holding last known value",
                    metric=sensor.metric,
                )
                continue
            self.ctx.record_reading(sensor.metric, reading)

    def _compute_derived(self) -> None:
        temp = self.ctx.readings.get("temperature")
        rh = self.ctx.readings.get("humidity_rh")
        if temp is not None and rh is not None:
            self.ctx.derived["vpd"] = compute_vpd(temp.value, rh.value)
            self.ctx.derived["dew_point"] = compute_dew_point(temp.value, rh.value)

    async def _drive_actuators(self) -> None:
        stage = self.ctx.current_stage
        for name, actuator in self.actuators.items():
            state = self.ctx.actuator_states[name]

            if name in stage.controls_disabled:
                await self._command(actuator, state, False, reason="disabled this stage")
                continue

            if not self._interlock_clear(name):
                await self._command(actuator, state, False, reason="interlock open")
                continue

            controller = self.controllers.get(name)
            desired = controller.compute(self.ctx) if controller is not None else False
            desired_on = Actuator.is_on(desired)

            safety = self.spec.actuators[name].safety if name in self.spec.actuators else None
            if safety is not None:
                allowed_on, reason = self.safety_guard.constrain(desired_on, state, safety)
                if allowed_on != desired_on:
                    await self._command(actuator, state, False, reason=reason)
                    continue

            command = desired if desired_on else False
            await self._command(actuator, state, command)

    def _interlock_clear(self, name: str) -> bool:
        spec = self.spec.actuators.get(name)
        if spec is None or spec.interlock is None:
            return True
        context = self.ctx.as_flat_dict()
        # Provide numeric defaults for target/tolerance so interlocks that
        # reference them (e.g. "temperature.current < target - tolerance") remain
        # evaluable even when no controller is attached. A controller overrides these.
        context.setdefault("target", 0.0)
        context.setdefault("tolerance", 0.0)
        controller = self.controllers.get(name)
        if controller is not None and controller.metric is not None:
            setpoint = controller.setpoint(self.ctx)
            if setpoint is not None:
                context["target"] = setpoint.target
                context["tolerance"] = getattr(setpoint, "tolerance", 0.0) or 0.0
        try:
            return bool(self._expr.evaluate(spec.interlock, context))
        except SpecValidationError:
            # Interlock references something not yet available — fail safe (open).
            return False

    async def _command(self, actuator, state: ActuatorState, command, *, reason: str | None = None) -> None:
        on = Actuator.is_on(command)
        await actuator.apply(command)
        if on != state.on:
            state.last_changed = self._clock()
            self.ctx.log_event(
                "actuator",
                f"{actuator.name} -> {'ON' if on else 'OFF'}"
                + (f" ({reason})" if reason else ""),
                actuator=actuator.name,
                on=on,
            )
        state.on = on
        state.command = command
