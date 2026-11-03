"""Source/data regressions only: no renderer, TeX compiler, speech or approval."""

import ast
from pathlib import Path
import re


SOURCE = Path(__file__).resolve().parents[1] / "examples/projectile_formula_motion_full.py"


def scene_method(name):
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    scene = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "FullFormulaLesson")
    return next(node for node in scene.body if isinstance(node, ast.FunctionDef) and node.name == name)


def test_vertical_authored_selectors_are_unambiguous_and_nonoverlapping():
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "vertical_steps")
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)
    steps = namespace["vertical_steps"]()
    assert len(steps) == 4
    for latex, tokens in steps:
        selected = []
        for identity, selector in tokens.items():
            literal, occurrence = (selector, None) if isinstance(selector, str) else selector
            matches = list(re.finditer(re.escape(literal), latex))
            if occurrence is None:
                assert len(matches) == 1, (identity, literal, latex)
                occurrence = 0
            assert occurrence < len(matches), (identity, literal, latex)
            span = matches[occurrence].span()
            assert all(span[1] <= old[0] or old[1] <= span[0] for old in selected), (identity, latex)
            selected.append(span)
    assert steps[-1][0] == "y_1(t)=y_2(t)"


def test_horizontal_distance_does_not_select_the_x_in_vx():
    formulas = [node for node in ast.walk(scene_method("_horizontal"))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_formula" and node.args and isinstance(node.args[0], ast.Constant)]
    assert not any(node.args[0].value == "x=v_x{t}" for node in formulas)
    initial = next(node for node in formulas if node.args[0].value == "{x}=v_x{t}")
    assert ast.literal_eval(initial.args[1])["distance"] == "{x}"


def test_final_substitution_carries_only_small_t_then_expands_at_its_destination():
    transports = [node for node in ast.walk(scene_method("_conclusion"))
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_merge"]
    assert len(transports) == 1
    carry = transports[0]
    assert ast.literal_eval(carry.args[3])["time"] == ("final_time", "time")
    assert "root" not in ast.literal_eval(carry.args[3])
    assert ast.unparse(next(item.value for item in carry.keywords if item.arg == "paths")) == "{'time': carry_path}"
    for transport in transports:
        mapping = ast.literal_eval(transport.args[3])
        assert all(mapping[key] == ("final_range", key) for key in ("range", "eq", "speed"))
        assert ast.literal_eval(next(item.value for item in transport.keywords if item.arg == "consume")) == ("final_range",)
    assert 108.5 + .2 + ast.literal_eval(carry.args[4]) + .6 < 110
    expansion = scene_method("_expand_time_here")
    calls = [node.func.id for node in ast.walk(expansion)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    assert "GrowFromPoint" in calls and "ReplacementTransform" not in calls
    assert "get_center" in ast.unparse(expansion)


def test_flight_geometry_retains_glyphs_instead_of_scene_restructured_wrappers():
    assert 'tuple(animation.mobject.family_members_with_points())' in ast.unparse(scene_method("_merge"))
    assert 'glyph.get_points()' in ast.unparse(scene_method("_geometry"))


def test_no_new_process_mark_ids_and_portable_landing_is_called_once():
    source = ast.parse(SOURCE.read_text(encoding="utf-8"))
    old = ast.parse((SOURCE.parents[1] / "outputs/sol61-visual-first-20261024-v1/candidate.py").read_text())
    def marks(tree):
        return [ast.literal_eval(node.args[0]) for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "mark"]
    authored = marks(source)
    landing = {"vertical_equation_linked", "ground_condition_applied", "landing_time_derived"}
    assert set(authored) == set(marks(old)) - landing
    assert len(authored) == len(set(authored))
    calls = [node for node in ast.walk(scene_method("construct"))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "play_landing_derivation"]
    assert len(calls) == 1
    assert ast.literal_eval(next(item.value for item in calls[0].keywords if item.arg == "start")) == 38
