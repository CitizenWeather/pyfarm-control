"""Controllers decide what an actuator should do, given the live context.

A controller's :meth:`compute` returns a command (bool or 0..1 float). The
runner is responsible for interlocks and safety limits, so controllers can
stay simple.
"""

from __future__ import annotations

import abc

from pyfarm.control.actuators.base import Command
from pyfarm.control.engine.context import ControlContext

# Map a metric name to its setpoint attribute on ``Stage.setpoints``.
_SETPOINT_ATTR = {
    "temperature": "temperature",
    "humidity_rh": "humidity_rh",
    "co2_ppm": "co2_ppm",
}


class Controller(abc.ABC):
    #: The metric this controller acts on (e.g. ``temperature``). ``None`` for
    #: controllers like scheduling that aren't tied to a measured setpoint.
    metric: str | None = None

    @abc.abstractmethod
    def compute(self, ctx: ControlContext) -> Command:
        raise NotImplementedError

    def setpoint(self, ctx: ControlContext):
        """Return the current stage's setpoint object for :attr:`metric`."""
        if self.metric is None:
            return None
        attr = _SETPOINT_ATTR.get(self.metric)
        if attr is None:
            return None
        return getattr(ctx.current_stage.setpoints, attr, None)
