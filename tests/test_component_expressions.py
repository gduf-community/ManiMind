import ast
from dataclasses import FrozenInstanceError
from decimal import Decimal
from fractions import Fraction
import inspect
import math

import pytest
import sympy

from manimind.components import expressions
from manimind.components.expressions import (
    CompiledExpression,
    ExpressionError,
    compile_expression,
)


def op(name, *args):
    return {"op": name, "args": list(args)}


@pytest.mark.parametrize("value", [0, -1, 0.25, -0.0, 10000, -10000.0, 1e-320])
def test_literals_return_finite_floats(value):
    expression = compile_expression(value, set())
    assert isinstance(expression, CompiledExpression)
    result = expression.evaluate({})
    assert type(result) is float
    assert math.isfinite(result)
    assert result == float(value)


def test_error_is_a_value_error():
    assert issubclass(ExpressionError, ValueError)


@pytest.mark.parametrize("name,args,expected", [
    ("add", [2, 3, -1], 4),
    ("sub", [2, 3], -1),
    ("mul", [2, 3, -1], -6),
    ("div", [3, 2], 1.5),
    ("pow", [-2, 3], -8),
    ("sin", [math.pi / 2], 1),
    ("cos", [math.pi], -1),
    ("sqrt", [9], 3),
    ("abs", [-2.5], 2.5),
])
def test_all_operators(name, args, expected):
    result = compile_expression(op(name, *args), set()).evaluate({})
    assert type(result) is float
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("name", ["add", "mul"])
@pytest.mark.parametrize("arity", range(2, 7))
def test_variadic_operators_accept_every_allowed_arity(name, arity):
    result = compile_expression(op(name, *([2] * arity)), set()).evaluate({})
    assert result == (2 * arity if name == "add" else 2 ** arity)


@pytest.mark.parametrize("name,arity", [
    (name, arity)
    for name, allowed in {
        "add": range(2, 7), "mul": range(2, 7),
        "sub": (2,), "div": (2,), "pow": (2,),
        "sin": (1,), "cos": (1,), "sqrt": (1,), "abs": (1,),
    }.items()
    for arity in range(9) if arity not in allowed
])
def test_invalid_arities(name, arity):
    with pytest.raises(ExpressionError, match="args"):
        compile_expression(op(name, *([1] * arity)), set())


def test_nested_expression_tracks_changing_parameters_without_caching():
    node = op("add", op("mul", "a", op("pow", "x", 2)), op("sin", "t"))
    expression = compile_expression(node, {"a", "x", "t", "unused"})
    bindings = {"a": 2, "x": 3, "t": 0}
    assert expression.evaluate(bindings) == 18
    bindings.update(a=-1, x=2, t=math.pi / 2, unused=123)
    assert expression.evaluate(bindings) == pytest.approx(-3)
    assert expression.evaluate({"a": 0.5, "x": -4, "t": 0}) == 8
    assert bindings == {"a": -1, "x": 2, "t": math.pi / 2, "unused": 123}


def test_compiled_state_is_an_immutable_snapshot():
    node = op("add", "x", 2)
    symbols = {"x"}
    expression = compile_expression(node, symbols)
    original_latex = expression.latex()
    node["op"] = "div"
    node["args"][:] = [True, 0]
    symbols.clear()
    assert expression.evaluate({"x": 4}) == 6
    assert expression.latex() == original_latex
    with pytest.raises(FrozenInstanceError):
        expression._symbols = frozenset()


@pytest.mark.parametrize("name", ["x", "x0", "abc12345", "alpha1", "pi", "sin"])
def test_names_are_explicit_symbols_not_implicit_constants_or_functions(name):
    expression = compile_expression(name, {name})
    assert expression.evaluate({name: 7}) == 7
    assert expression.latex() == sympy.latex(sympy.Symbol(name, real=True))


@pytest.mark.parametrize("node", ["x", op("sin", "x"), op("mul", 0, "x")])
def test_undeclared_symbols_rejected_at_compile_time(node):
    with pytest.raises(ExpressionError, match="undeclared"):
        compile_expression(node, set())


