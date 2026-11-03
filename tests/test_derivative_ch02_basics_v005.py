"""Narrow author checks: native construct, not rendered pixels or approval."""

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, transport_segments, validate_narration


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/derivative-ch02-basics-v005"
OLD = ROOT / "tests/fixtures/derivative-ch02-basics-v004"
SOURCE = ROOT / "examples/derivative_ch02_basics_v005.py"
AUTHOR = "01a19adc-bbae-7bc2-b33c-0be3ebd20365"


def read(name, directory=FIXTURES):
    return json.loads((directory / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_production_runtime_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT / "runtime"):
            raise AssertionError("Use frozen fixtures, not live production state")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


def construct_trace(lesson, base, plan):
    import derivative_ch02_basics as original
    import derivative_chapter_shared as shared

    class Probe(base):
        def beat(self, fraction, *animations, **kwargs):
            before = self.get_time()
            super().beat(fraction, *animations, **kwargs)
            self.stage_trace.append({"cue": self._cue["id"], "key": f"{fraction:.2f}",
                                     "before": before, "after": self.get_time()})

        def label(self, text, *args, **kwargs):
            obj = super().label(text, *args, **kwargs)
            if text == lesson.INHERITED_EXP_NOTE:
                self.comparison_objects.append(obj)
            return obj

        def focus_begin(self, identity):
            super().focus_begin(identity)
            self.formula_states[identity] = {node.get_tex() for mob in self.mobjects
                for node in mob.get_family() if hasattr(node, "get_tex")
                and float(node.get_opacity()) > .9}
            if identity == "exp_compare":
                self.comparison_added = [obj in self.mobjects for obj in self.comparison_objects]
                self.comparison_bounds = [{"left": float(obj.get_left()[0]),
                    "right": float(obj.get_right()[0]), "bottom": float(obj.get_bottom()[1]),
                    "top": float(obj.get_top()[1]), "center": obj.get_center().tolist(),
                    "opacity": float(obj.get_opacity()), "subtitle": obj is self._subtitle_driver}
                    for obj in self.comparison_objects]

    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            scene.motion_samples, scene.stage_trace, scene.formula_states = [], [], {}
            scene.comparison_objects, scene.comparison_added, scene.comparison_bounds = [], [], []
            patcher.setattr(original, "SemanticFormula", lesson.SemanticFormula)
            patcher.setattr(shared, "SemanticFormula", lesson.SemanticFormula)

        with native_run(lesson, Probe, plan, initialize) as scene:
            return scene


@pytest.fixture(scope="module")
def native(lesson):
    return construct_trace(lesson, lesson.DerivativeBasicsLessonV005, read("plan.json"))


@pytest.fixture(scope="module")
def previous(lesson):
    return construct_trace(lesson, lesson.DerivativeBasicsLessonV004, read("plan.json", OLD))


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json", OLD),
                    {"duration": native.time, "windows": native._closed_focus}, read("timings.json", OLD))


def test_whole_native_construct_has_identical_clock_focus_motion_and_old_formula_states(native, previous, lesson):
    assert native.time == previous.time == pytest.approx(654.033333333, abs=1e-8)
    assert native.stage_trace == previous.stage_trace
    assert native._closed_focus == previous._closed_focus
    assert native.visual_events == previous.visual_events
    assert native.motion_samples == previous.motion_samples
    assert native.plays == previous.plays
    assert not native._open_focus and not native._drivers
    assert native.labels == [s for s in previous.labels if s != lesson.INHERITED_EXP_NOTE]
    for identity, old in previous.formula_states.items():
        current = native.formula_states[identity]
        assert current == old | ({lesson.EXP_COMPARE_TEX} if identity == "exp_compare" else set())
    last = 0
    for row in native.stage_trace:
        assert row["after"] >= row["before"] >= last
        last = row["after"]


def test_a1_formula_is_actually_constructed_added_and_opaque_at_exp_compare(native, lesson):
    assert len(native.comparison_objects) == 1
    assert native.comparison_added == [True]
    assert lesson.EXP_COMPARE_TEX in native.formula_states["exp_compare"]
    for literal in [r"(e^x)'=e^x", r"0<a<1:\ (a^x)'<0", r"a=1\ \Rightarrow\ 1^x=1,\ (1^x)'=0"]:
        assert literal in native.comparison_objects[0].get_tex()
    bounds = native.comparison_bounds[0]
    assert bounds["center"] == pytest.approx([0, -2.72, 0])
    assert bounds["opacity"] > .99 and not bounds["subtitle"]
    assert -6.1 <= bounds["left"] < bounds["right"] <= 6.1
    # These are vector-placeholder bounds, not real TeX/caption pixel clearance.
    assert -3.1 < bounds["bottom"] < bounds["top"] < -2.3


def test_a1_constant_and_zero_derivative_agree_with_the_unchanged_model(lesson):
    from derivative_ch02_basics import basic_state

    for x in [-100, -1.3, 0, 1.3, 100]:
        assert basic_state("exp", x, base=1) == {"x": x, "value": 1, "slope": 0}
    assert "(1^x)'=0" in lesson.EXP_COMPARE_TEX


