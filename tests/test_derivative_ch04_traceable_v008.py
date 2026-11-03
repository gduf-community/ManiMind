"""Native semantic cancellation and intact-audio checks; never pixel approval."""

import json
from pathlib import Path
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch04-traceable-v008"


def read(name):
    return json.loads((FIXTURE / name).read_text())


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch04_traceable_v008.py")
        import derivative_ch04_chain as base
        import manimind.components.formula_motion as fm
        real_formula = fm.SemanticFormula
        class Probe(module.DerivativeChainTraceableV008):
            def semantic(self, latex, tokens, **kwargs):
                real_formula(latex, tokens=tokens, colors=kwargs.get("colors"))
                return super().semantic(latex, tokens, **kwargs)
        def initialize(scene):
            patch.setattr(base, "SemanticFormula", fm.SemanticFormula)
        with native_run(module, Probe, read("plan.json"), initialize) as scene:
            yield scene


def test_exact_clock_wavs_references_and_a_zero_case(native):
    p = read("plan.json")
    assert native.time == pytest.approx(p["duration"], abs=1e-6)
    rows = schedule(visual_timeline(p), read("narration.json"),
        {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))
    assert len(rows) == 8 and sum(len(r["references"]) for r in rows) == 26
    for got, intended in zip(rows, p["intended_full_wav_placement"], strict=True):
        assert got["start"] == pytest.approx(intended["intended_start"], abs=.04)
    assert "f(b) 有定义时，这是常数函数，导数为 0" in native.labels


def test_expands_then_cancels_two_pairs_without_whole_row_replacement(native):
    expand = [r for r in native.motion_samples if r["kind"] == "affine_expand"]
    cancel = [r for r in native.motion_samples if r["kind"] == "affine_cancel_pair"]
    assert len(expand) == 1 and [r["pair"] for r in cancel] == ["ax", "b"]
    assert expand[0]["time"] < cancel[0]["time"] < cancel[1]["time"]
    assert [r["role"] for r in native.motion_samples if r["kind"] == "active_replacement"] == ["collect_4_times_3"]
    assert not native._open_focus
