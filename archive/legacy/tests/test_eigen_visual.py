"""Exact topic facts, native frame clock and optional real TeX; no approval."""

import ast
from fractions import Fraction
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.semantic_focus import focus_windows, validate_narration


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/eigen_visual.py"
FIXTURE = ROOT / "tests/fixtures/eigen-visual"


def data(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lesson():
    return load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    with native_run(lesson, lesson.EigenDirectionsLesson, data("plan.json")) as scene:
        return scene


def test_native_full_clock_focus_and_chapters(native, lesson):
    plan = data("plan.json")
    assert native.time == plan["duration"] == 210
    assert native.frame == 6300
    assert tuple(cue["duration"] for cue in native.cues) == lesson.CUE_DURATIONS
    validate_events(native.timeline, {"duration": native.time, "events": native.visual_events})
    report = json.loads(native.out.files["focus-events.json"])
    windows = focus_windows(report, native.time)
    assert set(windows) == {row["id"] for row in plan["focus_intents"]}
    assert not native._open_focus
    for actual, cue in zip(native.chapter_times, native.cues, strict=True):
        assert actual == {"id": cue["id"], "start": cue["start"], "end": cue["start"] + cue["duration"]}
    for row in plan["focus_intents"]:
        cue = next(cue for cue in native.cues if cue["id"] == row["cue"])
        assert cue["start"] <= windows[row["id"]]["start"] < windows[row["id"]]["end"] <= cue["start"] + cue["duration"]
    motion = json.loads(native.out.files["eigen-motion.json"])
    assert motion["duration"] == native.time
    assert motion["chapters"] == native.chapter_times
    assert len(motion["samples"]) == len(native.motion_samples)
    validate_narration(data("narration-draft-v001.json"), native.timeline, report)


def test_measured_native_clock_contract_is_reproducible(native):
    contract = data("native-clock-contract.json")
    assert "no GL, pixels or approval" in contract["evidence_type"]
    assert contract["duration"] == native.time
    assert contract["frames"] == native.frame
    assert contract["chapters"] == native.chapter_times
    assert contract["events"] == native.visual_events
    assert contract["windows"] == native._closed_focus
    assert contract["symbol_transitions"] == native.symbol_transitions


@pytest.mark.parametrize("x,y", [(Fraction(3, 2), Fraction(1, 2)),
                                (Fraction(-2), Fraction(3)),
                                (Fraction(0), Fraction(0)),
                                (Fraction(7, 13), Fraction(-8, 11))])
def test_matrix_interpolation_and_decomposition_exact(lesson, x, y):
    assert lesson.A == ((2, 1), (1, 2))
    assert lesson.apply_matrix(lesson.A, (x, y)) == (2 * x + y, x + 2 * y)
    c1, c2 = lesson.decompose((x, y))
    assert (c1 + c2, c1 - c2) == (x, y)
    for t in (Fraction(0), Fraction(1, 7), Fraction(1, 2), Fraction(1)):
        assert lesson.transform((x, y), t) == ((1 + t) * x + t * y, t * x + (1 + t) * y)
        assert lesson.recombine(c1, c2, t) == lesson.transform((x, y), t)
        assert lesson.transform((c1, c1), t) == ((1 + 2 * t) * c1,) * 2
        assert lesson.transform((c2, -c2), t) == (c2, -c2)


@pytest.mark.parametrize("scale", [Fraction(-7, 3), Fraction(-1), Fraction(1, 13), Fraction(4)])
def test_two_whole_eigenlines_including_negative_multiples(lesson, scale):
    for vector, value in (((scale, scale), 3), ((scale, -scale), 1)):
        assert lesson.is_eigenvector(vector)
        assert lesson.apply_matrix(lesson.A, vector) == tuple(value * component for component in vector)
    assert not lesson.is_eigenvector((0, 0))


def test_solve_is_exhaustive_not_a_guess_from_two_arrows(lesson):
    for x in range(-5, 6):
        for y in range(-5, 6):
            image = lesson.apply_matrix(lesson.A, (x, y))
            assert lesson.cross((x, y), image) == x * x - y * y
            assert lesson.is_eigenvector((x, y)) == ((x == y or x == -y) and (x, y) != (0, 0))
            if (x, y) == (0, 0):
                continue
            if x == y:
                assert x != 0
                assert image == (3 * x, 3 * y)
            elif x == -y:
                assert x - y != 0
                assert image == (x, y)
            else:
                assert not lesson.is_eigenvector((x, y))
    assert lesson.transform((1, 0)) == (2, 1)
    # Definition itself allows negative or zero lambda; zero input is excluded.
    assert lesson.is_eigenvector((1, 2), ((-2, 0), (0, -2)))
    assert lesson.is_eigenvector((1, 2), ((0, 0), (0, 0)))
    assert not lesson.is_eigenvector((0, 0), ((0, 0), (0, 0)))


def test_real_rotation_counterexample_for_any_nonzero_input(lesson):
    for x, y in ((1, 0), (0, -1), (2, .7), (-3, 5), (.1, -.3)):
        image = lesson.apply_matrix(lesson.ROTATION, (x, y))
        assert image == (-y, x)
        assert x * image[0] + y * image[1] == pytest.approx(0)
        assert lesson.cross((x, y), image) == pytest.approx(x * x + y * y)
        assert not lesson.is_eigenvector((x, y), lesson.ROTATION)
        np.testing.assert_allclose(lesson.rotated((x, y), np.pi / 2), image, atol=1e-12)


def test_native_every_grid_endpoint_and_basis_share_one_matrix(native, lesson):
    rows = [row for row in native.motion_samples if row["kind"] == "plane"]
    assert len(rows) >= 40 * 30
    probes = np.array(lesson.PROBES)
    grid = np.array(lesson.GRID_SEGMENTS)
    for stage in ("opening", "directions", "closing"):
        subset = [row for row in rows if row["stage"] == stage]
        assert subset[0]["t"] < .01
        assert subset[-1]["t"] == pytest.approx(1)
    for row in rows:
        t = row["t"]
        matrix = (1 - t) * np.eye(2) + t * np.array(lesson.A)
        expected_probes = probes @ matrix.T
        expected_grid = grid @ matrix.T
        actual_probes = (np.array(row["endpoints"])[:, :2] - [-3.5, -.25]) / .7
        actual_grid = (np.array(row["grid"])[:, :, :2] - [-3.5, -.25]) / .7
        np.testing.assert_allclose(actual_probes, expected_probes, atol=2e-6)
        np.testing.assert_allclose(actual_grid, expected_grid, atol=2e-6)
        np.testing.assert_allclose(row["axes"], rows[0]["axes"], atol=1e-12)
        assert np.min(np.array(row["grid"])[:, :, 1]) > -3.28
        assert np.min(np.array(row["endpoints"])[:, 1]) > -3.28
        # A general vector changes line; both candidate eigenvectors stay on theirs.
        assert actual_probes[0, 1] == pytest.approx(t, abs=2e-6)
        assert actual_probes[2, 0] == pytest.approx(actual_probes[2, 1], abs=2e-6)
        assert actual_probes[3, 0] == pytest.approx(-actual_probes[3, 1], abs=2e-6)


def test_native_recomposition_and_direct_image_agree_throughout(native, lesson):
    rows = [row for row in native.motion_samples if row["kind"] == "decomposition"]
    assert len(rows) >= 17 * 30
    assert rows[0]["t"] < .01
    assert rows[-1]["t"] == pytest.approx(1)
    for row in rows:
        t = row["t"]
        np.testing.assert_allclose(row["first"], lesson.EigenDirectionsLesson.point((1 + 2 * t, 1 + 2 * t)), atol=2e-6)
        np.testing.assert_allclose(row["second_start"], row["first"], atol=2e-6)
        np.testing.assert_allclose(row["second_end"], row["total"], atol=2e-6)
        np.testing.assert_allclose(row["direct"], row["total"], atol=2e-6)
        np.testing.assert_allclose(row["total"], lesson.EigenDirectionsLesson.point(lesson.transform((1.5, .5), t)), atol=2e-6)
    np.testing.assert_allclose(rows[-1]["total"], lesson.EigenDirectionsLesson.point((3.5, 2.5)), atol=2e-6)


def test_native_rotation_uses_a_true_turn_not_a_length_change(native, lesson):
    rows = [row for row in native.motion_samples if row["kind"] == "rotation"]
    assert len(rows) >= 18 * 30
    assert rows[-1]["angle"] == pytest.approx(np.pi / 2)
    for row in rows:
        v = lesson.rotated(row["original"], row["angle"])
        np.testing.assert_allclose(row["endpoint"], lesson.EigenDirectionsLesson.point(v), atol=2e-6)
        assert np.linalg.norm(v) == pytest.approx(np.linalg.norm(row["original"]))


def test_native_symbol_routes_settle_before_reading(native):
    windows = {row["id"]: row for row in native._closed_focus}
    marks = {row["id"]: row["time"] for row in native.visual_events}
    focus_ids = {"components": "two_components", "factor": "factor"}
    assert len(native.symbol_transitions) == 7
    for transition in native.symbol_transitions:
        stage = transition["stage"]
        identity = focus_ids.get(stage, stage)
        assert marks[stage + "_ready"] == transition["end"]
        assert windows[identity]["start"] == transition["end"]
        assert windows[identity]["end"] - windows[identity]["start"] >= 3
        rows = [row for row in native.motion_samples if row["kind"] == "symbol" and row["stage"] == stage]
        assert len(rows) >= 60
        assert max(np.ptp([row["centers"][key] for row in rows], axis=0).max()
                   for key in rows[0]["centers"]) > .2


def test_fresh_scope_no_other_scenes_no_timing_override(lesson):
    plan = data("plan.json")
    assert plan["revision_mode"] == "fresh"
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v3.1.json"
    assert plan["scene_class"] == lesson.EigenDirectionsLesson.__name__
    assert visual_timeline(plan)["duration"] == sum(lesson.CUE_DURATIONS) == 210
    assert plan["subtitle_reserve"]["pixel_top"] == 984
    for row in plan["state_contracts"]:
        assert all(row.get(key) for key in ("writer", "consumers", "lifecycle", "invalidation"))
    tree = ast.parse(SOURCE.read_text())
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name.startswith("examples") or any(word in name for word in ("projectile", "derivative", "pi_bounds")) for name in imports)
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert not methods & {"get_time", "get_time_progression", "play", "wait", "render", "sound", "publish"}
    assert all(plan["production_boundary"][key] is False for key in ("rendered", "visual_approved", "narration_approved", "audio_generated"))
    draft = data("narration-draft-v001.json")
    assert "not_installed_or_approved" in draft["status"]
    assert all("audio_path" not in row and "duration" not in row for row in draft["segments"])


