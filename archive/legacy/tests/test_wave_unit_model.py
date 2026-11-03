"""Pure wave facts and non-render scene-clock contracts, never pixel approval."""

import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.meaning_units import validate_narration
from manimind.review.semantic_focus import focus_windows


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BASE = ROOT / "tests/fixtures/wave_unit"
FIXTURES = FIXTURE_BASE / "v003"
AUTHOR_AGENT = "01a1817c-7136-79a3-9ca8-6b508ab35228"
DRAFT_NAME = "narration-draft-v002.json"
MODEL_PATH = ROOT / "examples/wave_unit_model.py"
HISTORICAL_PATH = ROOT / "examples/wave_unit_visual.py"
SHARED_PATH = ROOT / "examples/wave_unit_shared.py"
SPEC = importlib.util.spec_from_file_location("tested_wave_model", MODEL_PATH)
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)
LESSONS = (
    ("wave-formation-20261028", "WaveFormationLesson"),
    ("wave-reading-20261028", "WaveReadingLesson"),
    ("wave-superposition-20261028", "WaveSuperpositionLesson"),
)
SCENE_PATHS = {
    "wave-formation-20261028": ROOT / "examples/wave_formation_visual.py",
    "wave-reading-20261028": ROOT / "examples/wave_reading_visual.py",
    "wave-superposition-20261028": ROOT / "examples/wave_superposition_visual.py",
}
PRODUCTION_PATHS = (SHARED_PATH, *SCENE_PATHS.values())
BASELINE_SCENES = {project: FIXTURES / path.name for project, path in SCENE_PATHS.items()}


def read(path):
    return json.loads((FIXTURES / path).read_text(encoding="utf-8"))


def test_model_imports_with_stdlib_and_no_manim_or_numpy():
    command = (
        "import importlib.util, sys; "
        f"s=importlib.util.spec_from_file_location('wave', {str(MODEL_PATH)!r}); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "assert 'manimlib' not in sys.modules; assert 'numpy' not in sys.modules; "
        "assert m.wave_speed()==1"
    )
    subprocess.run([sys.executable, "-I", "-S", "-c", command], check=True, capture_output=True)


@pytest.mark.parametrize("dt", [.125, .5, 1, 3.75])
def test_phase_moves_right_not_left(dt):
    for x in (0, .37, 2.1, 4, 9.2):
        for t in (.2, 1, 6.7):
            assert MODEL.harmonic(x + dt, t + dt) == pytest.approx(MODEL.harmonic(x, t), abs=1e-12)
    assert MODEL.harmonic(4 + dt, dt) == pytest.approx(1)
    if dt == .5:
        assert MODEL.harmonic(4 - dt, dt) != pytest.approx(1)


def test_fixed_material_identity_and_true_crest_position():
    for t in np.linspace(0, 20, 81):
        state = MODEL.particle_state(4, float(t))
        assert state["x_m"] == 4
        assert abs(state["y_cm"]) <= 1 + 1e-12
        assert MODEL.crest_position(4, t) == pytest.approx(4 + t)
        assert MODEL.harmonic(MODEL.crest_position(4, t), t) == pytest.approx(1)
    assert MODEL.particle_state(4, 17)["y_cm"] == pytest.approx(0, abs=1e-12)


def test_period_wavelength_frequency_and_speed_have_distinct_units():
    assert MODEL.wave_speed() == 1
    assert 1 / MODEL.PERIOD_S == .25
    for x in (.2, 1.1, 4, 8):
        for t in (.3, 1.6):
            y = MODEL.harmonic(x, t)
            assert MODEL.harmonic(x + 4, t) == pytest.approx(y)
            assert MODEL.harmonic(x, t + 4) == pytest.approx(y)
            assert MODEL.harmonic(x + 2, t) == pytest.approx(-y)
            assert MODEL.harmonic(x, t + 2) == pytest.approx(-y)
    assert MODEL.harmonic_velocity(5, 0) > 0
    assert MODEL.harmonic(5, .5) == pytest.approx(math.sqrt(2) / 2)


