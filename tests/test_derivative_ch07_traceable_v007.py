"""Endpoint-classification opacity in actual native motion, fixture-only."""
import json
from pathlib import Path
import sys
import pytest
from lesson_native_harness import load_lesson,native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule
from test_derivative_ch07_traceable import test_real_sources_native_intermediates_and_landing as check_motion

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"tests/fixtures/derivative-ch07-traceable-v007"


def read(name):
    return json.loads((FIX/name).read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original=Path.open
    def guard(path,*args,**kwargs):
        if any(path.resolve().is_relative_to(ROOT/name) for name in ("runtime","outputs")):
            raise AssertionError("Fixture-only tests")
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,"open",guard)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as p:
        p.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(ROOT/"examples/derivative_ch07_traceable_v007.py")


@pytest.fixture(scope="module")
def native(lesson):
    with pytest.MonkeyPatch.context() as p:
        def initialize(scene):
            p.setattr(sys.modules["derivative_ch07_traceable"],"SemanticFormula",lesson.SemanticFormula)
            scene.category_during_stationary=[]
        class Probe(lesson.DerivativeCh07TraceableV007):
            def sample(self,kind,**values):
                if kind=="traceable_roles" and values.get("stage")=="stationary_to_candidate":
                    self.category_during_stationary.append([
                        max(float(g.get_opacity()) for g in item.family_members_with_points())
                        for item in (self._endpoint_label,self._endpoint_scaffold)])
                super().sample(kind,**values)
        with native_run(lesson,Probe,read("plan.json"),initialize) as scene:
            yield scene


def test_endpoint_text_and_punctuation_are_absent_until_stationary_position_lands(native):
    assert len(native.category_during_stationary)>20
    assert all(values==[0,0] for values in native.category_during_stationary)
    show=next(r for r in native.motion_samples if r["kind"]=="endpoint_classification_revealed")
    motion=[r for r in native.motion_samples if r.get("stage")=="stationary_to_candidate"]
    assert show["time"]>motion[-1]["time"]
    assert native._endpoint_label is native._endpoint_scaffold is None


@pytest.mark.parametrize("stage",["stationary_to_candidate","domain_to_endpoints","substitute_0","value_0_to_column",
    "substitute_1","value_1_to_column","substitute_3","value_3_to_column","select_minimum_value","minimum_position",
    "select_maximum_value","maximum_position"])
def test_all_native_transfers_keep_real_visible_origins(native,stage):
    check_motion(native,stage)


def test_original_complete_audio_and_all_teaching_content_still_retained(native):
    plan=read("plan.json")
    assert read("narration.json")["units"]==read("baseline-narration.json")["units"]
    placed=schedule(visual_timeline(plan),read("narration.json"),{"duration":native.time,"windows":native._closed_focus},read("timings.json"))
    assert native.time==pytest.approx(322.2) and len(placed)==7
    assert sum(r["duration_seconds"] for r in placed)==pytest.approx(297.44)
    assert all(abs(r["start"]-o["intended_start"])<.04 for r,o in zip(placed,plan["intended_full_wav_placement"],strict=True))
    assert sum(len(u["features"]) for u in read("contract.json")["units"])==24
    assert "全域比较：左段与右支" in native.labels
