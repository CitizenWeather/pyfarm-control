from __future__ import annotations

import ast
import operator
import re
from typing import Any

_AND_OR_RE = re.compile(r"\b(AND|OR)\b")
_DOTTED_RE = re.compile(r"([a-zA-Z_]\w*)\.([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)")
_BARE_STRING_RE = re.compile(r"==\s*([a-zA-Z_]\w+)")

_SAFE_OPS = {
    ast.Gt: operator.gt,
    ast.Lt: operator.lt,
    ast.GtE: operator.ge,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


class ExpressionError(Exception):
    pass


class SafeExpressionEvaluator:
    """
    Evaluates alert/interlock expressions against a flat context dict.

    Supported syntax:
        "temperature.current > 28 AND stage == fruiting"
        "humidity_rh.current < 0.80 AND stage == fruiting"
        "sensor.co2.flatline_minutes > 10"

    No exec() or eval(). AST walk over a whitelist of node types.
    """

    def evaluate(self, expression: str, context: dict[str, Any]) -> bool:
        flat_ctx = _flatten(context)
        normalised = _normalise(expression)
        try:
            tree = ast.parse(normalised, mode="eval")
        except SyntaxError as e:
            raise ExpressionError(f"Syntax error in '{expression}': {e}") from e
        return bool(_eval_node(tree.body, flat_ctx))


def _normalise(expr: str) -> str:
    expr = _AND_OR_RE.sub(lambda m: m.group(1).lower(), expr)
    expr = _DOTTED_RE.sub(lambda m: m.group(0).replace(".", "__"), expr)
    expr = _BARE_STRING_RE.sub(lambda m: f"== '{m.group(1)}'", expr)
    return expr


def _flatten(d: dict, prefix: str = "") -> dict:
    out: dict = {}
    for k, v in d.items():
        key = f"{prefix}__{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def _eval_node(node: ast.AST, ctx: dict) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise ExpressionError(f"Unknown variable '{node.id.replace('__', '.')}'"
                                   f" (available: {sorted(ctx)})")
        return ctx[node.id]
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, ctx) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v, ctx) for v in node.values)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, ctx)
            op_fn = _SAFE_OPS.get(type(op))
            if op_fn is None:
                raise ExpressionError(f"Unsupported operator {type(op).__name__}")
            if not op_fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand, ctx)
        if isinstance(node.op, ast.Not):
            return not _eval_node(node.operand, ctx)
    raise ExpressionError(f"Unsupported AST node {type(node).__name__}")
