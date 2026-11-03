"""Chapter 02 author timing checks, native clock only, never pixel/listening review."""

import ast
import hashlib
import json
import math
from pathlib import Path
import sys

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, transport_segments, validate_narration


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/derivative-ch02-basics-v004"
SOURCE = ROOT / "examples/derivative_ch02_basics_v004.py"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_production_runtime_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT / "runtime"):
            raise AssertionError("Read versioned v004 test fixtures, not live production state")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    import derivative_ch02_basics as original
    import derivative_chapter_shared as shared

    class Probe(lesson.DerivativeBasicsLessonV004):
        def beat(self, fraction, *animations, **kwargs):
            start = self.get_time()
            super().beat(fraction, *animations, **kwargs)
            self.stage_trace.append({"cue": self._cue["id"], "key": f"{fraction:.2f}",
                                     "before": start, "after": self.get_time()})

        def focus_begin(self, identity):
            super().focus_begin(identity)
            self.formula_states[identity] = {node.get_tex() for mob in self.mobjects for node in mob.get_family()
                if hasattr(node, "get_tex") and float(node.get_opacity()) > .9}

    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            scene.motion_samples, scene.formula_states, scene.stage_trace = [], {}, []
            patcher.setattr(original, "SemanticFormula", lesson.SemanticFormula)
            patcher.setattr(shared, "SemanticFormula", lesson.SemanticFormula)

        with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
                    {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def at(native, placement, unit, local, function=None, kind="slope_map"):
    row = next(r for r in placement if r["id"] == unit)
    time = row["start"] + local
    samples = [s for s in native.motion_samples if s["kind"] == kind
               and (function is None or s.get("function") == function)]
    sample = min(samples, key=lambda s: abs(s["time"]-time))
    assert abs(sample["time"]-time) <= 1/30+.001
    return sample


def test_entire_native_scene_clock_focus_and_intact_wav_solution(native, placement):
    plan, narration, timings = read("plan.json"), read("narration.json"), read("timings.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-8)
    assert native.time > 609.28 > 516
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(609.28)
    assert len(placement) == 14
    assert not native._open_focus and not native._drivers
    validate_narration(narration, visual_timeline(plan), {"duration": native.time, "windows": native._closed_focus})
    assert {w["id"] for w in native._closed_focus} == {f["id"] for f in plan["focus_intents"]}
    previous = 0
    for row, timing, intended in zip(placement, timings["units"], plan["intended_full_wav_placement"], strict=True):
        assert row["start"] >= previous
        assert row["end"]-row["start"] == pytest.approx(timing["duration_seconds"])
        assert abs(row["start"]-intended["intended_start"]) <= .07
        for phrase in row["phrases"]:
            assert phrase["focus_start"] <= phrase["visual_start"]+.000001
            assert phrase["visual_end"] <= phrase["focus_end"]+.000001
        previous = row["end"]


def test_general_motion_has_negative_zero_hold_positive_and_exact_terminal_state(native, placement):
    assert at(native, placement, "general_unit", 40.6, "square")["x"] < 0
    assert at(native, placement, "general_unit", 42.5, "square")["x"] == pytest.approx(0)
    assert at(native, placement, "general_unit", 43.2, "square")["slope"] == pytest.approx(0)
    assert at(native, placement, "general_unit", 45, "square")["x"] > 0
    terminal = at(native, placement, "general_unit", 51.6, "square")
    assert terminal["x"] == pytest.approx(2)
    assert terminal["slope"] == pytest.approx(4)


def test_square_semantic_transfer_occurs_during_actual_expansion_not_initial_wait(native, placement):
    start = next(r["start"] for r in placement if r["id"] == "general_unit")
    copied = next(s for s in native.motion_samples if s["kind"] == "formula_copy")
    complete = next(s for s in native.motion_samples if s["kind"] == "formula_complete")
    assert start+7 <= copied["time"] < complete["time"] <= start+9.3
    assert copied["stage"] == complete["stage"] == "square_expand"
    assert r"2ah+h^2" in complete["target"]


def test_sine_spoken_crossings_and_plateaus_are_actual_values(native, placement):
    for local, x, slope in [(20.1, 0, 1), (23.97, 0, 1), (26.1, math.pi/2, 0),
                             (27.9, math.pi/2, 0), (30.5, math.pi, -1), (32.7, math.pi, -1)]:
        s = at(native, placement, "sine_unit", local, "sin")
        assert s["x"] == pytest.approx(x, abs=1e-8)
        assert s["slope"] == pytest.approx(slope, abs=1e-8)
    assert at(native, placement, "sine_unit", 36, "sin")["x"] > math.pi


def test_cosine_spoken_horizontal_tangents_and_upward_motion_are_actual(native, placement):
    assert at(native, placement, "cosine_unit", 3.2, "cos")["x"] == pytest.approx(0)
    assert at(native, placement, "cosine_unit", 4.4, "cos")["slope"] < 0
    assert at(native, placement, "cosine_unit", 6.9, "cos")["x"] == pytest.approx(math.pi)
    assert at(native, placement, "cosine_unit", 7.1, "cos")["slope"] == pytest.approx(0, abs=1e-8)
    assert at(native, placement, "cosine_unit", 8.2, "cos")["slope"] > 0


def test_remaining_map_processes_move_within_their_real_spoken_references(native, placement):
    cases = [("constant_unit", "constant", 3, 9, -2, 2),
             ("identity_unit", "identity", 16, 21, -2, 2),
             ("power_unit", "cube", 55.5, 60.5, -1.35, 1.35),
             ("reciprocal_unit", "reciprocal", 44, 50, -2.5, -.65),
             ("reciprocal_unit", "reciprocal", 53.5, 61, .65, 2.5),
             ("root_unit", "root", 40, 48, .09, 3.7),
             ("exponential_unit", "exp", 36.5, 44, -1.3, 1.3),
             ("log_graph_unit", "log", 2, 9, .25, 3.7)]
    for unit, function, before, after, lo, hi in cases:
        a, b = at(native, placement, unit, before, function), at(native, placement, unit, after, function)
        assert lo <= a["x"] < b["x"] <= hi+.0000001
    assert at(native, placement, "power_unit", 58, "cube")["x"] == pytest.approx(0)


def test_log_increment_moves_only_during_spoken_shrinking_clause(native, placement):
    samples = [s for s in native.motion_samples if s["kind"] == "log_increment_bridge"]
    assert min(s["dx"] for s in samples) == pytest.approx(.08)
    assert max(s["dx"] for s in samples) == pytest.approx(.8)
    assert all(a["dx"]+1e-12 >= b["dx"] for a, b in zip(samples, samples[1:]))
    for t in [20, 40, 48.1]:
        assert at(native, placement, "log_inverse_unit", t, kind="log_increment_bridge")["dx"] == pytest.approx(.8)
    mid = at(native, placement, "log_inverse_unit", 52, kind="log_increment_bridge")
    assert .08 < mid["dx"] < .8
    assert at(native, placement, "log_inverse_unit", 56.4, kind="log_increment_bridge")["dx"] == pytest.approx(.08)
    for s in samples[::41]:
        assert s["dy"] == pytest.approx(math.log1p(s["dx"]))
        assert s["other"] == pytest.approx([-6.2+2.45*(1+s["dx"]), .15+1.7*s["dy"], 0])
        assert s["horizontal"] == pytest.approx([-6.2+2.45*(1+s["dx"]), .15, 0])
        assert s["vertical"] == pytest.approx(s["other"])


def test_six_definition_derivations_and_both_log_bridges_are_real_formula_states(native):
    required = {"general_quotient": r"\frac{(a+h)^2-a^2}{h}",
        "general_limit": r"2a+h", "identity_quotient": r"\frac hh=1", "constant_increment": r"\frac{c-c}{h}=0",
        "power_cubic_limit": r"3x^2+3xh+h^2", "reciprocal_common_denominator": r"x-(x+h)",
        "reciprocal_limit": r"-\frac1{x^2}", "root_conjugate": r"(x+h)-x", "root_domain": r"\frac1{2\sqrt x}",
        "exp_standard_limit": r"\ln a", "sine_limits": r"\mathrm{radians}",
        "log_variables": r"x=e^y", "log_increments": r"x+\Delta x=e^{y+\Delta y}",
        "log_exp_increment": r"x(e^{\Delta y}-1)", "log_exp_rate": r"\frac{\Delta x}{\Delta y}",
        "log_inverse_limit": r"(\ln x)'=\frac1x", "log_base_definition": r"k=\frac1{\ln a}",
        "log_base_increment": r"\Delta z=k\ln(x+\Delta x)-k\ln x=k\Delta y",
        "log_base_quotient": r"k\frac{\Delta y}{\Delta x}", "log_base_derivative": r"\frac1{2\ln2}"}
    for focus, literal in required.items():
        assert any(literal in tex for tex in native.formula_states[focus]), (focus, literal)
    assert not any(r"\Delta y=" in tex for tex in native.formula_states["log_variables"])
    windows = {w["id"]: w for w in native._closed_focus}
    assert windows["log_increments"]["end"] < windows["log_inverse_limit"]["start"]
    assert windows["log_inverse_limit"]["end"] < windows["log_map"]["start"]
    assert windows["log_map"]["end"] < windows["log_base_definition"]["start"]


def test_root_cancelled_expression_exists_when_the_spoken_clause_names_it(native, placement):
    row = next(r for r in placement if r["id"] == "root_unit")
    reveal = next(s["after"] for s in native.stage_trace if s["cue"] == "root" and s["key"] == "0.36")
    assert row["start"]+21.66 <= reveal <= row["start"]+22.24


def test_contract_uses_full_real_v002_and_extends_old_inventory():
    contract = read("contract.json")
    validate_contract(contract)
    assert set(contract["assets"]) == {"visual_v002"}
    asset = contract["assets"]["visual_v002"]
    assert asset["duration"] == 516
    assert asset["sha256"] == "716b9ce6b0eff7ad27b5238ec4b5b9f3adfb9deff9a9d7ea849627c0c0ebd0f9"
    assert "/visual-v002/" in asset["path"]
    for unit in contract["units"]:
        for feature in unit["features"]:
            lo, hi = feature["baseline_interval"]
            assert unit["baseline_interval"][0] <= lo < hi <= unit["baseline_interval"][1]
            samples = feature["baseline_samples"]
            assert all(lo-.000001 <= e["time"] <= hi+.000001 for e in samples)
            if feature["kind"] == "process":
                assert [e["phase"] for e in samples] == ["before", "during", "after"]
                assert samples[0]["time"] < samples[1]["time"] < samples[2]["time"]
    log = next(u for u in contract["units"] if u["id"] == "logarithm")
    assert len(log["features"]) == 12


def test_inherited_content_and_frozen_sources_are_byte_identical(lesson):
    original = sys.modules["derivative_ch02_basics_v002"]
    for cue in read("plan.json")["cues"]:
        assert getattr(lesson.DerivativeBasicsLessonV004, cue["id"]) is getattr(original.DerivativeBasicsLessonV002, cue["id"])
    for item in read("baseline-lock.json")["protected_inputs"]:
        assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    assert {n.name for n in cls.body if isinstance(n, ast.FunctionDef)} == {"beat", "safe_formula"}


def test_new_candidate_is_not_approval_and_speech_transport_is_unchanged():
    plan = read("plan.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19ab5-b2d3-7003-a784-edeeaecdbc23"
    assert plan["contributors"][0]["author_agent"] == "01a199e9-7383-7a03-b45c-97d3d21bd9dd"
    assert plan["revision_mode"] == "revision"
    assert plan["narration_draft"].endswith("narration-draft-v003.json")
    assert plan["revision_review"].endswith("math-derivative-ch02-basics-20261102/review/regression-v004.json")
    assert all(read(name)["status"] == "not_reviewed" for name in ["plan.json", "contract.json", "timings.json", "narration.json", "baseline-lock.json"])
    assert len(transport_segments(read("narration.json"))) == 14
    for name in ["examples/derivative_ch02_basics.py", "examples/derivative_ch02_basics_v002.py", "examples/derivative_chapter_shared.py"]:
        assert name in plan["sources"]


def test_unretimed_short_film_cannot_fit_the_intact_original_wavs(native):
    plan = read("plan.json")
    # Keep the total/report valid so the original full-WAV conflict, rather
    # than a malformed test report, is the reason this negative control fails.
    reduction = plan["cues"][0]["duration"] - 18
    plan["cues"][0]["duration"] = 18
    plan["cues"][-1]["duration"] += reduction
    with pytest.raises(ValueError, match="opening_unit: no intersection"):
        schedule(visual_timeline(plan), read("narration.json"),
                 {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))
