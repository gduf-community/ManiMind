"""Retired-fraction lifetime, complete native clock and original WAV checks."""

import hashlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, validate_narration

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch02-traceable-v013"
CHANGED = {"square_factor_h", "cubic_divide_h", "exp_split_power", "sine_angle_substitution"}


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch02_traceable_v012.py")
        import sys
        import manimlib as gl

        class Capture(module.DerivativeCh02TraceableV012):
            def transfer(self, identity, source, *args, **kwargs):
                result = super().transfer(identity, source, *args, **kwargs)
                if identity in self.CONSUME_FRACTIONS - self.RESTORE_GIVENS:
                    self.retired.append((identity, source))
                return result

        original_update = gl.Scene.update_mobjects

        def update(scene, dt):
            original_update(scene, dt)
            for identity, source in scene.retired:
                if source in scene.mobjects:
                    opacity = max((p.get_fill_opacity() for p in source.family_members_with_points()), default=0)
                    scene.cleanup_observations.append((identity, scene.time, opacity))

        patcher.setattr(gl.Scene, "update_mobjects", update)

        def initialize(scene):
            scene.motion_samples, scene.retired, scene.cleanup_observations = [], [], []
            for name, owner in tuple(sys.modules.items()):
                if name.startswith("derivative_ch") and owner is not None:
                    patcher.setattr(owner, "SemanticFormula", module.SemanticFormula, raising=False)

        with native_run(module, Capture, read("plan-draft.json"), initialize) as scene:
            yield scene


def test_four_old_denominators_absent_before_any_travel(native):
    for identity in CHANGED:
        rows = [r for r in native.motion_samples if r.get("transition") == identity
                and r["kind"] == "traceable_formula"]
        assert rows and rows[0]["working_source_present"]
        assert all(not r["retained"] for r in rows)
        origin = rows[0]["moving"]
        for row in rows:
            if row["working_source_present"]:
                for role, point in row["moving"].items():
                    assert point == pytest.approx(origin[role])
            if row["phase"] in {"local_operation_at_readable_source", "travel_readable_term",
                                "local_operation_at_destination", "new_syntax"}:
                assert not row["working_source_present"]


def test_original_givens_restored_only_after_complete_landing(native):
    for identity in ("exp_split_power", "sine_angle_substitution"):
        complete = [r for r in native.motion_samples if r.get("transition") == identity
                    and r["kind"] == "traceable_complete"]
        restored = [r for r in native.motion_samples if r.get("transition") == identity
                    and r["kind"] == "traceable_history"]
        assert len(complete) == len(restored) == 1
        assert restored[0]["phase"] == "given_restored_after_landing"
        assert restored[0]["time"] > complete[0]["time"]
    assert native.cleanup_observations
    assert all(opacity == 0 for _, _, opacity in native.cleanup_observations)


def test_complete_clock_focus_and_all_43_operations(native):
    plan = read("plan-draft.json")
    assert native.time == pytest.approx(plan["duration"])
    assert not native._open_focus and not native._drivers
    assert len(plan["formula_transitions"]) == 43
    assert {r["id"] for r in plan["formula_transitions"]} == {
        r["transition"] for r in native.motion_samples if r["kind"] == "traceable_complete"}


def test_full_original_voice_complete_baseline_and_graphs(native):
    plan = read("plan-draft.json")
    focus = {"duration": native.time, "windows": native._closed_focus}
    validate_narration(read("narration.json"), visual_timeline(plan), focus)
    placed = schedule(visual_timeline(plan), read("narration.json"), focus, read("timings.json"))
    assert len(placed) == 14
    for actual, intended in zip(placed, plan["intended_full_wav_placement"], strict=True):
        assert abs(actual["start"]-intended["intended_start"]) <= .07
    contract = read("contract-draft.json")
    validate_contract(contract)
    assert sum(len(u["features"]) for u in contract["units"]) == 38
    assert set(contract["assets"]) == {"selected_visual_v005"}
    old = json.loads((ROOT / "outputs/math-derivative-ch02-basics-20261102/visual-v011/chapter-motion.json").read_text())

    def measured_frames(events):
        return {(r["kind"], r.get("function"), round(r["time"]*30)): r for r in events
                if r["kind"] in {"slope_map", "log_increment_bridge"}}

    before, after = measured_frames(old["events"]), measured_frames(native.motion_samples)
    assert before.keys() == after.keys()
    for key, original in before.items():
        current = after[key]
        assert current.keys() == original.keys()
        for name, value in original.items():
            if isinstance(value, (float, int, list)):
                assert current[name] == pytest.approx(value, abs=2e-6)
            else:
                assert current[name] == value


def test_all_rendered_02_and_03_dependencies_still_frozen():
    for lesson, name in (("02", "basics"), ("03", "rules")):
        record = json.loads((ROOT / f"outputs/math-derivative-ch{lesson}-{name}-20261102/visual-v011/render.json").read_text())
        for source, digest in record["input_hashes"].items():
            assert hashlib.sha256(Path(source).read_bytes()).hexdigest() == digest
    plan = read("plan-draft.json")
    assert "examples/derivative_ch02_traceable_v011.py" in plan["sources"]
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
