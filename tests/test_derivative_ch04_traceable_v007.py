"""Two local correction checks; no production reads or editorial claims."""

import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch04-traceable-v007"


def read(name):
    return json.loads((FIXTURE / name).read_text())


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch04_traceable_v007.py")
        import derivative_ch04_chain as base
        import manimind.components.formula_motion as fm
        real_formula = fm.SemanticFormula

        class Probe(module.DerivativeChainTraceableV007):
            def semantic(self, latex, tokens, **kwargs):
                real_formula(latex, tokens=tokens, colors=kwargs.get("colors"))
                return super().semantic(latex, tokens, **kwargs)

        def initialize(scene):
            patch.setattr(base, "SemanticFormula", fm.SemanticFormula)

        with native_run(module, Probe, read("plan.json"), initialize) as scene:
            yield scene


def test_same_clock_all_intact_wavs_and_references(native):
    plan = read("plan.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-6)
    result = schedule(visual_timeline(plan), read("narration.json"),
        {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))
    assert len(result) == 8 and sum(len(r["references"]) for r in result) == 26
    for row, intended in zip(result, plan["intended_full_wav_placement"], strict=True):
        assert row["start"] == pytest.approx(intended["intended_start"], abs=.04)


def test_only_two_transfers_use_active_rows_not_retained_copies(native):
    repairs = [r for r in native.motion_samples if r["kind"] == "active_replacement"]
    assert {r["role"] for r in repairs} == {"subtract_affine_states", "collect_4_times_3"}
    assert len(repairs) == 2
    assert len([r for r in native.motion_samples if r["kind"] == "source_copy"]) == 15
    assert not native._open_focus
