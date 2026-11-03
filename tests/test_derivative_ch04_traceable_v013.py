"""Run the exact diagnostic construct, including the hyphenated cue entry."""

import json
from pathlib import Path

from lesson_native_harness import load_lesson, native_run

ROOT = Path(__file__).resolve().parents[1]


def test_probe_runs_same_one_change_method_and_full_unchanged_cue(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/"examples"))
    module = load_lesson(ROOT/"examples/derivative_ch04_traceable_v013.py")
    from derivative_ch04_traceable_v012 import DerivativeChainTraceableV012
    assert module.DerivativeChainStateProbeV013.one_change is DerivativeChainTraceableV012.one_change
    assert module.DerivativeChainTraceableV013.one_change is DerivativeChainTraceableV012.one_change
    plan = json.loads((ROOT/"tests/fixtures/derivative-ch04-traceable-v013/probe-plan.json").read_text())
    with native_run(module,module.DerivativeChainStateProbeV013,plan) as scene:
        assert abs(scene.time-39.5)<1e-6
        roles = [r for r in scene.motion_samples if r["kind"] == "transfer_display_roles"]
        assert roles and all(r["base_reference_present"] for r in roles)
        assert roles[-1]["roles"] == ["ready","ready","ready"]
        assert roles[-1]["numeric_shown"] == [True,True,True]
        assert {r["phase"] for r in roles} == {"input","inner","outer"}
        assert len(scene._closed_focus)==4
