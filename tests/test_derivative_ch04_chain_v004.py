"""Offline native-clock checks; vector placeholders do not approve pixels."""

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


@pytest.fixture(scope="module")
def revisions():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        new = load_lesson(ROOT / "examples/derivative_ch04_chain_v004.py")
        old = importlib.import_module("derivative_ch04_chain_v003")
        yield old, new


def test_only_scope_headings_are_changed_and_core_remains_separate(revisions):
    old, new = revisions
    plan = read("plan.json")
    assert set(new.SCOPE_HEADINGS) == {"opening", "two-stages", "one-change", "ratios", "rule"}
    assert all("非线性内层拓展" in text for text in new.SCOPE_HEADINGS.values())
    assert new.AUTHOR_AGENT == "019eaf8b-9151-75e2-9db4-5ff834335577"
    for cue in plan["cues"]:
        assert getattr(new.DerivativeChainLessonV004, cue["id"].replace("-", "_")) is getattr(
            old.DerivativeChainLessonV003, cue["id"].replace("-", "_"))
    assert new.DerivativeChainLessonV004.construct is old.DerivativeChainLessonV003.construct
    assert new.DerivativeChainLessonV004.beat is old.DerivativeChainLessonV003.beat


def test_actual_native_clock_motion_and_intact_audio_schedule_are_identical(revisions):
    old, new = revisions
    import derivative_ch04_chain as base

    before = read("plan.json")
    after = copy.deepcopy(before)
    for cue in after["cues"]:
        cue["heading"] = new.SCOPE_HEADINGS.get(cue["id"], cue["heading"])
    observed = []
    for module, scene_class, plan in ((old, old.DerivativeChainLessonV003, before),
                                      (new, new.DerivativeChainLessonV004, after)):
        with pytest.MonkeyPatch.context() as patcher:
            def initialize(scene):
                patcher.setattr(base, "SemanticFormula", module.SemanticFormula)

            with native_run(module, scene_class, plan, initialize) as scene:
                placement = schedule(visual_timeline(plan), read("narration.json"),
                    {"duration": scene.time, "windows": scene._closed_focus}, read("timings.json"))
                labels = [label for label in scene.labels if label not in {
                    c["heading"] for c in plan["cues"]}]
                observed.append((scene.time, scene.visual_events, scene.motion_samples,
                                 scene._closed_focus, placement, labels))
                assert all(cue["heading"] in scene.labels for cue in plan["cues"])
    assert observed[0] == observed[1]
    assert len(observed[1][4]) == 8
    assert sum(len(row["references"]) for row in observed[1][4]) == 26
