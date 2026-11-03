"""Native route repair checks; frozen v005 tests and media remain unchanged."""
import json
from pathlib import Path
import sys

import pytest
from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule
from test_derivative_ch07_traceable import test_real_sources_native_intermediates_and_landing as check_motion

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/derivative-ch07-traceable-v006"


def read(name):
    return json.loads((FIX / name).read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        if any(path.resolve().is_relative_to(ROOT / name) for name in ("runtime","outputs")):
            raise AssertionError("Fixture-only tests")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path,"open",guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as p:
        p.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(ROOT / "examples/derivative_ch07_traceable_v006.py")


@pytest.fixture(scope="module")
def native(lesson):
    with pytest.MonkeyPatch.context() as p:
        def initialize(scene):
            p.setattr(sys.modules["derivative_ch07_traceable"],"SemanticFormula",lesson.SemanticFormula)
            scene.created_roles = []
        class Probe(lesson.DerivativeCh07TraceableV006):
            def role_formula(self, latex, *args, **kwargs):
                result = super().role_formula(latex, *args, **kwargs)
                self.created_roles.append((latex,result))
                return result
        with native_run(lesson,Probe,read("plan.json"),initialize) as scene:
            yield scene


@pytest.mark.parametrize("stage", ["stationary_to_candidate", "domain_to_endpoints", "substitute_0", "value_0_to_column",
    "substitute_1", "value_1_to_column", "substitute_3", "value_3_to_column", "select_minimum_value",
    "minimum_position", "select_maximum_value", "maximum_position"])
def test_sources_and_motion_are_still_native(native,stage):
    check_motion(native,stage)


def test_history_retires_only_after_stationary_transfer_before_endpoint_motion(native):
    retired = next(r for r in native.motion_samples if r["kind"] == "candidate_history_retired")
    root = [r for r in native.motion_samples if r.get("stage") == "stationary_to_candidate"]
    ends = [r for r in native.motion_samples if r.get("stage") == "domain_to_endpoints"]
    assert root[-1]["time"] < retired["time"] <= ends[0]["time"]
    assert native._candidate_history == []
    minimum = next(f for latex,f in native.created_roles if latex == r"\min f=0\quad(x=1)")
    assert minimum.get_center()[1] == pytest.approx(2.8)
    assert all(r["moving"][0][1] < 1 for r in native.motion_samples if r.get("stage") in ("maximum_position","select_maximum_value"))


def test_all_original_words_references_WAVs_and_parameter_open_proof(native,lesson):
    plan = read("plan.json")
    assert read("narration.json")["units"] == read("baseline-narration.json")["units"]
    placed = schedule(visual_timeline(plan),read("narration.json"),{"duration":native.time,"windows":native._closed_focus},read("timings.json"))
    assert len(placed) == 7 and native.time == pytest.approx(322.2)
    assert sum(r["duration_seconds"] for r in placed) == pytest.approx(297.44)
    for row, old in zip(placed,plan["intended_full_wav_placement"],strict=True):
        assert abs(row["start"]-old["intended_start"]) < .04
    prior = sys.modules["derivative_ch07_extremes_v004"].DerivativeCh07ExtremesV004
    for name in ("parameter","open_interval","conditions","closing"):
        assert getattr(lesson.DerivativeCh07TraceableV006,name) is getattr(prior,name)
    assert "全域比较：左段与右支" in native.labels
    assert sum(len(u["features"]) for u in read("contract.json")["units"]) == 24
