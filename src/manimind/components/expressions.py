"""Compile bounded expression data without parsing source code or TeX.

Only exact built-in int/float, str, dict and list nodes are accepted. The root
has depth one; every node occurrence (including a power's exponent) is counted.
Compiled objects snapshot their inputs and live only as long as their caller
keeps them. Recompile to change the expression or symbol declarations; neither
bindings nor results are cached or persisted.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import math
import operator
import re

import sympy


_MAX_NODES = 64
_MAX_DEPTH = 8
_MAX_CONSTANT = 1e4
_MAX_RESULT = 1e6
_SYMBOL = re.compile(r"[a-z][a-z0-9]{0,7}")
_OPERATIONS: dict[str, tuple[int, int, Callable[..., float]]] = {
    "add": (2, 6, lambda *args: sum(args)),
    "sub": (2, 2, operator.sub),
    "mul": (2, 6, lambda *args: math.prod(args)),
    "div": (2, 2, operator.truediv),
    "pow": (2, 2, math.pow),
    "sin": (1, 1, math.sin),
    "cos": (1, 1, math.cos),
    "sqrt": (1, 1, math.sqrt),
    "abs": (1, 1, abs),
}
_Evaluator = Callable[[dict[str, float]], float]


class ExpressionError(ValueError):
    """An expression or binding violates the data or numerical contract."""


def _valid_symbol(value: object) -> bool:
    return (type(value) is str and 1 <= len(value) <= 8
            and _SYMBOL.fullmatch(value) is not None)


def _finite_float(value: object, where: str) -> float:
    if type(value) not in (int, float):
        raise ExpressionError(f"{where}: expected an int or float, not bool or objects")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ExpressionError(f"{where}: number is outside the finite float range") from exc
    if not math.isfinite(number):
        raise ExpressionError(f"{where}: expected a finite number")
    return number


def _symbolic_operation(op: str, args: tuple[sympy.Expr, ...]) -> sympy.Expr:
    # Keep the tree unevaluated: cancellation must not conceal domain errors.
    if op == "add":
        return sympy.Add(*args, evaluate=False)
    if op == "sub":
        return sympy.Add(args[0], sympy.Mul(sympy.Integer(-1), args[1], evaluate=False),
                         evaluate=False)
    if op == "mul":
        return sympy.Mul(*args, evaluate=False)
    if op == "div":
        return sympy.Mul(args[0], sympy.Pow(args[1], sympy.Integer(-1), evaluate=False),
                         evaluate=False)
    if op == "pow":
        return sympy.Pow(*args, evaluate=False)
    if op == "sqrt":
        return sympy.Pow(args[0], sympy.Rational(1, 2), evaluate=False)
    if op == "sin":
        return sympy.sin(args[0], evaluate=False)
    if op == "cos":
        return sympy.cos(args[0], evaluate=False)
    if op == "abs":
        return sympy.Abs(args[0], evaluate=False)
    raise ExpressionError("Unknown operation")


@dataclass(frozen=True, slots=True)
class CompiledExpression:
    """Immutable output of compile_expression, independent of any renderer."""

    _evaluator: _Evaluator = field(repr=False)
    _expression: sympy.Expr = field(repr=False)
    _symbols: frozenset[str]
    _required_symbols: frozenset[str]

    def evaluate(self, values: dict) -> float:
        """Evaluate finite numeric bindings and return a float in [-1e6, 1e6].

        Only referenced symbols are required. Extra declared bindings are allowed
        but still validated; undeclared keys are rejected. Intermediate results
        must be finite, while the magnitude limit applies to the final result.
        """
        if type(values) is not dict:
            raise ExpressionError("Bindings must be a dict")
        bindings = {}
        for name, value in values.items():
            if type(name) is not str or name not in self._symbols:
                raise ExpressionError("Binding key is not a declared symbol")
            bindings[name] = _finite_float(value, f"Binding {name}")
        missing = self._required_symbols - bindings.keys()
        if missing:
            raise ExpressionError(f"Missing bindings: {', '.join(sorted(missing))}")
        result = self._evaluator(bindings)
        if not math.isfinite(result) or abs(result) > _MAX_RESULT:
            raise ExpressionError("Result must be finite with absolute value <= 1e6")
        return float(result)

    def latex(self) -> str:
        """Print only explicitly constructed SymPy objects, never user TeX."""
        return sympy.latex(self._expression)


def compile_expression(node: object, symbols: set[str]) -> CompiledExpression:
    """Compile a strict expression tree with explicit symbol declarations.

    Nodes are finite numbers of magnitude <= 1e4, declared simple symbol names,
    or exactly {"op": <allowed name>, "args": <list>}. Powers require a literal
    built-in integer exponent in [-4, 4]. Trees have at most 64 nodes and depth 8.
    Numerical domain errors are checked by evaluate, not by symbolic rewriting.
    """
    if type(symbols) is not set or any(not _valid_symbol(name) for name in symbols):
        raise ExpressionError("symbols must be a set of names matching [a-z][a-z0-9]{0,7}")
    declared = frozenset(symbols)
    required: set[str] = set()
    count = 0

    def visit(current: object, depth: int) -> tuple[_Evaluator, sympy.Expr]:
        nonlocal count
        count += 1
        if count > _MAX_NODES:
            raise ExpressionError("Expression exceeds 64 nodes")
        if depth > _MAX_DEPTH:
            raise ExpressionError("Expression exceeds depth 8 (root depth is 1)")
        if type(current) in (int, float):
            number = _finite_float(current, "Constant")
            if abs(number) > _MAX_CONSTANT:
                raise ExpressionError("Constant absolute value must be <= 1e4")
            literal = sympy.Integer(current) if type(current) is int else sympy.Float(current)
            return lambda values: number, literal
        if type(current) is str:
            if not _valid_symbol(current) or current not in declared:
                raise ExpressionError("Expression contains an invalid or undeclared symbol")
            required.add(current)
            return lambda values: values[current], sympy.Symbol(current, real=True)
        if (type(current) is not dict or len(current) != 2
                or any(type(key) is not str for key in current)
                or set(current) != {"op", "args"}):
            raise ExpressionError("Node must be a number, symbol, or exactly an op/args object")
        op, args = current["op"], current["args"]
        if type(op) is not str or op not in _OPERATIONS:
            raise ExpressionError("Unknown operation")
        minimum, maximum, operation = _OPERATIONS[op]
        if type(args) is not list or not minimum <= len(args) <= maximum:
            raise ExpressionError(f"{op}: args must be a list of {minimum}..{maximum} nodes")
        if op == "pow" and (type(args[1]) is not int or not -4 <= args[1] <= 4):
            raise ExpressionError("pow: exponent must be a literal integer in [-4, 4]")
        children = tuple(visit(arg, depth + 1) for arg in args)
        evaluators = tuple(child[0] for child in children)
        expression = _symbolic_operation(op, tuple(child[1] for child in children))

        def evaluate_operation(values: dict[str, float]) -> float:
            operands = tuple(evaluate(values) for evaluate in evaluators)
            try:
                result = operation(*operands)
            except (ArithmeticError, ValueError) as exc:
                raise ExpressionError(f"{op}: undefined or nonfinite result") from exc
            if not math.isfinite(result):
                raise ExpressionError(f"{op}: nonfinite result")
            return float(result)

        return evaluate_operation, expression

    evaluator, expression = visit(node, 1)
    return CompiledExpression(evaluator, expression, declared, frozenset(required))
