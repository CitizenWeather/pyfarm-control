from __future__ import annotations

import ast
import math
import re

from .schema import GrowSpec


class SpecValidationError(Exception):
    pass


# Re-export so loader only needs to import from here
SpecLoadError = SpecValidationError


def validate_spec(spec: GrowSpec) -> None:
    """Run all cross-field validations. Raises SpecValidationError on failure."""
    _validate_stage_names_unique(spec)
    _validate_vpd_consistency(spec)
    _validate_alert_expressions(spec)
    _validate_actuator_interlocks(spec)
    _validate_alert_channels(spec)


def _validate_stage_names_unique(spec: GrowSpec) -> None:
    names = [s.name for s in spec.stages]
    if len(names) != len(set(names)):
        raise SpecValidationError("Stage names must be unique")


def _validate_vpd_consistency(spec: GrowSpec) -> None:
    for stage in spec.stages:
        if stage.vpd is None:
            continue
        temp = stage.setpoints.temperature
        rh = stage.setpoints.humidity_rh
        if temp is None or rh is None:
            continue
        computed = _compute_vpd(temp.target, rh.target)
        delta = abs(computed - stage.vpd.target)
        # Allow some slack beyond the stated tolerance for rounding
        if delta > stage.vpd.tolerance + 0.15:
            raise SpecValidationError(
                f"Stage '{stage.name}': VPD target {stage.vpd.target} kPa is inconsistent "
                f"with temp={temp.target}°C + RH={rh.target} "
                f"(computed VPD ≈ {computed:.2f} kPa, tolerance={stage.vpd.tolerance} kPa)"
            )


def _compute_vpd(temp_c: float, rh: float) -> float:
    svp = 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))
    return svp * (1.0 - rh)


def _validate_alert_expressions(spec: GrowSpec) -> None:
    for alert in spec.alerts:
        _check_expression_syntax(alert.condition, f"alert condition '{alert.condition}'")


def _validate_actuator_interlocks(spec: GrowSpec) -> None:
    for name, actuator in spec.actuators.items():
        if actuator.interlock:
            _check_expression_syntax(actuator.interlock, f"actuator '{name}' interlock")


_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or,
    ast.Compare, ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.UnaryOp, ast.USub, ast.Not,
    ast.Constant, ast.Name, ast.Attribute,
)


def _check_expression_syntax(expr: str, label: str) -> None:
    normalised = _normalise_for_ast(expr)
    try:
        tree = ast.parse(normalised, mode="eval")
    except SyntaxError as e:
        raise SpecValidationError(f"Syntax error in {label}: {e}") from e
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise SpecValidationError(
                f"Unsafe AST node {type(node).__name__} in {label}"
            )


def _normalise_for_ast(expr: str) -> str:
    expr = expr.replace(" AND ", " and ").replace(" OR ", " or ")
    # dotted names -> valid Python identifiers
    expr = re.sub(r"([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)", r"\1__\2", expr)
    # bare enum values after == -> quoted strings so ast can parse them
    expr = re.sub(r"==\s*([a-zA-Z_]\w+)", r"== '\1'", expr)
    return expr


def _validate_alert_channels(spec: GrowSpec) -> None:
    defined = set(spec.notifications.channels.keys())
    if not defined:
        return  # no channels configured; skip (allows minimal specs)
    for alert in spec.alerts:
        for ch in alert.channels:
            if ch not in defined:
                raise SpecValidationError(
                    f"Alert references channel '{ch}' not defined in notifications.channels"
                )
