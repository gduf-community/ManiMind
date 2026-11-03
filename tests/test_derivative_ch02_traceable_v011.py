"""Native route/schedule checks; actual new pixels remain unrendered."""

import hashlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, validate_narration

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch02-traceable-v012"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch02_traceable_v011.py")
        import derivative_ch02_traceable as previous
        import derivative_ch02_traceable_v010 as prior
        import derivative_ch02_basics as original
        import derivative_chapter_shared as shared

        def initialize(scene):
            scene.motion_samples = []
            for owner in (previous, prior, original, shared):
                patcher.setattr(owner, "SemanticFormula", module.SemanticFormula, raising=False)

        with native_run(module, module.DerivativeCh02TraceableV011, read("plan-draft.json"), initialize) as scene:
            yield scene


def test_complete_clock_and_all_43_operations(native):
    plan = read("plan-draft.json")
    assert native.time == pytest.approx(plan["duration"])
    assert not native._open_focus and not native._drivers
    assert {r["id"] for r in plan["formula_transitions"]} == {
        r["transition"] for r in native.motion_samples if r["kind"] == "traceable_complete"}


def test_factor_crosses_only_in_a_lower_lane(native):
    rows = [r for r in native.motion_samples if r.get("transition") == "log_factor_exponential"
            and r["kind"] == "traceable_formula"]
    crossing = [r for r in rows if r["phase"] == "factor_crosses_below_waiting_increment"]
    assert crossing
    for row in crossing:
        assert row["moving"]["factor"][1] == pytest.approx(-.95)
        assert row["bounds"]["factor"][3] < row["bounds"]["increment"][2]
    phases = list(dict.fromkeys(r["phase"] for r in rows))
    assert phases.index("factor_lands_left_of_increment") < phases.index("local_exponential_factorization")
    assert phases[-1] == "new_syntax"


def test_base_terms_depart_vertically_before_crossing(native):
    rows = [r for r in native.motion_samples if r.get("transition") == "log_base_difference"
            and r["kind"] == "traceable_gather"]
    for identity in ("left_k", "right_k", "old"):
        crossing = [r for r in rows if r["active_role"] == identity
                    and r["phase"] == "cross_below_retained_definition"]
        assert crossing
        index = next(i for i, role in enumerate(crossing[0]["roles"]) if role[1] == identity)
        assert all(r["moving"][index][1] == pytest.approx(.8) for r in crossing)


def test_full_original_voice_contract_and_models(native):
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
    graph = [r for r in native.motion_samples if r["kind"] == "slope_map"]
    assert {r["function"] for r in graph} == {"square", "constant", "identity", "cube", "reciprocal", "root", "exp", "log", "sin", "cos"}
    old = json.loads((ROOT / "outputs/math-derivative-ch02-basics-20261102/visual-v010/chapter-motion.json").read_text())

    def measured_frames(events):
        # GL emits duplicate zero-dt updater observations at animation boundaries.
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


def test_rendered_02_and_03_sources_permanently_frozen():
    for lesson, name in (("02", "basics"), ("03", "rules")):
        record = json.loads((ROOT / f"outputs/math-derivative-ch{lesson}-{name}-20261102/visual-v010/render.json").read_text())
        for source, digest in record["input_hashes"].items():
            if "/examples/" in source:
                assert hashlib.sha256(Path(source).read_bytes()).hexdigest() == digest
    plan = read("plan-draft.json")
    assert "examples/derivative_ch02_traceable_v010.py" in plan["sources"]
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