def test_full_original_transport_placement_and_ref5_constant_clause_are_unchanged(native, previous, placement):
    plan, old_plan = read("plan.json"), read("plan.json", OLD)
    narration, timings = read("narration.json", OLD), read("timings.json", OLD)
    old_placement = schedule(visual_timeline(old_plan), narration,
        {"duration": previous.time, "windows": previous._closed_focus}, timings)
    assert placement == old_placement
    assert len(placement) == len(transport_segments(narration)) == 14
    assert sum(row["duration_seconds"] for row in placement) == pytest.approx(609.28)
    validate_narration(narration, visual_timeline(plan),
                       {"duration": native.time, "windows": native._closed_focus})
    assert plan["intended_full_wav_placement"] == old_plan["intended_full_wav_placement"]
    assert plan["timing_provenance"] == old_plan["timing_provenance"]
    row = next(r for r in placement if r["id"] == "exponential_unit")
    focus = next(w for w in native._closed_focus if w["id"] == "exp_compare")
    phrase = next(p for u in timings["units"] if u["id"] == "exponential_unit"
                  for p in u["phrases"] if p["id"] == "exponential_ref_5")
    assert (phrase["start"], phrase["end"]) == (46.2, 57.48)
    assert focus["start"] <= row["start"] + phrase["start"]
    assert row["start"] + 53.86 < row["start"] + 57.48 <= focus["end"]
    assert "底数等于一时，函数是常数一，导数为零。" in phrase["text"]
    for placed, intended in zip(placement, plan["intended_full_wav_placement"], strict=True):
        assert abs(placed["start"] - intended["intended_start"]) <= .07


def test_plan_changes_no_other_cue_or_timing_and_retains_all_contributors():
    plan, old = read("plan.json"), read("plan.json", OLD)
    for new_cue, old_cue in zip(plan["cues"], old["cues"], strict=True):
        expected = deepcopy(old_cue)
        if expected["id"] == "exponential":
            expected["anchors"][-1]["meaning"] = new_cue["anchors"][-1]["meaning"]
        assert new_cue == expected
    for new_focus, old_focus in zip(plan["focus_intents"], old["focus_intents"], strict=True):
        assert new_focus["id"] == old_focus["id"]
        if new_focus["id"] != "exp_compare":
            assert new_focus == old_focus
    assert plan["review_times"] == old["review_times"]
    assert plan["author_agent"] == plan["author_context"] == plan["writer"] == AUTHOR
    assert {c["author_agent"] for c in plan["contributors"]} == {
        "01a199e9-7383-7a03-b45c-97d3d21bd9dd", "019eaf8b-9151-75e2-9db4-5ff834335577",
        "01a19ab5-b2d3-7003-a784-edeeaecdbc23"}
    assert plan["revision_mode"] == "revision"
    assert plan["narration_draft"].endswith("narration-draft-v003.json")
    assert plan["revision_review"].endswith("review/regression-v005.json")
    assert set(old["sources"]) <= set(plan["sources"])


def test_contract_honestly_corrects_unverified_inventory_without_dropping_any_feature():
    contract, old = read("contract.json"), read("contract.json", OLD)
    validate_contract(contract)
    assert contract["assets"] == old["assets"]
    assert set(contract["assets"]) == {"visual_v002"}
    assert contract["assets"]["visual_v002"]["duration"] == 516
    assert sum(len(u["features"]) for u in contract["units"]) == 38
    changed = []
    for new_unit, old_unit in zip(contract["units"], old["units"], strict=True):
        assert {k: v for k, v in new_unit.items() if k != "features"} == {
            k: v for k, v in old_unit.items() if k != "features"}
        for new, previous in zip(new_unit["features"], old_unit["features"], strict=True):
            assert (new["id"], new["kind"], new["baseline_interval"], new["baseline_samples"]) == (
                previous["id"], previous["kind"], previous["baseline_interval"], previous["baseline_samples"])
            if new != previous:
                changed.append(new["id"])
                assert "非已证实的旧片库存" in new["claim"]
                assert "a=1" in new["claim"] and "(1^x)'=0" in new["claim"]
                assert new["new_visual_requirement"]["kind"] == "v005_new_visual_completion"
    assert changed == ["exp_domain_sign"]
    amendment = contract["contract_amendment"]
    assert amendment["source"]["prior_result"] == {
        "features": 38, "retained": 37, "lost": 1, "loss_established": False,
        "failure_kind": "unverified_contract_component"}
    assert len(amendment["baseline_evidence"]) == len(amendment["prior_candidate_evidence"]) == 3
    assert all("frame_sha256" in row for row in amendment["baseline_evidence"])
    for name in ["plan.json", "contract.json", "baseline-lock.json"]:
        value = read(name)
        assert value["status"] == "not_reviewed" and value["writer"] == AUTHOR
        assert all(value[key] for key in ["consumers", "lifecycle", "invalidation"])


def test_wrapper_only_overrides_label_without_editing_old_scene_methods(lesson):
    for cue in read("plan.json")["cues"]:
        assert getattr(lesson.DerivativeBasicsLessonV005, cue["id"]) is getattr(
            lesson.DerivativeBasicsLessonV004, cue["id"])
    assert lesson.DerivativeBasicsLessonV005.beat is lesson.DerivativeBasicsLessonV004.beat
    assert lesson.DerivativeBasicsLessonV005.safe_formula is lesson.DerivativeBasicsLessonV004.safe_formula
    tree = ast.parse(SOURCE.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assert {node.name for node in cls.body if isinstance(node, ast.FunctionDef)} == {"label"}


def test_other_labels_and_same_text_outside_exponential_remain_native(lesson):
    class Probe(lesson.DerivativeBasicsLessonV005):
        _cue = {"id": "opening"}

        def cn(self, text, **kwargs):
            self.called = (text, kwargs)
            return self

        def get_width(self):
            return 1

        def move_to(self, position):
            self.position = position
            return self

    probe = Probe.__new__(Probe)
    assert probe.label(lesson.INHERITED_EXP_NOTE, x=2, y=1, size=20) is probe
    assert probe.called[0] == lesson.INHERITED_EXP_NOTE
    assert probe.position == [2, 1, 0]


def test_protected_non_runtime_inputs_are_byte_identical():
    for row in read("baseline-lock.json")["protected_inputs"]:
        if not row["path"].startswith("runtime/"):
            assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