def test_spatial_and_temporal_slices_are_the_same_function():
    xs, ts = [0, 1, 4, 6, 8], [0, 1, 2, 4, 8]
    for t in ts:
        for x, y in MODEL.spatial_snapshot(t, xs):
            assert dict(MODEL.temporal_record(x, ts))[t] == pytest.approx(y)


def test_causal_start_is_rest_before_front_and_matches_the_steady_model():
    for t in (0, .5, 2, 4, 8):
        for x in np.linspace(t, t + 5, 11):
            assert MODEL.forming_wave(float(x), t) == 0
    assert MODEL.source_displacement(0) == 0
    assert MODEL.source_displacement(1e-6) == pytest.approx(0, abs=1e-12)
    assert MODEL.smooth_start(-1) == 0
    assert MODEL.smooth_start(2) == 1
    for x in np.linspace(0, 10, 31):
        assert MODEL.forming_wave(float(x), 12) == pytest.approx(MODEL.harmonic(float(x), 12))
    assert MODEL.forming_wave(4, 8.5) == pytest.approx(MODEL.forming_wave(2, 6.5))
    assert MODEL.forming_wave(4, 8.5) == pytest.approx(math.sqrt(2) / 2)
    with pytest.raises(ValueError):
        MODEL.forming_wave(-.1, 1)


@pytest.mark.parametrize("second", [1, -1, -.5])
def test_pulse_addition_and_traversal_keep_each_component(second):
    for t in (0, 1.5, 2.5, 3, 4, 6):
        first, other = MODEL.pulse_centers(t)
        assert first == 2 + t
        assert other == 8 - t
        for x in np.linspace(0, 10, 61):
            row = MODEL.pulse_state(float(x), t, second)
            assert row["x_m"] == x
            assert row["y_cm"] == pytest.approx(row["y1_cm"] + row["y2_cm"])
            assert row["y1_cm"] == pytest.approx(MODEL.pulse_shape(x - first))
            assert row["y2_cm"] == pytest.approx(second * MODEL.pulse_shape(x - other))
    assert MODEL.pulse_state(8, 6, second)["y_cm"] == pytest.approx(1)
    assert MODEL.pulse_state(2, 6, second)["y_cm"] == pytest.approx(second)
    assert MODEL.pulse_state(5, 3, second)["y_cm"] == pytest.approx(1 + second)
    for offset in (-1, -.4, 0, .8):
        assert MODEL.pulse_state(8 + offset, 6, second)["y1_cm"] == pytest.approx(
            MODEL.pulse_state(2 + offset, 0, second)["y1_cm"])


def test_complete_cancellation_is_not_a_zero_velocity_field():
    for x in np.linspace(0, 10, 101):
        assert MODEL.pulse_state(float(x), 3, -1)["y_cm"] == pytest.approx(0)
    left = MODEL.pulse_state(4.5, 3, -1)
    right = MODEL.pulse_state(5.5, 3, -1)
    assert left["vy_cm_s"] < 0 < right["vy_cm_s"]
    assert left["vy_cm_s"] == pytest.approx(-right["vy_cm_s"])
    assert MODEL.pulse_state(5, 3, -1)["vy_cm_s"] == 0
    for x in (4.5, 5.5):
        dt = 1e-6
        derivative = (MODEL.pulse_state(x, 3 + dt, -1)["y_cm"] -
                      MODEL.pulse_state(x, 3 - dt, -1)["y_cm"]) / (2 * dt)
        assert MODEL.pulse_state(x, 3, -1)["vy_cm_s"] == pytest.approx(derivative, rel=1e-8)


def test_pulse_support_is_exact_and_smooth_at_its_edges():
    for x in (-10, -1.3, 1.3, 10):
        assert MODEL.pulse_shape(x) == 0
        assert MODEL.pulse_gradient(x) == 0
    assert MODEL.pulse_shape(0) == 1
    assert abs(MODEL.pulse_gradient(1.3 - 1e-6)) < 1e-9