@pytest.mark.parametrize("node", [
    "x", op("pow", "x", 0), op("sub", "x", "x"), op("mul", 0, "x"),
])
def test_missing_bindings_are_not_hidden_by_simplification(node):
    expression = compile_expression(node, {"x", "unused"})
    with pytest.raises(ExpressionError, match="Missing bindings: x"):
        expression.evaluate({"unused": 1})


@pytest.mark.parametrize("symbols", [None, [], ["x"], ("x",), {"x": 1},
                                      frozenset({"x"}), "x", {1}, {True}, {None}])
def test_symbol_declarations_must_be_an_explicit_set_of_names(symbols):
    with pytest.raises(ExpressionError):
        compile_expression(1, symbols)


@pytest.mark.parametrize("name", [
    "", "X", "abcdefgh9", "1x", "x_y", "x-y", "x.y", "x y", "x\n", " x", "\u03b1",
    "x+1", "sin(x)", "x**2", "1", "float('nan')", "__import__('os').system('id')",
    r"\input{/etc/passwd}", r"\write18{touch injected}", "../secret", "/tmp/data",
    "${HOME}", "x;quit()", "{x}", "x\x00", "x" * 10000,
])
def test_code_tex_paths_and_malformed_symbols_are_rejected(name):
    with pytest.raises(ExpressionError):
        compile_expression(name, {"x"})
    with pytest.raises(ExpressionError):
        compile_expression(1, {name})


@pytest.mark.parametrize("node", [
    True, False, None, [], [1, 2], (1,), 1j, Decimal("1"), Fraction(1, 2),
    sympy.Integer(1), b"x", math.nan, math.inf, -math.inf, 10001, -10001.0, 10 ** 1000,
    {}, {"op": "add"}, {"args": [1, 2]}, {"op": "add", "args": [1, 2], "code": "pass"},
    {"op": "add", "args": [1, 2], "latex": r"\input{bad}"},
    {"op": "add", "args": [1, 2], 1: 2}, {1: "add", "args": [1, 2]},
    {"op": "add", "args": (1, 2)}, {"op": "sin", "args": "x"},
    {"op": "sin", "args": None}, {"op": "sin", "args": {"x": 1}},
    op("eval", 1), op("__import__", "os"), op("log", 1), op("ADD", 1, 2),
    op([], 1), op({}, 1), op(True, 1), op(None, 1),
    op("add", 1, True), op("sin", math.nan), op("abs", math.inf),
])
def test_invalid_nodes_are_expression_errors(node):
    with pytest.raises(ExpressionError):
        compile_expression(node, {"x"})


@pytest.mark.parametrize("exponent", range(-4, 5))
@pytest.mark.parametrize("base", [-2, 2])
def test_every_allowed_literal_power(base, exponent):
    expression = compile_expression(op("pow", base, exponent), set())
    assert expression.evaluate({}) == pytest.approx(base ** exponent)


@pytest.mark.parametrize("exponent", [
    -5, 5, 10000, 10 ** 1000, 2.0, -4.0, 0.5, True, False, math.nan, math.inf,
    "n", "2", op("add", 1, 1), op("sub", 0, 1), None, [], {},
])
def test_power_requires_a_literal_builtin_integer(exponent):
    with pytest.raises(ExpressionError, match="exponent"):
        compile_expression(op("pow", 2, exponent), {"n"})


def test_zero_power_follows_real_math_pow_convention():
    assert compile_expression(op("pow", 0, 0), set()).evaluate({}) == 1.0


@pytest.mark.parametrize("values", [None, [], [("x", 1)], "x=1", (1,)])
def test_bindings_require_a_dict(values):
    with pytest.raises(ExpressionError):
        compile_expression("x", {"x"}).evaluate(values)


@pytest.mark.parametrize("value", [True, False, None, "1", math.nan, math.inf, -math.inf,
                                    1j, [], {}, Decimal("1"), Fraction(1, 2), 10 ** 1000])
