import pytest
from pyfarm.control.engine.evaluator import SafeExpressionEvaluator, ExpressionError

eval = SafeExpressionEvaluator()


def test_simple_gt():
    assert eval.evaluate("temperature.current > 28", {"temperature": {"current": 29.0}})
    assert not eval.evaluate("temperature.current > 28", {"temperature": {"current": 27.0}})


def test_and_expression():
    ctx = {"humidity_rh": {"current": 0.75}, "stage": "fruiting"}
    assert eval.evaluate("humidity_rh.current < 0.80 AND stage == fruiting", ctx)
    ctx2 = {"humidity_rh": {"current": 0.85}, "stage": "fruiting"}
    assert not eval.evaluate("humidity_rh.current < 0.80 AND stage == fruiting", ctx2)


def test_enum_comparison():
    assert eval.evaluate("stage == fruiting", {"stage": "fruiting"})
    assert not eval.evaluate("stage == colonisation", {"stage": "fruiting"})


def test_unknown_variable_raises():
    with pytest.raises(ExpressionError, match="Unknown variable"):
        eval.evaluate("nonexistent > 5", {})


def test_injection_attempt_raises():
    with pytest.raises(ExpressionError):
        eval.evaluate("__import__('os').system('id') == 0", {})
