"""Offline mathematics and bounded native geometry; no GL or lesson approval."""

import ast
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_intro_visual.py"
FIXTURE = ROOT / "tests/fixtures/derivative-intro"
PURE_NAMES = {"finite_real", "square", "increments", "difference_quotient", "two_sided_rates",
              "tangent_value", "local_prediction", "approximation_remainder", "plot_point"}


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def forbid_production_project_reads():
    original_open = Path.open
    production = ROOT / "runtime/projects"

    def fixture_open(path, *args, **kwargs):
        if path.resolve().is_relative_to(production):
            raise AssertionError("Tests must not read production runtime projects")
        return original_open(path, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(Path, "open", fixture_open)
        yield


@pytest.fixture(scope="module")
def model():
    # Pure functions are tested without importing Manim, creating a camera or TeX.
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if
             isinstance(node, ast.Import) and any(item.name == "math" for item in node.names)
             or isinstance(node, ast.ImportFrom) and node.module == "numbers"
             or isinstance(node, ast.FunctionDef) and node.name in PURE_NAMES]
    module = types.ModuleType("derivative_intro_offline_model")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), module.__dict__)
    return module


@pytest.mark.parametrize("h", [Fraction(-4), Fraction(-4, 5), Fraction(-1, 10), Fraction(-1, 10000),
                               Fraction(1, 10000), Fraction(1, 10), Fraction(4, 5), Fraction(1), Fraction(4)])
def test_every_algebra_step_is_exact_on_original_nonzero_domain(model, h):
    raw = ((2 + h) ** 2 - 4) / h
    expanded = (4 + 4 * h + h ** 2 - 4) / h
    combined = (4 * h + h ** 2) / h
    factored = h * (4 + h) / h
    assert raw == expanded == combined == factored == 4 + h == model.difference_quotient(h)
    assert model.increments(h) == (h, (2 + h) ** 2 - 4)


@pytest.mark.parametrize("zero", [0, -0.0, Fraction(0)])
def test_quotient_excludes_zero_but_prediction_and_remainder_include_it(model, zero):
    with pytest.raises(ValueError, match="h != 0"):
        model.difference_quotient(zero)
    assert model.local_prediction(zero) == 4
    assert model.approximation_remainder(zero) == 0
    assert model.increments(zero) == (0, 0)


@pytest.mark.parametrize("radius", [Fraction(4, 5), Fraction(1, 10), Fraction(1, 100), Fraction(1, 10000)])
def test_both_sides_and_direct_error_identity(model, radius):
    right, left = model.two_sided_rates(radius)
    assert right > 4 > left
    assert abs(right - 4) == abs(left - 4) == radius
    assert model.increments(-radius)[1] < 0
    assert model.increments(radius)[1] > 0


@pytest.mark.parametrize("radius", [0, -.1])
def test_two_sided_radius_is_positive(model, radius):
    with pytest.raises(ValueError, match="positive"):
        model.two_sided_rates(radius)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_model_inputs_rejected(model, bad):
    for helper in (model.square, model.increments, model.difference_quotient,
                   model.two_sided_rates, model.local_prediction, model.approximation_remainder):
        with pytest.raises(ValueError, match="finite"):
            helper(bad)


@pytest.mark.parametrize("bad", [True, "0.1", 1j, None])
def test_not_real_model_inputs_rejected(model, bad):
    with pytest.raises(TypeError, match="real"):
        model.difference_quotient(bad)


@pytest.mark.parametrize("base", [Fraction(-3), Fraction(0), Fraction(2), Fraction(7, 3)])
def test_tangent_and_exact_remainder_general_base_without_teaching_extra_rule(model, base):
    for h in (Fraction(-1, 2), Fraction(0), Fraction(1, 10)):
        actual = model.square(base + h)
        predicted = model.local_prediction(h, base)
        assert predicted == model.tangent_value(base + h, base)
        assert actual - predicted == model.approximation_remainder(h) == h * h
    assert model.local_prediction(Fraction(1, 10)) == Fraction(44, 10)
    assert model.square(Fraction(21, 10)) == Fraction(441, 100)


@pytest.fixture(scope="module")
def lesson():
    from lesson_native_harness import load_lesson
    return load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    from lesson_native_harness import native_run
    with native_run(lesson, lesson.DerivativeIntroLesson, read("plan.json")) as scene:
        return scene