@pytest.mark.parametrize("bad", [0, -1, float("inf"), float("nan")])
def test_nonphysical_scales_are_rejected(bad):
    with pytest.raises(ValueError):
        MODEL.wave_speed(bad, 4)
    with pytest.raises(ValueError):
        MODEL.harmonic(0, 0, period_s=bad)
    with pytest.raises(ValueError):
        MODEL.pulse_shape(0, bad)


class Shape:
    """Only enough native-object protocol to execute chapter timing without GL."""
    def __init__(self, *children, **kwargs):
        self.children = list(children)
        self.center, self.updaters = np.zeros(3), []

    def __iter__(self):
        return iter(self.children)

    def __getitem__(self, index):
        return self.children[index]

    def add(self, *items):
        self.children.extend(items)
        return self

    def move_to(self, point):
        self.center = np.array(point)
        return self

    def get_center(self):
        return self.center.copy()

    def get_width(self):
        return getattr(self, "width", 1)

    def set_width(self, width):
        self.width = width
        return self

    def set_stroke(self, *args):
        return self

    def set_points_as_corners(self, points):
        assert all(len(point) == 3 and np.isfinite(point).all() for point in points)
        return self

    def set_value(self, value):
        self.value = value
        return self

    def add_updater(self, fn):
        self.updaters.append(fn)
        return self

    def clear_updaters(self):
        self.updaters.clear()
        return self


class Tracker:
    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value

    @property
    def animate(self):
        return SimpleNamespace(set_value=lambda value: ("tracker", self, value))


class DryRuntime:
    """Simulated clock/events only. Does not create font, TeX, video or evidence."""
    def __init__(self, plan):
        self.timeline = visual_timeline(plan)
        self.cues = self.timeline["cues"]
        self.camera = SimpleNamespace(fps=30)
        self.now = 0.
        self._subtitle_driver = Shape()
        self.mobjects = [self._subtitle_driver]
        self.events, self.windows, self.open_focus, self.physics_intervals = [], [], {}, []
        self.labels, self.focus_start_labels, self.focus_end_labels = [], {}, {}

    def cn(self, *args, **kwargs):
        obj = Shape()
        obj.text = str(args[0])
        self.labels.append(obj)
        return obj

    formula = cn
    number = cn

    def add(self, *items):
        for item in items:
            if item not in self.mobjects:
                self.mobjects.append(item)

    def remove(self, item):
        if item in self.mobjects:
            self.mobjects.remove(item)
        for child in item.children:
            if isinstance(child, Shape):
                self.remove(child)

    def get_time(self):
        return self.now

    def visible_labels(self):
        result = set()

        def visit(obj):
            if hasattr(obj, "text"):
                result.add(obj.text)
            for child in obj.children:
                if isinstance(child, Shape):
                    visit(child)

        for obj in self.mobjects:
            visit(obj)
        return result

    def play(self, *actions, run_time=1, **kwargs):
        begin = self.now
        tracks = []
        for kind, obj, target in actions:
            if kind == "tracker":
                tracks.append((obj, obj.value, target))
                self.physics_intervals.append((run_time, target - obj.value, kwargs.get("rate_func")))
            elif kind == "out":
                self.remove(obj)
            else:
                self.add(obj)
        steps = max(1, round(run_time * 2))
        for step in range(1, steps + 1):
            self.now = begin + run_time * step / steps
            for obj, source, target in tracks:
                obj.value = source + (target - source) * step / steps
            for obj in list(self.mobjects):
                for updater in list(obj.updaters):
                    updater(obj)

    def wait(self, seconds):
        self.play(run_time=seconds)

    def until(self, target):
        assert self.now <= target + 1e-7, (self.now, target)
        if target > self.now + 1e-7:
            self.wait(target - self.now)
        self.now = target

    def mark(self, name):
        self.events.append({"id": name, "time": self.now})

    def focus_begin(self, name):
        assert name not in self.open_focus
        assert name not in {row["id"] for row in self.windows}
        self.open_focus[name] = self.now
        self.focus_start_labels[name] = self.visible_labels()

    def focus_end(self, name):
        self.windows.append({"id": name, "start": self.open_focus.pop(name), "end": self.now})
        self.focus_end_labels[name] = self.visible_labels()


