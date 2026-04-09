import pytest

from app.pipeline.math_eval import safe_eval_math


def test_addition():
    assert safe_eval_math("2 + 3") == 5


def test_subtraction():
    assert safe_eval_math("10 - 4") == 6


def test_multiplication():
    assert safe_eval_math("3 * 7") == 21


def test_division():
    assert safe_eval_math("15 / 3") == 5.0


def test_operator_precedence():
    assert safe_eval_math("2 + 3 * 4") == 14


def test_parentheses():
    assert safe_eval_math("(2 + 3) * 4") == 20


def test_negative_number():
    assert safe_eval_math("-5 + 3") == -2


def test_floor_division():
    assert safe_eval_math("7 // 2") == 3


def test_modulo():
    assert safe_eval_math("10 % 3") == 1


def test_power():
    assert safe_eval_math("2 ** 3") == 8


def test_float_literal():
    assert safe_eval_math("1.5 + 2.5") == 4.0


def test_complex_expression():
    assert safe_eval_math("(10 + 5) * 2 - 3") == 27


def test_division_by_zero():
    with pytest.raises(ZeroDivisionError):
        safe_eval_math("1 / 0")


def test_reject_variable_name():
    with pytest.raises(ValueError):
        safe_eval_math("x + 1")


def test_reject_function_call():
    with pytest.raises(ValueError):
        safe_eval_math("abs(-5)")


def test_reject_import():
    with pytest.raises((ValueError, SyntaxError)):
        safe_eval_math("__import__('os')")


def test_reject_string():
    with pytest.raises(ValueError):
        safe_eval_math("'hello'")


def test_reject_empty():
    with pytest.raises(ValueError):
        safe_eval_math("")


def test_whitespace_handling():
    assert safe_eval_math("  12 * 13  ") == 156


def test_unary_plus():
    assert safe_eval_math("+5") == 5