def test_actual_native_clock_marks_and_focus_schema(native, lesson):
    from manimind.experiments.visual_first_data import validate_events
    from manimind.review.semantic_focus import focus_windows
    from manimind.review.meaning_units import validate_narration
    plan, draft = read("plan.json"), read("narration.json")
    assert native.time == plan["duration"] == sum(lesson.CUE_DURATIONS) == 304
    assert native.frame == 9120
    assert tuple(row["id"] for row in native.cues) == lesson.CUE_IDS
    assert tuple(row["duration"] for row in native.cues) == lesson.CUE_DURATIONS
    validate_events(native.timeline, {"duration": native.time, "events": native.visual_events})
    focus = json.loads(native.out.files["focus-events.json"])
    windows = focus_windows(focus, native.time)
    assert set(windows) == {row["id"] for row in plan["focus_intents"]}
    validate_narration(draft, native.timeline, focus)
    cue_map = {row["id"]: row for row in native.cues}
    for unit in draft["units"]:
        cue = cue_map[unit["cue"]]
        for ref in unit["references"]:
            window = windows[ref["focus"]]
            assert cue["start"] <= window["start"] < window["end"] <= cue["start"] + cue["duration"]
    assert not native._open_focus
    assert len(native.chapter_times) == 8
    assert json.loads(native.out.files["derivative-intro-motion.json"])["chapters"] == native.chapter_times


def test_native_approach_uses_one_h_and_fixed_P(native, lesson):
    import numpy as np
    rows = [row for row in native.motion_samples if row["kind"] == "approach"]
    assert len(rows) > 500
    assert rows[0]["h"] == pytest.approx(1)
    assert rows[-1]["h"] == pytest.approx(.02)
    assert all(row["h"] != 0 for row in rows)
    assert all(a["h"] >= b["h"] for a, b in zip(rows, rows[1:]))
    for row in rows:
        h = row["h"]
        assert row["slope"] == pytest.approx(4 + h)
        assert row["delta_y"] == pytest.approx(4 * h + h * h)
        np.testing.assert_allclose(row["q"], lesson.plot_point(2 + h, (2 + h) ** 2))
        assert row["q"][1] > -3.05


def test_native_two_sides_are_signed_and_converge_without_h_zero(native, lesson):
    import numpy as np
    rows = [row for row in native.motion_samples if row["kind"] == "two_sides"]
    assert len(rows) > 350
    assert rows[0]["radius"] == pytest.approx(.8)
    assert rows[-1]["radius"] == pytest.approx(.02)
    for row in rows:
        r = row["radius"]
        assert r > 0
        assert row["right"] > 4 > row["left"]
        assert row["right_dy"] > 0 > row["left_dy"]
        np.testing.assert_allclose(row["qr"], lesson.plot_point(2 + r, (2 + r) ** 2))
        np.testing.assert_allclose(row["ql"], lesson.plot_point(2 - r, (2 - r) ** 2))


def test_native_symbols_move_and_final_states_precede_reading_windows(native, lesson):
    import numpy as np
    marks = {row["id"]: row["time"] for row in native.visual_events}
    windows = {row["id"]: row for row in native._closed_focus}
    for transition, focus in zip(native.symbol_transitions,
                                  ("expanded_terms", "combined_terms", "factored_h", "simplified_rate"), strict=True):
        stage = transition["stage"]
        assert marks[stage + "_ready"] == transition["end"] == windows[focus]["start"]
        rows = [row for row in native.motion_samples if row["kind"] == "symbols" and row["stage"] == stage]
        assert len(rows) > 100
        displacement = max(np.ptp([row["centers"][key] for row in rows], axis=0).max()
                           for key in rows[0]["centers"])
        if stage != "combined":
            assert displacement > .01
    assert [row["target"] for row in native.symbol_transitions] == [row[1] for row in lesson.ALGEBRA[1:]]
    assert marks["factored_ready"] < marks["cancellation_condition_ready"] < marks["simplified_ready"]
    assert windows["nonzero_cancel"]["end"] <= native.symbol_transitions[-1]["start"]


def test_native_local_prediction_is_same_coordinate_mapping_not_shape_morph(native, lesson):
    import numpy as np
    rows = [row for row in native.motion_samples if row["kind"] == "prediction"]
    assert len(rows) > 300
    assert rows[0]["h"] == pytest.approx(.4)
    assert rows[-1]["h"] == pytest.approx(.1)
    for row in rows:
        h = row["h"]
        assert row["actual"] - row["predicted"] == pytest.approx(h * h)
        np.testing.assert_allclose(row["actual_point"], lesson.plot_point(2 + h, (2 + h) ** 2, True))
        np.testing.assert_allclose(row["predicted_point"], lesson.plot_point(2 + h, 4 + 4 * h, True))
        assert min(row["actual_point"][1], row["predicted_point"][1]) > -3.05


def test_local_hold_can_change_without_retiming_scientific_motion(lesson, native):
    from lesson_native_harness import native_run
    plan = deepcopy(read("plan.json"))
    # Extra reading time after the near-state mark, before the chapter boundary.
    plan["cues"][2]["duration"] += 2
    plan["cues"][2]["stage_times"] = {
        f"{fraction:.2f}": 42 * fraction for fraction in (.04, .08, .12, .24, .52, .58, .80)}
    with native_run(lesson, lesson.DerivativeIntroLesson, plan) as adjusted:
        assert adjusted.time == 306
        baseline = [row for row in native.motion_samples if row["kind"] == "approach" and row["time"] <= 89.6]
        changed = [row for row in adjusted.motion_samples if row["kind"] == "approach" and row["time"] <= 89.6]
        assert baseline == changed
        marks = {row["id"]: row["time"] for row in adjusted.visual_events}
        assert marks["approach_near_ready"] == pytest.approx(89.6)