@pytest.fixture(scope="module")
def dry_scenes():
    namespace = {"UnderstandingScene": DryRuntime, "model": MODEL, "np": np,
                 "INK": "white", "WAVE": "green", "PARTICLE": "yellow", "SECOND": "pink",
                 "MUTED": "grey", "GUIDE": "grey", "linear": "linear", "ValueTracker": Tracker}
    for name in ("Arrow", "Circle", "Dot", "Group", "Line", "VMobject", "VGroup"):
        namespace[name] = Shape
    for name, kind in (("FadeIn", "in"), ("FadeOut", "out"), ("ShowCreation", "in")):
        namespace[name] = lambda obj, kind=kind: (kind, obj, None)
    for path in (SHARED_PATH, *BASELINE_SCENES.values()):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    result = {}
    for project, name in LESSONS:
        plan = read(f"{project}/plan.json")
        scene = namespace[name](plan)
        scene.construct()
        result[project] = scene
    return result


@pytest.mark.parametrize("project,scene_class", LESSONS)
def test_chapter_events_focuses_and_continuous_narration_contract(dry_scenes, project, scene_class):
    scene = dry_scenes[project]
    plan = read(f"{project}/plan.json")
    narration = read(f"{project}/{DRAFT_NAME}")
    assert scene.get_time() == plan["duration"] == sum(scene.durations)
    assert not scene.open_focus
    validate_events(scene.timeline, {"duration": scene.now, "events": scene.events})
    focuses = {"duration": scene.now, "windows": scene.windows}
    windows = focus_windows(focuses, scene.now)
    validate_narration(narration, scene.timeline, focuses)
    expected = {row["id"]: row["cue"] for row in plan["focus_intents"]}
    assert set(windows) == set(expected)
    cues = {row["id"]: row for row in scene.cues}
    for identity, window in windows.items():
        cue = cues[expected[identity]]
        assert cue["start"] <= window["start"] < window["end"] <= cue["start"] + cue["duration"]
        assert window["end"] - window["start"] < cue["duration"]
    for unit in narration["units"]:
        assert "".join(ref["text"] for ref in unit["references"]) == unit["text"]
        for ref in unit["references"]:
            assert expected[ref["focus"]] == unit["cue"]
    assert {unit["cue"] for unit in narration["units"]} == set(cues)
    assert plan["scene_class"] == scene_class
    assert all(0 <= moment < scene.now for moment in plan["review_times"])
    for render_seconds, physical_seconds, rate in scene.physics_intervals:
        assert render_seconds == pytest.approx(physical_seconds)
        assert rate == "linear"


@pytest.mark.parametrize("project,scene_class", LESSONS)
def test_explicit_followed_context_and_model_source_bindings(tmp_path, project, scene_class):
    from manimind.curriculum import verify_context, write_context

    plan = read(f"{project}/plan.json")
    assert plan["revision_mode"] == "fresh"
    assert plan["scene"] == str(SCENE_PATHS[project].relative_to(ROOT))
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v4-unit.json"
    assert plan["lesson_context"] == f"runtime/projects/{project}/context-v003.json"
    # Rebuild provenance under a new root; archived machine-specific context
    # paths are deliberately not fixtures and no original runtime is read.
    unit_prefix = "runtime/projects/wave-unit-20261028/"
    unit_path = tmp_path / unit_prefix / "unit.json"
    unit_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "unit.json", unit_path)
    catalogue_path = tmp_path / read("unit.json")["catalogue"]
    catalogue_path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / read("unit.json")["catalogue"], catalogue_path)
    context_path = tmp_path / plan["lesson_context"]
    write_context(unit_path, project, context_path, tmp_path)
    context = verify_context(context_path, tmp_path)
    assert context["current_lesson"]["project_id"] == project
    assert context["current_lesson"]["catalogue_ids"] == plan["catalogue_ids"]
    assert {"examples/wave_unit_shared.py", "examples/wave_unit_model.py", plan["lesson_context"],
            "runtime/projects/wave-unit-20261028/unit.json", "docs/curricula/high-school-physics-v0.1.csv",
            "src/manimind/curriculum.py"} <= set(plan["sources"])
    for source in plan["sources"]:
        if source == plan["lesson_context"]:
            assert context_path.is_file()
        elif source.startswith(unit_prefix):
            assert (FIXTURES / source.removeprefix(unit_prefix)).is_file()
        else:
            assert not source.startswith("runtime/")
            assert (ROOT / source).is_file()
    assert not any(source.endswith("/wave_model.py") for source in plan["sources"])
    assert not plan["production_boundary"]["rendered"]