def test_every_supplied_binding_is_a_finite_number(value):
    expression = compile_expression("x", {"x", "unused"})
    with pytest.raises(ExpressionError):
        expression.evaluate({"x": value})
    with pytest.raises(ExpressionError):
        expression.evaluate({"x": 1, "unused": value})


@pytest.mark.parametrize("name", ["y", "x+1", r"\input{bad}", 1, None, True])
def test_undeclared_binding_keys_are_rejected_even_when_unused(name):
    with pytest.raises(ExpressionError, match="declared"):
        compile_expression(1, {"x"}).evaluate({name: 2})


@pytest.mark.parametrize("node,values", [
    (op("div", 1, 0), {}), (op("div", 1, -0.0), {}),
    (op("div", "x", "x"), {"x": 0}),
    (op("div", 1, op("sub", "x", "x")), {"x": 2}),
    (op("sqrt", -1), {}), (op("sqrt", "x"), {"x": -1}),
    (op("pow", 0, -1), {}), (op("pow", 0, -4), {}),
    (op("div", 1, 1e-320), {}), (op("pow", 1e-300, -4), {}),
    (op("pow", "x", 4), {"x": 1e308}),
    (op("mul", "x", "x"), {"x": 1e308}),
    (op("add", "x", "x"), {"x": 1e308}),
    (op("sub", "x", "y"), {"x": 1e308, "y": -1e308}),
    (op("mul", 0, op("div", 1, 0)), {}),
    (op("mul", 0, op("sqrt", -1)), {}),
    (op("pow", op("div", 1, 0), 0), {}),
    (op("mul", 0, op("mul", "x", "x")), {"x": 1e308}),
])
def test_domain_and_nonfinite_results_raise_expression_error(node, values):
    expression = compile_expression(node, {"x", "y"})
    assert isinstance(expression.latex(), str)
    with pytest.raises(ExpressionError):
        expression.evaluate(values)


@pytest.mark.parametrize("sign", [-1, 1])
def test_result_magnitude_boundary(sign):
    expression = compile_expression("x", {"x"})
    assert expression.evaluate({"x": sign * 1e6}) == sign * 1e6
    with pytest.raises(ExpressionError, match="1e6"):
        expression.evaluate({"x": sign * math.nextafter(1e6, math.inf)})
    with pytest.raises(ExpressionError, match="1e6"):
        compile_expression(op("mul", sign * 10000, 10000), set()).evaluate({})


def test_large_finite_inputs_and_intermediates_can_produce_bounded_results():
    expression = compile_expression(op("div", op("mul", 10000, 10000), 1000), set())
    assert expression.evaluate({}) == 100000
    assert compile_expression(op("div", "x", "x"), {"x"}).evaluate({"x": 1e308}) == 1
    assert compile_expression(op("sin", "x"), {"x"}).evaluate({"x": 1e308}) == math.sin(1e308)


def test_depth_limit_counts_the_root_and_leaves():
    node = 1
    for _ in range(7):
        node = op("abs", node)
    assert compile_expression(node, set()).evaluate({}) == 1
    with pytest.raises(ExpressionError, match="depth 8"):
        compile_expression(op("abs", node), set())


def test_size_limit_counts_repeated_subtrees_as_node_occurrences():
    branch = op("add", *([1] * 6))  # Seven nodes, deliberately shared below.
    wide = op("add", *([branch] * 6))  # 43 nodes.
    node = op("add", wide, branch, branch, op("add", *([1] * 5)))  # 64 nodes.
    assert compile_expression(node, set()).evaluate({}) == 53
    node["args"][-1] = branch  # 65 nodes, still only four levels deep.
    with pytest.raises(ExpressionError, match="64 nodes"):
        compile_expression(node, set())


def test_cyclic_data_is_rejected_without_recursion_error():
    node = op("abs")
    node["args"].append(node)
    with pytest.raises(ExpressionError, match="depth"):
        compile_expression(node, set())