def test_fresh_author_scope_and_schema_not_audio_or_review():
    plan, design, draft = (read(name) for name in ("plan.json", "design.json", "narration.json"))
    expected = "01a1976b-d4e1-7161-a92f-0e5d6e5ab5ca"
    assert all(row["author_agent"] == row["author_context"] == expected for row in (plan, design, draft))
    assert plan["revision_mode"] == "fresh"
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v4.2-unit.json"
    assert not any(plan["production_boundary"][key] for key in ("rendered", "visual_approved", "narration_approved", "audio_generated"))
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name and "derivative_visual" in name for name in imports)
    scene = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assert [node.id for node in scene.bases] == ["UnderstandingScene"]
    assert not {"get_time", "get_time_progression", "play", "wait", "render", "sound", "publish"} & {
        node.name for node in scene.body if isinstance(node, ast.FunctionDef)}
    assert all(set(row) == {"id", "cue", "text", "references"} for row in draft["units"])
    assert all("".join(ref["text"] for ref in row["references"]) == row["text"] for row in draft["units"])
    for row in plan["state_contracts"]:
        assert all(row[key] for key in ("writer", "consumers", "lifecycle", "invalidation"))


def test_fixtures_are_test_only_and_production_access_is_blocked():
    for name in ("plan.json", "narration.json", "design.json"):
        value = read(name)
        assert value["artifact_type"] == "test_fixture"
        assert value["status"] == "test_only_not_production_or_approved"
        assert not {"lesson_context", "sources", "audio_path"} & value.keys()
    with pytest.raises(AssertionError, match="must not read production"):
        (ROOT / "runtime/projects/unused-by-derivative-tests/plan.json").read_text()


def test_original_default_stage_times_are_versioned_independently(lesson):
    design = read("design.json")
    assert lesson.STAGE_TIMES == design["default_stage_times"]
    assert tuple(design["default_cue_durations"]) == lesson.CUE_DURATIONS
    assert list(lesson.CUE_IDS) == list(design["default_stage_times"])


def test_design_fixture_matches_pure_model(model):
    design = read("design.json")["model"]
    base = design["base_x"]
    assert model.square(base) == design["base_y"]
    for sample in design["samples"]:
        h, dy, rate = (Fraction(sample[key]) for key in ("h", "delta_y", "rate"))
        assert model.increments(h, base) == (h, dy)
        assert model.difference_quotient(h, base) == rate
    sample = design["prediction"]
    h = Fraction(sample["h"])
    assert model.local_prediction(h, base) == Fraction(sample["predicted"])
    assert model.square(base + h) == Fraction(sample["actual"])
    assert model.approximation_remainder(h) == Fraction(sample["remainder"])


def test_real_tex_selectors_and_bounded_native_matching_no_camera(lesson, native, monkeypatch):
    from manimind.components.formula_motion import SemanticFormula, matching_transform
    from manimind.render.manim_renderer import _render_environment
    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    formulas = [SemanticFormula(latex, tokens=tokens, font_size=66)
                for _, latex, tokens in lesson.ALGEBRA]
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for call in ast.walk(tree):
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "SemanticFormula"
                and isinstance(call.args[0], ast.Constant)):
            tokens = ast.literal_eval(next(item.value for item in call.keywords if item.arg == "tokens"))
            formula = SemanticFormula(call.args[0].value, tokens=tokens, font_size=49)
            assert set(formula._resolve_tags()) == set(tokens)
            assert formula.get_width() < 12.6
    for formula, (_, _, tokens) in zip(formulas, lesson.ALGEBRA, strict=True):
        assert set(formula._resolve_tags()) == set(tokens)
        assert formula.get_width() < 12.6

    class Sink:
        def __init__(self, source):
            self.mobjects = [source]

        def add(self, *objects):
            self.mobjects.extend(objects)

        def remove(self, *objects):
            self.mobjects = [obj for obj in self.mobjects if all(obj is not old for old in objects)]

    for source, target in zip(formulas, formulas[1:]):
        sink = Sink(source)
        animation = matching_transform(source, target, unmatched_in_place=True, path_arc=.18)
        animation.begin()
        animation.interpolate(.5)
        animation.finish()
        animation.clean_up_from_scene(sink)
        assert all(obj is not source for obj in sink.mobjects)
        assert any(obj is target for obj in sink.mobjects)
    from manimlib import Tex
    for latex in {label for label in native.labels if label and label.isascii()}:
        formula = Tex(latex, template="basic_ctex", font_size=40)
        assert formula.family_members_with_points()