@pytest.fixture(scope="module")
def tex_environment():
    from manimind.render.manim_renderer import _render_environment

    env = _render_environment()
    if not all(shutil.which(tool, path=env["PATH"]) for tool in ("xelatex", "dvisvgm")):
        pytest.skip("Real TeX needs renderer PATH tools; no GL rendering is requested")
    return env


def test_real_tex_all_selectors_and_plain_formulas(lesson, native, tex_environment, monkeypatch):
    from manimlib import Tex
    from manimind.components.formula_motion import SemanticFormula

    monkeypatch.setenv("PATH", tex_environment["PATH"])
    for stage, (latex, tokens) in lesson.ALGEBRA.items():
        formula = SemanticFormula(latex, tokens=tokens, font_size=54)
        assert set(formula._resolve_tags()) == set(tokens), stage
        assert all(formula.tag(key).family_members_with_points() for key in tokens)
        assert formula.get_width() < 11.8
    for latex in sorted({label for label in native.labels if label.isascii()}):
        formula = Tex(latex, template="basic_ctex", font_size=42)
        assert formula.family_members_with_points(), latex


def test_real_tex_native_replacements_and_non_crossing_identities(lesson, native, tex_environment, monkeypatch):
    from manimind.components.formula_motion import SemanticFormula, matching_transform

    monkeypatch.setenv("PATH", tex_environment["PATH"])

    class Sink:
        def __init__(self, source):
            self.mobjects = [source]

        def add(self, *objects):
            self.mobjects.extend(objects)

        def remove(self, *objects):
            self.mobjects = [obj for obj in self.mobjects if all(obj is not old for old in objects)]

    for transition in native.symbol_transitions:
        stage = transition["stage"]
        source_stage = next(key for key, value in lesson.ALGEBRA.items() if value[0] == transition["source"])
        a, b = lesson.ALGEBRA[source_stage], lesson.ALGEBRA[stage]
        source = SemanticFormula(a[0], tokens=a[1], font_size=54).move_to(transition["source_center"])
        target = SemanticFormula(b[0], tokens=b[1], font_size=54).move_to(transition["target_center"])
        keys = [key for key in lesson.MATCH_IDS.get(stage, target.semantic_ids) if key in source.semantic_ids]
        pairs = [(key, key) for key in keys]
        start = {key: source.tag(key).get_center().copy() for key in keys}
        animation = matching_transform(source, target, pairs=pairs, unmatched_in_place=True)
        sink = Sink(source)
        animation.begin()
        for alpha in np.linspace(0, 1, 21):
            animation.interpolate(alpha)
            for i, key in enumerate(keys):
                for other in keys[i + 1:]:
                    left, right = source.tag(key), source.tag(other)
                    # Axis-aligned boxes of the moving semantic identities must not collide.
                    separated = (abs(left.get_x() - right.get_x()) > (left.get_width() + right.get_width()) / 2 + .015
                                 or abs(left.get_y() - right.get_y()) > (left.get_height() + right.get_height()) / 2 + .015)
                    assert separated, (stage, alpha, key, other)
        assert max(np.linalg.norm(source.tag(key).get_center() - start[key]) for key in keys) > .5
        animation.finish()
        animation.clean_up_from_scene(sink)
        assert all(obj is not source for obj in sink.mobjects)
        assert any(obj is target for obj in sink.mobjects)