@pytest.mark.parametrize("node,expected", [
    (op("add", "x", 2), "x + 2"),
    (op("sub", "x", 2), "x - 2"),
    (op("mul", "x", "y"), "x y"),
    (op("div", "x", "y"), r"\frac{x}{y}"),
    (op("pow", "x", 2), "x^{2}"),
    (op("sin", "x"), r"\sin{\left(x \right)}"),
    (op("cos", "x"), r"\cos{\left(x \right)}"),
    (op("sqrt", "x"), r"\sqrt{x}"),
    (op("abs", "x"), r"\left|{x}\right|"),
    (op("pow", op("add", "x", 2), 2), r"\left(x + 2\right)^{2}"),
    (op("div", "x", "x"), r"\frac{x}{x}"),
    (op("div", "x", op("add", "x", 2)), r"\frac{x}{x + 2}"),
])
def test_safe_latex_is_printed_by_sympy_with_correct_grouping(node, expected):
    expression = compile_expression(node, {"x", "y"})
    assert expression.latex() == expected
    assert not any(command in expression.latex() for command in (
        r"\input", r"\include", r"\write", r"\open", r"\read", r"\catcode", r"\def",
    ))


def test_symbolic_tree_and_numeric_closure_agree_without_string_parsing():
    node = op("div", op("sub", op("pow", "x", 2), op("mul", 2, "x")),
              op("sqrt", op("add", op("abs", "y"), 1)))
    expression = compile_expression(node, {"x", "y"})
    x, y = sympy.Symbol("x", real=True), sympy.Symbol("y", real=True)
    expected = (x ** 2 - 2 * x) / sympy.sqrt(sympy.Abs(y) + 1)
    assert sympy.simplify(expression._expression - expected) == 0
    for x_value, y_value in [(0, 0), (2, -3), (-4, 8), (0.5, -0.25)]:
        result = float(expected.subs({x: x_value, y: y_value}))
        assert expression.evaluate({"x": x_value, "y": y_value}) == pytest.approx(result)


def test_objects_cannot_trigger_numeric_or_sympy_conversion_hooks():
    class Hostile:
        def __float__(self):
            raise AssertionError("Numeric conversion hook called")

        def _sympy_(self):
            raise AssertionError("Symbolic conversion hook called")

    value = Hostile()
    for node in (value, op("add", 1, value)):
        with pytest.raises(ExpressionError):
            compile_expression(node, set())
    with pytest.raises(ExpressionError):
        compile_expression("x", {"x"}).evaluate({"x": value})


def test_builtin_subclasses_cannot_override_the_data_contract():
    class Number(float):
        def __float__(self):
            raise AssertionError("Numeric conversion hook called")

    class Text(str):
        pass

    class Object(dict):
        def items(self):
            raise AssertionError("Mapping hook called")

    class Array(list):
        pass

    class Symbols(set):
        pass

    for node in (Number(1), Text("x"), Object(op("abs", 1)),
                 {"op": "abs", "args": Array([1])}, op(Text("abs"), 1),
                 {Text("op"): "abs", "args": [1]}):
        with pytest.raises(ExpressionError):
            compile_expression(node, {"x"})
    for symbols in (Symbols({"x"}), {Text("x")}):
        with pytest.raises(ExpressionError):
            compile_expression(1, symbols)
    for values in (Object(x=1), {Text("x"): 1}, {"x": Number(1)}):
        with pytest.raises(ExpressionError):
            compile_expression("x", {"x"}).evaluate(values)


def test_module_does_not_use_source_parsers_or_import_renderers():
    tree = ast.parse(inspect.getsource(expressions))
    forbidden = {"eval", "exec", "sympify", "parse_expr", "lambdify"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (node.func.id if isinstance(node.func, ast.Name)
                    else node.func.attr if isinstance(node.func, ast.Attribute) else None)
            assert name not in forbidden
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in {"manim", "manimlib"}
                       for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in {"manim", "manimlib"}
