"""Flat survivor group on the original full native clock, no pixel approval."""

import json
from pathlib import Path
import pytest
from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule

ROOT = Path(__file__).resolve().parents[1]


def test_native_survivor_group_full_clock_and_intact_original_audio():
    plan = json.loads((ROOT / "tests/fixtures/derivative-ch04-traceable-v009/plan.json").read_text())
    original = ROOT / "tests/fixtures/derivative-ch04-traceable-v008"
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch04_traceable_v009.py")
        import derivative_ch04_chain as base
        import manimind.components.formula_motion as fm
        def initialize(scene):
            patch.setattr(base, "SemanticFormula", fm.SemanticFormula)
        with native_run(module, module.DerivativeChainTraceableV009, plan, initialize) as scene:
            assert scene.time == pytest.approx(plan["duration"], abs=1e-6)
            survivors = [r for r in scene.motion_samples if r["kind"] == "affine_survivor_flat"]
            assert len(survivors) == 1 and survivors[0]["glyphs"] > 2
            rows = schedule(visual_timeline(plan), json.loads((original / "narration.json").read_text()),
                {"duration": scene.time, "windows": scene._closed_focus}, json.loads((original / "timings.json").read_text()))
            assert len(rows) == 8 and sum(len(r["references"]) for r in rows) == 26
            for row, expected in zip(rows, plan["intended_full_wav_placement"], strict=True):
                assert row["start"] == pytest.approx(expected["intended_start"], abs=.04)
