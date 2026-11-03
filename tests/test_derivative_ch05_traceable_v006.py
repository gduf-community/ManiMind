"""Fixture-only CH05 caption-lane checks; never replace actual PNG review."""
import json
from pathlib import Path
import sys

import pytest
from lesson_native_harness import load_lesson,native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule
from test_derivative_ch05_traceable import test_real_sources_intermediate_motion_and_destinations as check_motion

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/derivative-ch05-traceable-v006"


def read(name):
    return json.loads((FIX / name).read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original = Path.open

    def guarded(path,*args,**kwargs):
        if any(path.resolve().is_relative_to(ROOT / name) for name in ("runtime","outputs")):
            raise AssertionError("Fixture-only tests")
        return original(path,*args,**kwargs)

    monkeypatch.setattr(Path,"open",guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as p:
        p.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(ROOT / "examples/derivative_ch05_traceable_v006.py")


@pytest.fixture(scope="module")
def native(lesson):
    with pytest.MonkeyPatch.context() as p:
        def initialize(scene):
            p.setattr(sys.modules["derivative_ch05_traceable"],"SemanticFormula",lesson.SemanticFormula)
            p.setattr(sys.modules["derivative_ch05_monotonicity"],"SemanticFormula",lesson.SemanticFormula)
            scene.captions = {}
        class Probe(lesson.DerivativeCh05TraceableV006):
            def label(self,text,*args,**kwargs):
                result = super().label(text,*args,**kwargs)
                if text.startswith("中值定理："):
                    self.captions["MVT"] = result
                return result

            def put(self,latex,*args,**kwargs):
                result = super().put(latex,*args,**kwargs)
                if latex == r"f'(c)>0,\quad b-a>0":
                    self.captions["positive"] = result
                return result
        with native_run(lesson,Probe,read("plan.json"),initialize) as scene:
            yield scene


@pytest.mark.parametrize("stage",["negative_factor_to_zero","positive_factor_to_zero","negative_root_to_boundary",
    "positive_root_to_boundary","left_sign_factors","middle_sign_factors","right_sign_factors",
    "witness_to_fb","witness_to_fa","witness_to_b","witness_to_a","witness_to_dc",
    "difference_to_product","slope_to_product","positive_delta_to_product","positive_product_to_difference",
    "difference_to_left_value","difference_to_right_value"])
def test_original_scientific_role_motions_unmodified(native,stage):
    check_motion(native,stage)


def test_only_two_captions_leave_right_hand_activity_lanes(native,lesson):
    assert native.captions["MVT"].get_center() == pytest.approx([-3.55,2.65,0])
    assert native.captions["positive"].get_center() == pytest.approx([-3.55,-2.35,0])
    assert native.captions["MVT"].get_right()[0] < 0
    assert native.captions["positive"].get_right()[0] < 0
    for stage in ("slope_to_product","positive_product_to_difference"):
        samples = [r for r in native.motion_samples if r.get("stage") == stage]
        assert all(p[0] > 0 for row in samples for p in row["moving"])
    assert native._path_positive_reminder is None
    assert any(r["kind"] == "path_caption_retired" for r in native.motion_samples)
    prior = sys.modules["derivative_ch05_traceable"].DerivativeCh05Traceable
    for name in ("construct","signs","interval","transfer_roles","plots","disconnected_domain"):
        assert getattr(lesson.DerivativeCh05TraceableV006,name) is getattr(prior,name)


def test_complete_original_text_references_WAVs_and_all_v004_features(native):
    plan = read("plan.json")
    assert read("narration.json")["units"] == read("baseline-narration.json")["units"]
    placed = schedule(visual_timeline(plan),read("narration.json"),{"duration":native.time,"windows":native._closed_focus},read("timings.json"))
    assert native.time == pytest.approx(371.3) and len(placed) == 8
    assert sum(row["duration_seconds"] for row in placed) == pytest.approx(343.2)
    assert sum(len(u["features"]) for u in read("contract.json")["units"]) == 20
    for row,old in zip(placed,plan["intended_full_wav_placement"],strict=True):
        assert abs(row["start"]-old["intended_start"]) < .04
