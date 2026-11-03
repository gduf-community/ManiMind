"""Actual native state checks; no production reads, audio calls or pixel claims."""

import copy
import importlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/derivative-ch04-chain-v003"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_settled_output_delta_is_visible_before_focus_closes_with_same_clock(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "examples"))
    new = load_lesson(ROOT / "examples/derivative_ch04_chain_v005.py")
    old = importlib.import_module("derivative_ch04_chain_v003")
    base = importlib.import_module("derivative_ch04_chain")
    before = read("plan.json")
    after = copy.deepcopy(before)
    for cue in after["cues"]:
        cue["heading"] = new.SCOPE_HEADINGS.get(cue["id"], cue["heading"])
        if cue["id"] == "one-change":
            cue["stage_times"]["0.76"] = 22.3
            cue["animation_starts"]["0.76"] = 21.9
    capture = {}

    class Probe(new.DerivativeChainLessonV005):
        def focus_end(self, identity):
            if identity == "outer_change":
                formulas = [node for mob in self.mobjects for node in mob.get_family()
                            if hasattr(node, "get_tex") and node.get_tex() == r"\Delta y=2.793861"]
                capture["delta_opacity_at_close"] = max(float(f.get_opacity()) for f in formulas)
            super().focus_end(identity)

    observed = []
    for module, scene_class, plan in ((old, old.DerivativeChainLessonV003, before), (new, Probe, after)):
        with pytest.MonkeyPatch.context() as patcher:
            def initialize(scene):
                patcher.setattr(base, "SemanticFormula", module.SemanticFormula)

            with native_run(module, scene_class, plan, initialize) as scene:
                placement = schedule(visual_timeline(plan), read("narration.json"),
                    {"duration": scene.time, "windows": scene._closed_focus}, read("timings.json"))
                # A new FadeIn adds updater callbacks, not new video frames.
                motion_by_frame = {(row["kind"], round(row["time"] * 30)): row
                                   for row in scene.motion_samples}
                observed.append((scene.time, scene.visual_events, motion_by_frame,
                                 scene._closed_focus, placement))
    assert observed[0] == observed[1]
    assert capture["delta_opacity_at_close"] == 1
    assert len(observed[1][4]) == 8
    assert sum(len(row["references"]) for row in observed[1][4]) == 26
