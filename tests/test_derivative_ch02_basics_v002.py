"""Version-2 math and native interpolation tests, with no camera/GL/TeX/TTS.

Native mobjects and animations run in the established in-memory clock harness.
Formula placeholders test lifecycle and sequence, never actual font pixels.
Only versioned fixtures are read; production runtime is not a test fixture.
"""

import ast
import hashlib
import json
import math
from pathlib import Path
import sys
import types

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_ch02_basics import pure_module
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import validate_narration, validate_units
from manimind.review.content_regression import revision_required, validate_contract


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch02_basics_v002.py"
FIXTURES = ROOT / "tests/fixtures/derivative-ch02-basics-v002"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_production_runtime_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT / "runtime"):
            raise AssertionError("Use versioned v002 fixtures, not production runtime")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def model():
    base = pure_module(ROOT / "examples/derivative_ch02_basics.py")
    module = types.ModuleType("ch02_v002_pure")
    module.__dict__.update(math=math, finite=base.finite)
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), module.__dict__)
    return module


@pytest.mark.parametrize("x", [.2, .5, 1., 2., 7.])
@pytest.mark.parametrize("relative", [-.4, -.01, -.00001, .00001, .01, .4])
def test_inverse_increment_equations_are_exact_before_taking_limit(model, x, relative):
    dx = relative*x
    s = model.log_increment_state(x, dx)
    assert s["y"] == pytest.approx(math.log(x))
    assert math.exp(s["end_y"]) == pytest.approx(x+dx)
    assert x*math.expm1(s["dy"]) == pytest.approx(dx, rel=2e-12, abs=1e-15)
    assert s["dy"] == pytest.approx(math.log(x+dx)-math.log(x), abs=1e-15)
    assert s["inverse_rate"] == pytest.approx(s["exp_rate"])
    assert s["forward_rate"]*s["inverse_rate"] == pytest.approx(1)
    assert s["limit"] == pytest.approx(1/x)
    assert s["dy"] != 0 and (s["dy"] > 0) == (dx > 0)


@pytest.mark.parametrize("x", [.5, 1, 2, 5])
@pytest.mark.parametrize("sign", [-1, 1])
def test_both_sides_converge_to_positive_x_then_reciprocal(model, x, sign):
    errors = []
    for relative in (.1, .01, .001, .0001):
        s = model.log_increment_state(x, sign*x*relative)
        errors.append(abs(s["forward_rate"]-1/x))
        assert s["inverse_rate"] > 0
    assert all(a > b for a, b in zip(errors, errors[1:]))


@pytest.mark.parametrize("a", [.2, .5, 2, math.e, 10])
@pytest.mark.parametrize("dx", [-.25, -.001, .001, .25])
def test_fixed_coefficient_survives_increment_and_difference_quotient(model, a, dx):
    x = 2
    s = model.base_change_state(x, dx, a)
    raw = (math.log(x+dx)-math.log(x))/math.log(a)
    assert s["dz"] == pytest.approx(raw, abs=1e-15)
    assert s["dz"] == s["k"]*s["dy"]
    assert s["quotient"] == pytest.approx(s["dz"]/dx)
    assert s["derivative"] == pytest.approx(1/(x*math.log(a)))
    assert (s["derivative"] > 0) == (a > 1)


def test_transfer_case_has_ln2_in_denominator(model):
    s = model.base_change_state(2, .001, 2)
    assert s["derivative"] == pytest.approx(1/(2*math.log(2)))
    assert s["derivative"] != pytest.approx(math.log(2)/2)


@pytest.mark.parametrize("x,dx", [(0, .1), (-1, .1), (1, 0), (1, -1), (1, -2)])
def test_invalid_log_increment_domain_rejected(model, x, dx):
    with pytest.raises(ValueError):
        model.log_increment_state(x, dx)


@pytest.mark.parametrize("base", [0, -1, 1, float("inf"), float("nan"), True, None])
def test_invalid_fixed_base_rejected(model, base):
    with pytest.raises((ValueError, TypeError)):
        model.base_change_state(2, .1, base)


@pytest.mark.parametrize("bad", [True, None, "1", 1j, float("nan"), float("inf")])
def test_nonreal_or_nonfinite_increments_rejected(model, bad):
    with pytest.raises((ValueError, TypeError)):
        model.log_increment_state(1, bad)


@pytest.fixture(scope="module")
def lesson():
    # Importing modules creates no Scene or GL context. The native harness
    # replaces typography only during its own in-memory execution.
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    import derivative_ch02_basics as original
    import derivative_chapter_shared as shared

    class Probe(lesson.DerivativeBasicsLessonV002):
        def focus_begin(self, identity):
            super().focus_begin(identity)
            formulas = {node.get_tex() for mob in self.mobjects for node in mob.get_family()
                        if hasattr(node, "get_tex")}
            self.formula_states[identity] = formulas

    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            scene.motion_samples, scene.formula_states = [], {}
            # Existing inherited sf/safe_formula resolve globals in their
            # defining modules, so scope placeholders there for this test only.
            patcher.setattr(original, "SemanticFormula", lesson.SemanticFormula)
            patcher.setattr(shared, "SemanticFormula", lesson.SemanticFormula)

        with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
            yield scene


