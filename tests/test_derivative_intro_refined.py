"""Versioned v002 geometry and source contracts, never pixel or review approval."""

import ast
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path

import pytest

from test_derivative_intro_visual import forbid_production_project_reads, model


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-intro-refined"
SOURCE = ROOT / "examples/derivative_intro_refined.py"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def plan():
    delta = read("plan.json")
    result = json.loads((FIXTURE / delta["base_fixture"]).read_text(encoding="utf-8"))
    result.update({key: delta[key] for key in ("scene", "scene_class", "duration", "sources")})
    cue = next(row for row in result["cues"] if row["id"] == "definition")
    cue.update(delta["definition_update"])
    cue["anchors"] = delta["definition_anchor_prefix"] + cue["anchors"]
    index = next(i for i, row in enumerate(result["focus_intents"]) if row["id"] == "derivative_at_two")
    result["focus_intents"][index:index] = delta["definition_focus_prefix"]
    return result


def narration():
    delta = read("narration.json")
    result = json.loads((FIXTURE / delta["base_fixture"]).read_text(encoding="utf-8"))
    index = next(i for i, row in enumerate(result["units"]) if row["id"] == delta["insert_before"])
    result["units"].insert(index, delta["unit"])
    return result


@pytest.fixture(scope="module")
def lesson():
    from lesson_native_harness import load_lesson
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        return load_lesson(SOURCE)


