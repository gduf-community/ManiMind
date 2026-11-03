"""30-fps native animation/sampler tests, without renderer, TeX, speech or runtime files."""

import ast
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.semantic_focus import focus_windows, validate_narration
from test_projectile_integrated import MemoryPath


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/projectile-paced"
SOURCE = ROOT / "examples/projectile_paced.py"


def data(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def native_smoke():
    patcher = pytest.MonkeyPatch()
    original_spec = importlib.util.spec_from_file_location

    def spec(name, location, *args, **kwargs):
        if str(location).endswith("outputs/sol61-visual-first-20261024-v1/candidate.py"):
            location = ROOT / "tests/fixtures/projectile-integrated/frozen_candidate.py"
        return original_spec(name, location, *args, **kwargs)

    patcher.setattr(importlib.util, "spec_from_file_location", spec)
    patcher.syspath_prepend(str(ROOT / "examples"))
    for name in ("projectile_paced", "projectile_integrated", "projectile_formula_motion_full"):
        patcher.delitem(sys.modules, name, raising=False)
    import projectile_paced as paced
    import projectile_formula_motion_full as full
    import projectile_formula_motion as landing
    import manimind.components.formula_motion as motion
    import manimlib as gl
    from manimlib.animation.animation import prepare_animation
    from manimind.experiments.visual_first_support import VisualLessonScene

    class Formula(gl.VGroup):
        """Native vector placeholders; real semantic matching and routes run."""
        def __init__(self, latex, tokens=None, font_size=38, **kwargs):
            self.latex, self.selectors = latex, tokens or {}
            self.semantic_ids = tuple(self.selectors)
            unit = .065 * font_size / 38
            super().__init__(*(gl.Rectangle(width=.8 * unit, height=.32 * font_size / 38,
                fill_opacity=1, stroke_width=0).move_to([i * unit, 0, 0]) for i in range(len(latex))))
            self.center()

        def get_tex(self):
            return self.latex

        def get_parts_by_tex(self, literal):
            return gl.VGroup(*(gl.VGroup(*self.submobjects[m.start():m.end()])
                for m in re.finditer(re.escape(literal), self.latex)))

        def tag(self, identity):
            selector = self.selectors[identity]
            literal, index = (selector, 0) if isinstance(selector, str) else selector
            return self.get_parts_by_tex(literal)[index]

        def _resolve_tags(self):
            return {identity: self.tag(identity) for identity in self.semantic_ids}

    class Number(gl.VGroup):
        def __init__(self, value=0, **kwargs):
            super().__init__(gl.Rectangle(width=.65, height=.3, fill_opacity=1))
            self.value = value

        def set_value(self, value):
            self.value = value
            return self

    class Smoke(paced.PacedLesson):
        def __init__(self):
            self.time, self.frame, self.mobjects = 0., 0, []
            self.camera = SimpleNamespace(fps=30)
            self.skip_animations = False
            self.out = MemoryPath()
            self.timeline = visual_timeline(data("plan.json"))
            self.cues = self.timeline["cues"]
            self.visual_events, self.sound_events = [], []
            self._open_focus, self._closed_focus = {}, []
            self.full_formula_frames, self.full_formula_events = [], []
            self.full_active, self.full_flights = {}, {}
            self._legacy_offset, self._reading_focus, self._chapter_id = None, None, None
            self._legacy_extra, self._height_step = 0., 0
            self._direct_steps, self._expansion_plays = [], []
            self.plays, self.labels = [], []

        def add(self, *objects):
            for obj in objects:
                if not any(old is obj for old in self.mobjects):
                    self.mobjects.append(obj)
            return self

        def remove(self, *objects):
            self.mobjects = [obj for obj in self.mobjects if all(obj is not old for old in objects)]
            return self

        def cn(self, text, size=32, **kwargs):
            self.labels.append(str(text))
            return gl.Rectangle(width=max(.01, min(11., len(str(text)) * .11)), height=.3,
                                fill_opacity=1, stroke_width=0)

        def formula(self, latex, size=38, **kwargs):
            self.labels.append(latex)
            return Formula(latex, font_size=size)

        def number(self, value, **kwargs):
            return Number(value, **kwargs)

    def advance(scene, dt):
        scene.frame += 1
        scene.time = scene.frame / 30
        # Execute the production FullFormulaLesson updater and portable driver
        # after each actual native animation interpolation, including waits.
        scene.update_mobjects(dt)

    def play(scene, *proto, run_time=None, rate_func=None, lag_ratio=None):
        begin = scene.time
        animations = list(map(prepare_animation, proto))
        for animation in animations:
            animation.update_rate_info(run_time, rate_func, lag_ratio)
            scene.add(animation.mobject)
            animation.begin()
        duration = max(animation.run_time for animation in animations)
        previous = 0.
        for t in scene.get_time_progression(duration):
            for animation in animations:
                animation.update_mobjects(t - previous)
                animation.interpolate(t / animation.run_time)
            advance(scene, t - previous)
            previous = t
        for animation in animations:
            animation.finish()
            animation.clean_up_from_scene(scene)
        scene.update_mobjects(0)
        scene.plays.append({"start": begin, "end": scene.time, "chapter": scene._chapter_id})

    def wait(scene, duration, **kwargs):
        for _ in scene.get_time_progression(duration):
            advance(scene, 1 / 30)

    def teardown(scene):
        validate_events(scene.timeline, {"duration": scene.time, "events": scene.visual_events})

    patcher.setattr(full, "SemanticFormula", Formula)
    patcher.setattr(landing, "SemanticFormula", Formula)
    patcher.setattr(motion, "SemanticFormula", Formula)
    patcher.setattr(full._frozen, "DecimalNumber", Number)
    patcher.setattr(gl.Scene, "play", play)
    patcher.setattr(gl.Scene, "wait", wait)
    patcher.setattr(VisualLessonScene, "tear_down", teardown)
    scene = Smoke()
    try:
        scene.construct()
        scene.tear_down()
        yield SimpleNamespace(scene=scene, module=paced)
    finally:
        patcher.undo()


def test_real_frame_clock_matches_cues_plan_and_motion_reports(native_smoke):
    scene, module = native_smoke.scene, native_smoke.module
    plan = data("plan.json")
    assert scene.time == pytest.approx(plan["duration"])
    assert list(module.CUE_BOUNDARIES) == plan["cue_boundaries"]
    chapters = [row for row in scene.full_formula_events if row["kind"] in {"chapter_begin", "chapter_end"}]
    for cue in scene.cues:
        rows = [row for row in scene.plays if row["chapter"] == cue["id"]]
        assert min(row["start"] for row in rows) == pytest.approx(cue["start"])
        assert max(row["end"] for row in rows) <= cue["start"] + cue["duration"] + 1e-6
    for row in chapters:
        cue = next(cue for cue in scene.cues if cue["id"] == row["chapter"])
        assert row["time"] == pytest.approx(cue["start"] + (cue["duration"] if row["kind"] == "chapter_end" else 0))
    portable = json.loads(scene.out.files["motion-samples.json"])
    full = json.loads(scene.out.files["full-formula-motion.json"])
    cue = next(cue for cue in scene.cues if cue["id"] == "landing")
    assert portable["duration"] == pytest.approx(cue["duration"])
    assert portable["start"] == pytest.approx(cue["start"])
    assert full["duration"] == pytest.approx(scene.time)
    assert full["cue_boundaries"] == plan["cue_boundaries"]
    assert not scene._open_focus and scene._legacy_offset is None
    assert not scene._direct_steps and not scene._expansion_plays


def test_each_algebra_has_real_move_settle_and_semantic_focus(native_smoke):
    scene = native_smoke.scene
    events = scene.full_formula_events
    begins = {row["focus"]: row for row in events if row["kind"] == "paced_step_begin"}
    ends = {row["focus"]: row for row in events if row["kind"] == "paced_step_end"}
    marks = {row["id"]: row["time"] for row in scene.visual_events}
    for identity, begin in begins.items():
        ready = marks[identity + "_ready"]
        assert ready - begin["time"] == pytest.approx(begin["motion"])
        assert ends[identity]["time"] - ready == pytest.approx(begin["hold"])
        assert any(begin["time"] < row["time"] < ready for row in scene.full_formula_frames) or identity.startswith("landing_")
    assert marks["both_landings_full_size_held"] - marks["high_ball_landed"] == pytest.approx(5)
    assert len([key for key in begins if key in native_smoke.module.HEIGHT_FOCI]) == 7
    for stage, (focus, _, _) in native_smoke.module.LANDING_STEPS.items():
        assert ends[focus]["time"] - begins[focus]["time"] >= 4.1
    report = json.loads(scene.out.files["motion-samples.json"])
    assert len(report["samples"]) > report["duration"] * 29
    for stage in ("relocated_term", "twice_height", "isolated_square"):
        moving = [row for row in report["samples"] if row["stage"] == stage and "moving" in row]
        assert {"lift", "across", "settle"} <= {row["phase"] for row in moving}
        boxes = np.array([row["moving"]["bbox"] for row in moving])
        assert np.ptp(boxes, axis=0).max() > .1
    assert all(row["local_time"] == pytest.approx(row["time"] - report["start"], abs=1e-6) for row in report["samples"])


def test_narration_intent_uses_actual_independent_windows(native_smoke):
    scene = native_smoke.scene
    windows = focus_windows({"duration": scene.time, "windows": scene._closed_focus}, scene.time)
    assert set(windows) == {row["id"] for row in data("plan.json")["focus_intents"]}
    narration = data("narration-draft.json")
    validate_narration(narration, scene.timeline, {"duration": scene.time, "windows": scene._closed_focus})
    for row in narration["segments"]:
        window = windows[row["focus"]]
        cue = next(cue for cue in scene.cues if cue["id"] == row["cue"])
        assert cue["start"] <= window["start"] < window["end"] <= cue["start"] + cue["duration"] + 1e-6
        assert row["focus"] != "prediction_space"
    assert {"landing_ground_condition", "landing_relocate", "landing_multiply_two", "landing_divide_gravity", "landing_positive_root"} <= {row["focus"] for row in narration["segments"]}
    assert "horizontal_units_orange" not in {row["focus"] for row in narration["segments"]}


def test_full_old_formulas_conditions_and_fixed_symbol_expansion_survive(native_smoke):
    scene = native_smoke.scene
    events = scene.full_formula_events
    vertical = [row["actual"]["latex"] for row in events if row["kind"] == "matching_end" and row.get("name") == "vertical"]
    assert "{0}{t}" in vertical[0] and "{0}{t}" not in vertical[1]
    assert vertical[2] == "y_1(t)=y_2(t)"
    products = next(row["formulas"] for row in events if row["kind"] == "substitute_products_end")
    assert all(r"\mathrm{m/s}\times{1}\,\mathrm{s}" in row["latex"] for row in products.values())
    assert len([row for row in events if row["kind"] == "matching_end" and row.get("name") in {"range1", "range2"}]) == 2
    expansion = next(row for row in events if row["kind"] == "local_expansion_end")
    assert expansion["actual"]["latex"] == r"R=v_x\sqrt{\frac{{2}{h}}{{g}}}"
    assert all(word in " ".join(scene.labels) for word in ("质点", "无空气阻力", "v_{y0}=0", "向上为正", "第1秒：5米", "第2秒：再落15米", "横向展开不是实际运动"))


def test_revision_and_sources_do_not_claim_render_or_inherit_approval():
    plan = data("plan.json")
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v3.json"
    assert plan["revision_mode"] == "revision"
    assert plan["revision_contract"] == "runtime/projects/projectile-paced-20261027/revision-contract.json"
    assert plan["revision_review"] == "runtime/sessions/projectile-paced-20261027/review-regression-v001.json"
    assert {"examples/projectile_paced.py", "examples/projectile_integrated.py", "examples/projectile_formula_motion_full.py",
            "examples/projectile_formula_motion.py", "outputs/sol61-visual-first-20261024-v1/candidate.py"} <= set(plan["sources"])
    assert visual_timeline(plan)["duration"] == plan["duration"]
    for row in plan["state_contracts"]:
        assert all(row.get(key) for key in ("writer", "consumers", "lifecycle", "invalidation"))
    methods = {node.name for node in ast.walk(ast.parse(SOURCE.read_text())) if isinstance(node, ast.FunctionDef)}
    assert not {"get_time", "get_time_progression", "render", "sound", "publish"} & methods
    assert "def play(" not in ast.get_source_segment(SOURCE.read_text(), next(node for node in ast.parse(SOURCE.read_text()).body if isinstance(node, ast.ClassDef) and node.name == "PacedLandingChapter"))
