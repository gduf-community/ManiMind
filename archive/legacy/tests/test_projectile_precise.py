"""Terminology adapter tests without importing Manim or private runtime files."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_display_terms_are_explicit_and_do_not_change_motion():
    tree = ast.parse((ROOT / "examples/projectile_precise.py").read_text())
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "DISPLAY_TERMS" for t in node.targets))
    terms = ast.literal_eval(assignment.value)
    assert terms["横速改变了什么？"] == "水平速度改变了什么？"
    assert terms["横向初速度"] == "水平速度"
    assert all("横速" not in value and "横向" not in value for value in terms.values())
    scene = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assert [ast.unparse(base) for base in scene.bases] == ["PacedLesson"]
    assert {node.name for node in scene.body if isinstance(node, ast.FunctionDef)} == {"cn"}


def test_exact_term_adapter_leaves_other_text_untouched():
    tree = ast.parse((ROOT / "examples/projectile_precise.py").read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "DISPLAY_TERMS" for t in node.targets)]
    nodes += [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "display_term"]
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "terminology", "exec"), namespace)
    normalize = namespace["display_term"]
    assert normalize("竖直速度（负号表示向下）") == "竖直速度（负号表示向下）"
    assert normalize("相同水平速度 · 高度 ×4") == "相同水平速度 · 高度 ×4"