@contextmanager
def run(lesson, value, real_tex=False):
    from lesson_native_harness import native_run
    import manimind.components.formula_motion as motion
    real_formula = lesson.SemanticFormula
    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            if real_tex:
                # native_run owns/restores these two module attributes.
                lesson.SemanticFormula = real_formula
                motion.SemanticFormula = real_formula
            patcher.setattr(lesson.base, "SemanticFormula", lesson.SemanticFormula)

        with native_run(lesson, lesson.DerivativeIntroRefinedLesson, value, initialize=initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def native(lesson):
    with run(lesson, plan()) as scene:
        return scene


def test_original_work_is_reused_without_scene_or_shared_engine_copy(lesson):
    assert lesson.DerivativeIntroRefinedLesson.__bases__ == (lesson.base.DerivativeIntroLesson,)
    for name in ("opening", "average", "approach", "algebra", "both_sides", "tangent_prediction", "closing", "construct"):
        assert getattr(lesson.DerivativeIntroRefinedLesson, name) is getattr(lesson.base.DerivativeIntroLesson, name)
    assert "examples/derivative_intro_visual.py" in plan()["sources"]
    tree = ast.parse(SOURCE.read_text())
    assert not any(isinstance(node, ast.ClassDef) and node.name != "DerivativeIntroRefinedLesson" for node in tree.body)


def test_raw_zero_state_is_separate_from_nonzero_quotient_offline(model):
    node = next(node for node in ast.parse(SOURCE.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == "raw_quotient_components")
    namespace = {"base": model}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    components = namespace["raw_quotient_components"]
    assert components(0) == (0, 0)
    with pytest.raises(ValueError, match="h != 0"):
        model.difference_quotient(0)
    for h in (Fraction(-1, 10), Fraction(-1, 100), Fraction(1, 100), Fraction(1, 10)):
        numerator, denominator = components(h)
        assert denominator != 0
        assert numerator / denominator == model.difference_quotient(h) == 4 + h


def test_original_cue_clock_plus_explicit_zero_bridge(native, lesson):
    design = read("design.json")
    assert lesson.CUE_DURATIONS == tuple(design["default_cue_durations"])
    assert lesson.DEFINITION_STAGES == design["definition_stages"]
    assert native.time == 338 and native.frame == 10140
    assert tuple(row["duration"] for row in native.cues) == lesson.CUE_DURATIONS
    assert len(native.visual_events) == 31
    assert len(native._closed_focus) == 28
    assert not native._open_focus
    assert [row["stage"] for row in native.symbol_transitions] == design["semantic_stages"]


def test_schema3_references_use_actual_readable_windows(native):
    from manimind.review.meaning_units import validate_narration
    from manimind.review.semantic_focus import focus_windows
    focus = json.loads(native.out.files["focus-events.json"])
    validate_narration(narration(), native.timeline, focus)
    windows = focus_windows(focus, native.time)
    assert set(windows) == {row["id"] for row in plan()["focus_intents"]}
    cues = {row["id"]: row for row in native.cues}
    for unit in narration()["units"]:
        assert "".join(ref["text"] for ref in unit["references"]) == unit["text"]
        cue = cues[unit["cue"]]
        for ref in unit["references"]:
            window = windows[ref["focus"]]
            assert cue["start"] <= window["start"] < window["end"] <= cue["start"] + cue["duration"]


def test_staged_geometry_keeps_history_separate_and_withholds_new_syntax(native):
    rows = [row for row in native.motion_samples if row["kind"] == "refined_formula"]
    assert len(rows) > 300
    for row in rows:
        assert row["target"][3] < row["history"][2]
        if row["phase"] == "tokens":
            assert row["syntax_opacity"] == 0
            for token in row["visible_tokens"]:
                if token["visible"]:
                    assert token["bounds"][3] < row["history"][2] - .06
    marks = {row["id"]: row["time"] for row in native.visual_events}
    for transition in native.symbol_transitions:
        ready = "definition_pattern_ready" if transition["stage"] == "general_position" else transition["stage"] + "_ready"
        assert marks[ready] >= transition["end"]
        assert transition["start"] < transition["phase_ends"][0] < transition["phase_ends"][1] < transition["phase_ends"][2] < transition["end"]


def test_zero_bridge_explicitly_displays_both_objects_with_real_motion(native):
    assert any(r"\frac{0}{0}" in label for label in native.labels)
    assert "原差商在 h = 0 处无定义" in native.labels
    assert r"\lim_{h\to0}m(h)=4" in native.labels
    rows = [row for row in native.motion_samples if row["kind"] == "zero_bridge"]
    assert rows[0]["radius"] == pytest.approx(.1)
    assert rows[-1]["radius"] == pytest.approx(.01)
    assert all(row["radius"] > 0 and row["right"] > 4 > row["left"] for row in rows)
    marks = {row["id"]: row["time"] for row in native.visual_events}
    assert marks["zero_input_undefined_ready"] < marks["zero_limit_comparison_ready"] < marks["derivative_value_ready"]


def test_local_timing_changes_hold_without_stretching_nonzero_motion(lesson, native):
    value = deepcopy(plan())
    value["cues"][5]["duration"] += 2
    with run(lesson, value) as adjusted:
        assert adjusted.time == 340
        before = [row for row in native.motion_samples if row["kind"] == "zero_bridge"]
        after = [row for row in adjusted.motion_samples if row["kind"] == "zero_bridge"]
        assert before == after


def test_real_tex_native_staged_geometry_without_gl(lesson, monkeypatch):
    from manimind.render.manim_renderer import _render_environment
    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    with run(lesson, plan(), real_tex=True) as scene:
        rows = [row for row in scene.motion_samples if row["kind"] == "refined_formula"]
        assert len(rows) > 300
        for row in rows:
            assert row["target"][2] > -3.05
            assert row["target"][3] < row["history"][2]
            if row["phase"] == "tokens":
                assert row["syntax_opacity"] == 0
                for token in row["visible_tokens"]:
                    if token["visible"]:
                        assert token["bounds"][3] < row["history"][2] - .06
        for stage in read("design.json")["semantic_stages"]:
            assert any(token["visible"] for row in rows if row["stage"] == stage and row["phase"] == "tokens"
                       for token in row["visible_tokens"])
        assert len(scene.symbol_transitions) == 5
        assert all(row["end"] > row["start"] for row in scene.symbol_transitions)


def test_inherited_effective_motion_is_unchanged_except_declared_time_offset(lesson, native):
    from lesson_native_harness import native_run
    original = json.loads((FIXTURE / "../derivative-intro/plan.json").read_text())
    with native_run(lesson.base, lesson.base.DerivativeIntroLesson, original) as baseline:
        for kind in ("approach", "two_sides", "prediction"):
            before = [row for row in baseline.motion_samples if row["kind"] == kind]
            after = [row for row in native.motion_samples if row["kind"] == kind]
            assert len(before) == len(after)
            for left, right in zip(before, after, strict=True):
                assert right["time"] - left["time"] == pytest.approx(34 if kind == "prediction" else 0)
                assert {key: value for key, value in left.items() if key != "time"} == {
                    key: value for key, value in right.items() if key != "time"}


def test_all_fixture_patches_are_versioned_test_inputs_only():
    for name in ("plan.json", "narration.json", "design.json"):
        value = read(name)
        assert value["artifact_type"] == "test_fixture"
        assert value["status"] == "test_only_not_production_or_approved"
        assert "lesson_context" not in value
