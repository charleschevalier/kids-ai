"""Safe math expression evaluator using AST parsing.

Only allows basic arithmetic operations on numeric literals.
No access to builtins, variables, or function calls.
"""

from __future__ import annotations

import ast
import json
import logging
import operator
from typing import Union

logger = logging.getLogger(__name__)

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

Number = Union[int, float]


def safe_eval_math(expr: str) -> Number:
    """Safely evaluate a math expression.

    Supports: +, -, *, /, //, %, **, parentheses, and numeric literals.
    Raises ValueError for anything else.
    """
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression: {expr!r}") from e
    return _eval_node(tree.body)


def _eval_node(node: ast.expr) -> Number:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
        return op_func(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return +_eval_node(node.operand)
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def execute_calculate_tool(arguments_json: str) -> str:
    """Parse calculate tool arguments and safely evaluate the math expression.

    This is the tool executor for the 'calculate' function in the LLM tool calling API.
    It takes JSON arguments containing a math expression and returns the result as a string.
    """
    try:
        args = json.loads(arguments_json)
        expression = args.get("expression", "")
        result = safe_eval_math(expression)
        # Return integer if result is a whole number
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)
    except (json.JSONDecodeError, ValueError, ZeroDivisionError) as exc:
        logger.warning("Calculate tool error: %s", exc)
        return f"Error: {exc}"