def test_native_entire_scene_clock_schema_and_windows(native):
    plan, narration = read("plan.json"), read("narration.json")
    assert native.time == plan["duration"] == 516
    focuses = {"duration": native.time, "windows": native._closed_focus}
    validate_narration(narration, visual_timeline(plan), focuses)
    assert not native._open_focus and not native._drivers
    assert {w["id"] for w in native._closed_focus} == {r["id"] for r in plan["focus_intents"]}


def test_native_log_variables_precede_increments_and_limit(native):
    states = native.formula_states
    assert any(r"y=\ln x" in tex and r"x=e^y" in tex for tex in states["log_variables"])
    assert not any(r"\Delta y=" in tex for tex in states["log_variables"])
    assert any(r"\Delta y=\ln(x+\Delta x)-y" in tex for tex in states["log_increments"])
    assert any(r"x+\Delta x=e^{y+\Delta y}" in tex for tex in states["log_increments"])
    assert any(r"\Delta x=e^y" in tex for tex in states["log_exp_increment"])
    assert any(r"\frac{\Delta x}{\Delta y}" in tex for tex in states["log_exp_rate"])
    assert any(r"\Delta x\to0" in tex for tex in states["log_exp_rate"])
    assert any(r"(\ln x)'=\frac1x" in tex for tex in states["log_inverse_limit"])


def test_native_fixed_base_bridge_keeps_all_intermediate_rows(native):
    states = native.formula_states
    assert any(r"k=\frac1{\ln a}" in tex for tex in states["log_base_definition"])
    assert any(r"\Delta z=k\ln(x+\Delta x)-k\ln x=k\Delta y" in tex for tex in states["log_base_increment"])
    assert any(r"\frac{\Delta z}{\Delta x}=k\frac{\Delta y}{\Delta x}" in tex
               for tex in states["log_base_quotient"])
    final = states["log_base_derivative"]
    assert any(r"\Delta z=k\ln" in tex for tex in final)
    assert any(r"\frac{\Delta z}{\Delta x}" in tex for tex in final)
    assert any(r"\frac1{x\ln a}" in tex for tex in final)
    assert any(r"\frac1{2\ln2}" in tex for tex in final)


def test_native_one_increment_drives_points_segments_and_numbers(native, model):
    samples = [s for s in native.motion_samples if s["kind"] == "log_increment_bridge"]
    assert len(samples) > 200
    assert min(s["dx"] for s in samples) == pytest.approx(.08)
    assert max(s["dx"] for s in samples) == pytest.approx(.8)
    assert all(a["dx"]+1e-12 >= b["dx"] for a, b in zip(samples, samples[1:]))
    for s in samples[::19]:
        assert s["point"] == pytest.approx(model.increment_point(1, 0))
        assert s["other"] == pytest.approx(model.increment_point(1+s["dx"], s["dy"]))
        assert s["horizontal"] == pytest.approx(model.increment_point(1+s["dx"], 0))
        assert s["vertical"] == pytest.approx(s["other"])


def test_native_process_window_ends_before_phase_removal(native):
    windows = {w["id"]: w for w in native._closed_focus}
    assert windows["log_increment_motion"]["end"] < windows["log_exp_rate"]["start"]
    assert windows["log_increments"]["end"] < windows["log_inverse_limit"]["start"]
    assert windows["log_inverse_limit"]["end"] < windows["log_map"]["start"]
    assert windows["log_map"]["end"] < windows["log_base_definition"]["start"]


def test_frozen_baseline_sources_and_actual_contract_inventory():
    lock = read("baseline-lock.json")
    for item in lock["protected_inputs"]:
        if item["path"].startswith("examples/"):
            assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    contract, plan = read("regression-contract.json"), read("plan.json")
    validate_contract(contract)
    assert revision_required(plan, profile_version="understanding-first-v3")
    assert contract["assets"]["visual_v001"]["duration"] == 452
    assert contract["assets"]["visual_v001"]["sha256"] == "ddb26caa018afd09eb9feb1dfed2918e05ffc49139f89f7db36d7970d419622f"
    assert [u["id"] for u in contract["units"]] == [c["id"] for c in plan["cues"]]
    assert contract["units"][0]["baseline_interval"][0] == 0
    assert contract["units"][-1]["baseline_interval"][1] == 452
    assert all(f["kind"] in {"state", "process"} for u in contract["units"] for f in u["features"])


def test_every_nonlog_method_and_narration_is_inherited_unchanged(lesson):
    original = sys.modules["derivative_ch02_basics"]
    for cue in read("plan.json")["cues"]:
        if cue["id"] != "logarithm":
            assert getattr(lesson.DerivativeBasicsLessonV002, cue["id"]) is getattr(original.DerivativeBasicsLesson, cue["id"])
    prior = json.loads((ROOT / "tests/fixtures/derivative-ch02-basics/narration.json").read_text(encoding="utf-8"))
    assert [u for u in read("narration.json")["units"] if u["cue"] != "logarithm"] == [u for u in prior["units"] if u["cue"] != "logarithm"]
    validate_units(read("narration.json"))


def test_versioned_state_and_no_fabricated_audio_times():
    for filename in ("plan.json", "narration.json", "science.json", "regression-contract.json"):
        value = read(filename)
        assert all(value.get(k) for k in ("writer", "consumers", "lifecycle", "invalidation"))
    narration = read("narration.json")
    assert narration["audio_status"] == "not_generated"
    assert all(set(ref) == {"id", "focus", "text"} for u in narration["units"] for ref in u["references"])