def test_scene_only_uses_the_tracked_model_not_runtime_executable():
    source = SHARED_PATH.read_text(encoding="utf-8")
    assert "import wave_unit_model as model" in source
    assert "wave_model.py" not in source
    assert "runtime/projects" not in source
    for path in SCENE_PATHS.values():
        text = path.read_text(encoding="utf-8")
        assert "from wave_unit_shared import" in text
        assert "wave_unit_visual" not in text
        assert "runtime/projects" not in text
    assert "manimlib" not in MODEL_PATH.read_text(encoding="utf-8")


def test_declared_review_times_sample_hard_motion_before_during_after(dry_scenes):
    # The inspection tool also adds focus/cue samples. These explicit points
    # ensure fast transitions are not lost in a coarse contact sheet.
    targets = {
        "wave-formation-20261028": ("contrast_mid", "disturbance_reaches_four", "period_half", "formation_answer_motion"),
        "wave-reading-20261028": ("record_quarter", "record_half", "record_cycle", "speed_mid", "direction_shifted"),
        "wave-superposition-20261028": ("positive_collision", "through_mid", "zero_displacement", "opposite_reappearing", "unequal_collision"),
    }
    for project, names in targets.items():
        moments = read(f"{project}/plan.json")["review_times"]
        events = {row["id"]: row["time"] for row in dry_scenes[project].events}
        for name in names:
            when = events[name]
            assert any(when - 1.01 <= moment < when for moment in moments), (project, name, "before", when)
            assert any(abs(moment - when) <= .51 for moment in moments), (project, name, "during", when)
            assert any(when < moment <= when + 1.51 for moment in moments), (project, name, "after", when)


def test_actual_author_identity_is_explicit_in_every_authored_data_snapshot():
    for project, _ in LESSONS:
        for name in ("plan.json", DRAFT_NAME):
            value = read(f"{project}/{name}")
            assert value["author_agent"] == value["author_context"] == AUTHOR_AGENT
    brief = read("scientific-brief.json")
    assert brief["author_agent"] == brief["writer"] == AUTHOR_AGENT


def test_tracked_snapshots_match_the_frozen_source_and_are_not_approval():
    freeze = read("source-freeze-v003.json")
    assert freeze["author_agent"] == AUTHOR_AGENT
    assert freeze["author_context"] == AUTHOR_AGENT
    assert freeze["status"] == "frozen_for_lead_silent_render_not_reviewed"
    assert freeze["aggregate_is_not_a_render_dependency"] is True
    files = {str(path.relative_to(ROOT)): path for path in (SHARED_PATH, MODEL_PATH)}
    files.update({str(path.relative_to(ROOT)): BASELINE_SCENES[project]
                  for project, path in SCENE_PATHS.items()})
    files.update({f"runtime/projects/wave-unit-20261028/{name}": FIXTURES / name
                  for name in ("unit.json", "scientific-brief.json", "teaching-design.md")})
    for project, _ in LESSONS:
        files[f"runtime/projects/{project}/plan.json"] = FIXTURES / project / "plan.json"
    for source, path in files.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == freeze["visual_input_sha256"][source]
    for project, _ in LESSONS:
        path = FIXTURES / project / DRAFT_NAME
        source = f"runtime/projects/{project}/{DRAFT_NAME}"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == freeze["narration_draft_sha256"][source]
        assert read(f"{project}/{DRAFT_NAME}")["status"] == "intent_draft_not_approved_not_audio_timed"


