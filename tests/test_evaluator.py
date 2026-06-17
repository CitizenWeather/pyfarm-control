import pytest
from pyfarm.control.expr.evaluator import SafeExpressionEvaluator
from pyfarm.control.exceptions import SpecValidationError

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


def test_unknown_dotted_variable_raises():
    # A dotted path that can't be resolved raises SpecValidationError at runtime.
    with pytest.raises(SpecValidationError):
        eval.evaluate("nonexistent.current > 5", {})


def test_bare_unknown_name_is_treated_as_string_literal():
    # Bare names (e.g. enum literals like 'fruiting') return their own name as
    # a fallback, so they work in equality comparisons against string context values.
    assert not eval.evaluate("stage == unknown_stage", {"stage": "fruiting"})


def test_injection_attempt_raises():
    with pytest.raises(SpecValidationError):
        eval.evaluate("__import__('os').system('id') == 0", {})


def test_validate_catches_unknown_bare_name():
    # validate() is the spec-load-time check; it rejects bare names not in available_vars.
    with pytest.raises(SpecValidationError, match="unknown variable"):
        eval.validate("nonexistent > 5", {"temperature.current", "stage"})
