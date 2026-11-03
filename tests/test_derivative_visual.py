"""Topic facts and native 30fps geometry/time, without rendering or approval."""

import ast
from fractions import Fraction
import json
from pathlib import Path

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.bootstrap import resolve_tool
from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.semantic_focus import focus_windows, validate_narration


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_visual.py"
FIXTURE = ROOT / "tests/fixtures/derivative-visual"


def data(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lesson():
    return load_lesson(SOURCE)


@pytest.mark.parametrize("h", [Fraction(-3, 5), Fraction(-1, 10000),
                               Fraction(1, 10000), Fraction(3, 5), Fraction(4)])
def test_exact_difference_quotient_before_limit(lesson, h):
    numerator = (1 + h) ** 2 - 1
    assert numerator == 1 + 2 * h + h * h - 1 == 2 * h + h * h == h * (2 + h)
    assert lesson.secant_rate(h) == numerator / h == 2 + h


def test_zero_never_enters_a_difference_quotient(lesson):
    with pytest.raises(ValueError, match="distinct"):
        lesson.secant_rate(0)
    with pytest.raises(ValueError, match="undefined"):
        lesson.corner_rate(0)
    for s in (0, -1):
        with pytest.raises(ValueError, match="positive"):
            lesson.zoom_height(.5, s)


@pytest.mark.parametrize("s", [Fraction(1, 2), Fraction(1, 10), Fraction(1, 100)])
def test_zoom_is_an_exact_common_scale_change_not_a_shape_morph(lesson, s):
    for u in [Fraction(-1), Fraction(-3, 7), Fraction(0), Fraction(3, 7), Fraction(1)]:
        x = 1 + s * u
        v = (lesson.square(x) - lesson.square(1)) / s
        assert v == lesson.zoom_height(u, s) == 2 * u + s * u * u
        assert abs(v - 2 * u) <= s
        assert (x - 1) / s == u


def test_two_sided_limit_and_corner_counterexample(lesson):
    for r in (Fraction(1, 10), Fraction(1, 100), Fraction(1, 1000)):
        assert lesson.secant_rate(r) - 2 == r
        assert 2 - lesson.secant_rate(-r) == r
        assert lesson.corner_rate(r) == 1
        assert lesson.corner_rate(-r) == -1
    for h in (Fraction(-1, 10), Fraction(1, 10)):
        assert lesson.square(1 + h) - 1 - 2 * h == h * h


@pytest.fixture(scope="module")
def native(lesson):
    with native_run(lesson, lesson.DerivativeLesson, data("plan.json")) as scene:
        return scene


def test_native_7020_frame_clock_and_event_focus_teardown(native, lesson):
    plan = data("plan.json")
    assert native.time == plan["duration"] == 234
    assert native.frame == 7020
    assert tuple(cue["duration"] for cue in native.cues) == lesson.CUE_DURATIONS
    validate_events(native.timeline, {"duration": native.time, "events": native.visual_events})
    report = json.loads(native.out.files["focus-events.json"])
    windows = focus_windows(report, native.time)
    assert set(windows) == {row["id"] for row in plan["focus_intents"]}
    assert not native._open_focus
    assert all(play["end"] > play["start"] for play in native.plays)
    for actual, expected in zip(native.chapter_times, native.cues, strict=True):
        assert actual["start"] == expected["start"]
        assert actual["end"] == expected["start"] + expected["duration"]
    motion = json.loads(native.out.files["derivative-motion.json"])
    assert motion["duration"] == native.time
    assert motion["chapters"] == native.chapter_times
    assert len(motion["samples"]) == len(native.motion_samples)


def test_native_clock_contract_is_reproducible_not_a_render_report(native):
    contract = data("native-clock-contract.json")
    assert "no GL, pixels or approval" in contract["evidence_type"]
    assert native.time == contract["duration"]
    assert native.frame == contract["frames"]
    assert native.chapter_times == contract["chapters"]
    assert native.visual_events == contract["events"]
    assert native._closed_focus == contract["windows"]


def test_narration_is_only_intent_inside_its_actual_cue(native):
    report = json.loads(native.out.files["focus-events.json"])
    windows = focus_windows(report, native.time)
    draft = data("narration-draft-v001.json")
    validate_narration(draft, native.timeline, report)
    intended = {row["id"]: row for row in data("plan.json")["focus_intents"]}
    for row in draft["segments"]:
        assert intended[row["focus"]]["cue"] == row["cue"]
        cue = next(cue for cue in native.cues if cue["id"] == row["cue"])
        window = windows[row["focus"]]
        assert cue["start"] <= window["start"] < window["end"] <= cue["start"] + cue["duration"]
    assert "not_installed_or_approved" in draft["status"]
    # Do not turn a character-count estimate into a fabricated audio duration.
    assert all("audio_path" not in row and "duration" not in row for row in draft["segments"])


def test_two_sides_are_real_native_motion_on_the_same_parabola(native, lesson):
    rows = [row for row in native.motion_samples if row["kind"] == "sides"]
    assert len(rows) >= 22 * 30
    assert rows[0]["h"] == pytest.approx(.6)
    assert rows[-1]["h"] == pytest.approx(.06)
    for row in rows:
        h = row["h"]
        assert 0 < h <= .6
        assert row["right"] == pytest.approx(2 + h)
        assert row["left"] == pytest.approx(2 - h)
        np.testing.assert_allclose(row["qr"], lesson.DerivativeLesson.original_point(1 + h, (1 + h) ** 2))
        np.testing.assert_allclose(row["ql"], lesson.DerivativeLesson.original_point(1 - h, (1 - h) ** 2))
    assert np.ptp([row["qr"][1] for row in rows]) > 1
    assert np.ptp([row["ql"][0] for row in rows]) > .8


def test_native_symbols_move_and_settle_before_each_focus(native, lesson):
    windows = {row["id"]: row for row in native._closed_focus}
    marks = {row["id"]: row["time"] for row in native.visual_events}
    for transition in native.symbol_transitions:
        stage = transition["stage"]
        assert marks[stage + "_ready"] == transition["end"]
        assert windows[stage]["start"] == transition["end"]
        assert windows[stage]["end"] - windows[stage]["start"] >= 5
        rows = [row for row in native.motion_samples if row["kind"] == "symbol" and row["stage"] == stage]
        assert len(rows) >= 90
        moving = max(np.ptp([row["centers"][key] for row in rows], axis=0).max()
                     for key in rows[0]["centers"])
        if stage != "reduce":
            assert moving > .03
    assert [row["target"] for row in native.symbol_transitions] == [row[1] for row in lesson.ALGEBRA[1:]]
    assert marks["cancellation_ready"] < windows["simplify"]["start"]
    assert windows["cancel_nonzero"]["end"] - windows["cancel_nonzero"]["start"] == 5


def test_zoom_native_geometry_shrinks_only_the_exact_remainder(native):
    rows = [row for row in native.motion_samples if row["kind"] == "zoom"]
    assert len(rows) >= 25 * 30
    assert rows[0]["s"] == pytest.approx(.5)
    assert rows[-1]["s"] == pytest.approx(.01)
    for row in rows:
        s, u = row["s"], row["u"]
        assert s > 0
        assert row["v"] == pytest.approx(2 * u + s * u * u)
        assert row["error"] == pytest.approx(1.1 * s, abs=3e-7)
        np.testing.assert_allclose(row["curve_end"], [-3.6 + 1.1, -.35 + 1.1 * (2 + s), 0])
    assert rows[0]["error"] / rows[-1]["error"] == pytest.approx(50, abs=.001)


def test_native_counterexample_never_converges_to_one_slope(native):
    rows = [row for row in native.motion_samples if row["kind"] == "corner"]
    assert len(rows) >= 22 * 30
    assert rows[0]["h"] > rows[-1]["h"] > 0
    assert all(row["right"] == 1 and row["left"] == -1 for row in rows)


def test_plan_is_fresh_and_no_runtime_fixture_or_frozen_lesson_dependency(lesson):
    plan = data("plan.json")
    assert plan["revision_mode"] == "fresh"
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v3.1.json"
    assert plan["scene_class"] == lesson.DerivativeLesson.__name__
    assert visual_timeline(plan)["duration"] == sum(lesson.CUE_DURATIONS) == plan["duration"]
    assert not any("outputs/" in path for path in plan["sources"])
    for row in plan["state_contracts"]:
        assert all(row.get(key) for key in ("writer", "consumers", "lifecycle", "invalidation"))
    source = SOURCE.read_text()
    tree = ast.parse(source)
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any("projectile" in name for name in imports)
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert not methods & {"get_time", "get_time_progression", "play", "wait", "render", "sound", "publish"}
    assert set(plan["production_boundary"][key] for key in ("rendered", "visual_approved", "audio_generated")) == {False}


def test_scene_geometry_stays_above_subtitle_reserve(native, lesson):
    # Geometry bounds only; placeholder text sizes cannot approve typography.
    for row in native.motion_samples:
        if row["kind"] == "sides":
            assert min(row["qr"][1], row["ql"][1]) > -3.28
    for slope in (1.4, 2, 2.6):
        assert native.slope_line(slope, lesson.CURVE).get_bottom()[1] > -3.28
    with pytest.raises(ValueError, match="h != 0"):
        native.secant(0, lesson.CURVE)
    assert "趋近零，和直接等于零，是两件事" in native.labels
    assert "横纵增量，都除以同一个 s" in native.labels


@pytest.mark.skipif(resolve_tool("xelatex") is None or resolve_tool("dvisvgm") is None,
                    reason="Real native TeX selectors need xelatex and dvisvgm; not a pixel render")
def test_real_tex_selectors_and_all_plain_formula_strings(lesson, native, monkeypatch):
    from manimlib import Tex
    from manimind.components.formula_motion import SemanticFormula
    from manimind.render.manim_renderer import _render_environment

    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    for _, latex, tokens in lesson.ALGEBRA:
        formula = SemanticFormula(latex, tokens=tokens, font_size=60)
        assert set(formula._resolve_tags()) == set(tokens)
        assert all(formula.tag(key).family_members_with_points() for key in tokens)
        assert formula.get_width() < 12
    formulas = {label for label in native.labels if all(ord(char) < 128 for char in label)}
    for latex in formulas:
        formula = Tex(latex, template="basic_ctex", font_size=40)
        assert formula.has_points() or formula.family_members_with_points()


@pytest.mark.skipif(resolve_tool("xelatex") is None or resolve_tool("dvisvgm") is None,
                    reason="Real native TeX matching needs local TeX tools, never a GL camera")
def test_real_native_glyph_chain_moves_and_replaces_source(lesson, monkeypatch):
    from manimind.components.formula_motion import SemanticFormula, matching_transform
    from manimind.render.manim_renderer import _render_environment

    monkeypatch.setenv("PATH", _render_environment()["PATH"])

    class Sink:
        def __init__(self, source):
            self.mobjects = [source]

        def add(self, *objects):
            self.mobjects.extend(objects)

        def remove(self, *objects):
            self.mobjects = [obj for obj in self.mobjects if all(obj is not old for old in objects)]

    formulas = [SemanticFormula(latex, tokens=tokens, font_size=60)
                for _, latex, tokens in lesson.ALGEBRA]
    for (stage, _, _), source, target in zip(lesson.ALGEBRA[1:], formulas, formulas[1:]):
        common = set(source.semantic_ids) & set(target.semantic_ids)
        before = {key: source.tag(key).get_center().copy() for key in common}
        animation = matching_transform(source, target, unmatched_in_place=True, path_arc=.25)
        sink = Sink(source)
        animation.begin()
        animation.interpolate(.5)
        displacement = max(np.linalg.norm(source.tag(key).get_center() - before[key]) for key in common)
        if stage == "reduce":
            # Symmetric +1/-1 removal should leave the central terms in place.
            assert displacement < 1e-5
        else:
            assert displacement > .01
        animation.finish()
        animation.clean_up_from_scene(sink)
        assert all(obj is not source for obj in sink.mobjects)
        assert any(obj is target for obj in sink.mobjects)