def test_each_frozen_watch_manifest_matches_the_real_renderer_dependency_set():
    freeze = read("source-freeze-v003.json")
    actual = lesson_watch_sets()
    for row in freeze["lessons"]:
        project = row["project_id"]
        path = FIXTURES / project / "watch-v003.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["watch_manifest_sha256"]
        watch = read(f"{project}/watch-v003.json")
        assert set(watch["visual_input_sha256"]) == actual[project]
        assert set(watch["renderer_watch_sources"]) | {watch["plan"]} == actual[project]
        assert watch["visual_input_sha256"] == freeze["per_lesson_visual_input_sha256"][project]
        assert watch["narration_draft"] == f"runtime/projects/{project}/{DRAFT_NAME}"
        assert watch["author_context"] == watch["author_agent"] == AUTHOR_AGENT


def test_v003_preserves_model_intact_text_and_historical_aggregate():
    old = json.loads((FIXTURE_BASE / "v002/source-freeze-v002.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(HISTORICAL_PATH.read_bytes()).hexdigest() == old["visual_input_sha256"]["examples/wave_unit_visual.py"]
    for project, _ in LESSONS:
        before = json.loads((FIXTURE_BASE / "v002" / project / "plan.json").read_text(encoding="utf-8"))
        after = read(f"{project}/plan.json")
        assert after.pop("narration_draft") == f"runtime/projects/{project}/{DRAFT_NAME}"
        after["scene"] = before["scene"]
        after["sources"].remove("examples/wave_unit_shared.py")
        if project == "wave-superposition-20261028":
            assert after["duration"] == before["duration"] + 6
            for old_cue, new_cue in zip(before["cues"], after["cues"], strict=True):
                if old_cue["id"] == "cancellation":
                    assert new_cue["duration"] == old_cue["duration"] + 6
                    assert new_cue["learning_purpose"] == old_cue["learning_purpose"]
                    assert {row["id"] for row in new_cue["anchors"]} == {row["id"] for row in old_cue["anchors"]} | {"flat_result_ready"}
                else:
                    assert old_cue == new_cue
            assert {row["id"] for row in after["focus_intents"]} == {row["id"] for row in before["focus_intents"]} | {"flat_result"}
            for field in ("duration", "cues", "focus_intents", "review_times"):
                after[field] = before[field]
        assert after == before
        old_draft = json.loads((FIXTURE_BASE / "v002" / project / "narration-draft-v001.json").read_text(encoding="utf-8"))
        new_draft = read(f"{project}/{DRAFT_NAME}")
        assert [(u["id"], u["cue"], u["text"]) for u in new_draft["units"]] == [
            (u["id"], u["cue"], u["text"]) for u in old_draft["units"]]
        for old_unit, new_unit in zip(old_draft["units"], new_draft["units"], strict=True):
            if old_unit["id"] != "S04":
                assert old_unit["references"] == new_unit["references"]
    assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == old["visual_input_sha256"]["examples/wave_unit_model.py"]
    for name in ("scientific-brief.json", "teaching-design.md", "unit.json"):
        assert (FIXTURES / name).read_bytes() == (FIXTURE_BASE / "v002" / name).read_bytes()


def test_every_dot_declares_its_actual_fill_not_only_a_color_fallback():
    dots = [node for path in PRODUCTION_PATHS
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == "Dot"]
    assert len(dots) == 6
    for dot in dots:
        keywords = {entry.arg: entry.value for entry in dot.keywords}
        assert "fill_color" in keywords
        assert "color" not in keywords


@pytest.mark.parametrize("end,x_name", [(10, r"x\,(\mathrm m)"), (8, r"t\,(\mathrm s)")])
def test_axis_name_has_space_after_last_tick_and_stays_in_frame(dry_scenes, monkeypatch, end, x_name):
    class SizedShape(Shape):
        def __init__(self, width):
            super().__init__()
            self.width = width

        def get_width(self):
            return self.width

    def put(text, x, y, **kwargs):
        width = .63 if "mathrm" in text else .23
        return SizedShape(min(width, kwargs.get("width", width))).move_to([x, y, 0])

    scene = dry_scenes["wave-reading-20261028"]
    monkeypatch.setattr(scene, "put", put)
    labels = scene.axes(scene.point, end, x_name=x_name)[1]
    name = labels[0]
    tick = labels[2 + list(range(0, end + 1, 2)).index(end)]
    left = name.get_center()[0] - name.get_width() / 2
    right = name.get_center()[0] + name.get_width() / 2
    tick_right = tick.get_center()[0] + tick.get_width() / 2
    assert left - tick_right > .2
    assert right < 7


def test_split_preserves_formation_and_shared_runtime_methods_exactly():
    def definition(path, name):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return ast.dump(next(node for node in tree.body if getattr(node, "name", None) == name), include_attributes=False)

    assert definition(SHARED_PATH, "WaveLessonBase") == definition(HISTORICAL_PATH, "WaveLessonBase")
    assert definition(SHARED_PATH, "polyline") == definition(HISTORICAL_PATH, "polyline")
    assert definition(BASELINE_SCENES["wave-formation-20261028"], "WaveFormationLesson") == definition(HISTORICAL_PATH, "WaveFormationLesson")


def test_reading_time_and_distance_labels_are_spatially_separate(dry_scenes):
    project = "wave-reading-20261028"
    scene = type(dry_scenes[project])(read(f"{project}/plan.json"))
    scene.drivers, scene.motion_samples = [], []
    scene.speed()
    time = next(obj for obj in scene.labels if obj.text == r"\Delta t=T=4\,\mathrm s")
    distance = next(obj for obj in scene.labels if obj.text == r"\Delta x=\lambda=4\,\mathrm m")
    # Conservative widths; native Tex bounds are also checked before handoff.
    assert distance.get_center()[0] - 1.2 - (time.get_center()[0] + 1.2) > .5


def test_overlap_sum_and_velocity_caption_expire_before_time_resumes(dry_scenes):
    scene = dry_scenes["wave-superposition-20261028"]
    equation = r"(+1)+(-0.5)=+0.5\,\mathrm{cm}"
    caption = "箭头：这一刻质点的速度方向"
    assert equation in scene.focus_end_labels["unequal_test"]
    assert equation not in scene.focus_start_labels["unequal_pass"]
    assert equation not in scene.focus_end_labels["unequal_pass"]
    assert caption in scene.focus_start_labels["zero_not_rest"]
    assert caption not in scene.focus_start_labels["opposite_pass"]
    assert caption not in scene.focus_end_labels["opposite_pass"]


def test_s04_flat_result_has_its_own_hold_and_exact_reference_text(dry_scenes):
    scene = dry_scenes["wave-superposition-20261028"]
    windows = {row["id"]: row for row in scene.windows}
    assert windows["opposite_approach"]["end"] == 99
    assert windows["flat_result"] == {"id": "flat_result", "start": 99, "end": 105}
    assert windows["zero_not_rest"]["start"] == 106
    assert windows["opposite_pass"]["start"] == 116
    assert "箭头：这一刻质点的速度方向" not in scene.focus_start_labels["flat_result"]
    samples = [row for row in scene.motion_samples if row["kind"] == "pulses" and 99 < row["render_s"] < 105]
    assert samples and all(row["physical_s"] == 3 for row in samples)
    assert all(probe["y_cm"] == 0 for row in samples for probe in row["probes"])
    unit = next(row for row in read(f"wave-superposition-20261028/{DRAFT_NAME}")["units"] if row["id"] == "S04")
    refs = {ref["id"]: ref for ref in unit["references"]}
    assert refs["r2a"] == {"id": "r2a", "focus": "opposite_approach", "text": "相遇时，同处一个正位移、一个负位移，逐渐抵消；"}
    assert refs["r2b"] == {"id": "r2b", "focus": "flat_result", "text": "完全重合的一刻，绳形竟然平直了。"}
    assert "".join(ref["text"] for ref in unit["references"]) == unit["text"]


def lesson_watch_sets():
    from manimind.postproduce.understanding_render import sources

    return {project: {str(path.relative_to(ROOT)) for path in sources(read(f"{project}/plan.json"))}
                     | {f"runtime/projects/{project}/plan.json"}
            for project, _ in LESSONS}


def test_each_watch_set_contains_only_its_own_lesson_and_shared_sources():
    watches = lesson_watch_sets()
    for project, paths in watches.items():
        assert str(SCENE_PATHS[project].relative_to(ROOT)) in paths
        assert "examples/wave_unit_shared.py" in paths
        assert "examples/wave_unit_model.py" in paths
        assert "examples/wave_unit_visual.py" not in paths
        assert not any("source-freeze" in path or "watch-v" in path for path in paths)
        for other, _ in LESSONS:
            if other != project:
                assert str(SCENE_PATHS[other].relative_to(ROOT)) not in paths
                assert not any(path.startswith(f"runtime/projects/{other}/") for path in paths)


def test_local_imports_are_explicitly_bound_without_historical_or_sibling_scenes():
    for project, paths in lesson_watch_sets().items():
        for source in (SHARED_PATH, SCENE_PATHS[project]):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            modules = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.append(node.module)
            local = {f"examples/{name}.py" for name in modules if name.startswith("wave_")}
            assert local <= paths
            assert local <= {"examples/wave_unit_shared.py", "examples/wave_unit_model.py"}


def test_synthetic_single_lesson_hold_change_invalidates_only_its_own_watch(tmp_path):
    # These are temporary hash probes, not executed retimed scenes or edits to
    # any production source. The real renderer's watch sets are used unchanged.
    watches = lesson_watch_sets()
    contexts = {read(f"{project}/plan.json")["lesson_context"] for project, _ in LESSONS}
    for source in set.union(*watches.values()):
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        if source in contexts:
            continue
        if source.startswith("runtime/projects/wave-unit-20261028/"):
            content = (FIXTURES / Path(source).name).read_bytes()
        elif source.startswith("runtime/projects/"):
            parts = Path(source).parts
            assert parts[3] == "plan.json"
            content = (FIXTURES / parts[2] / parts[3]).read_bytes()
        else:
            content = (ROOT / source).read_bytes()
        target.write_bytes(content)
    from manimind.curriculum import write_context
    for project, _ in LESSONS:
        plan = read(f"{project}/plan.json")
        write_context(tmp_path / "runtime/projects/wave-unit-20261028/unit.json", project,
                      tmp_path / plan["lesson_context"], tmp_path)

    def hashes(project):
        return {source: hashlib.sha256((tmp_path / source).read_bytes()).hexdigest() for source in watches[project]}

    before = {project: hashes(project) for project in watches}
    for project, _ in LESSONS:
        source = tmp_path / SCENE_PATHS[project].relative_to(ROOT)
        original = source.read_bytes()
        tree = ast.parse(original.decode("utf-8"))
        hold = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr in {"wait", "at_audio", "until"}
                    and node.args and (isinstance(node.args[0], ast.Constant)
                        or isinstance(node.args[0], ast.BinOp) and isinstance(node.args[0].right, ast.Constant)))
        delay = hold.args[0] if isinstance(hold.args[0], ast.Constant) else hold.args[0].right
        delay.value += .25
        source.write_text(ast.unparse(tree), encoding="utf-8")
        assert [name for name in watches if hashes(name) != before[name]] == [project]
        source.write_bytes(original)
    shared = tmp_path / "examples/wave_unit_shared.py"
    shared.write_bytes(shared.read_bytes() + b"\n# temporary shared-input hash probe\n")
    assert {name for name in watches if hashes(name) != before[name]} == set(watches)
