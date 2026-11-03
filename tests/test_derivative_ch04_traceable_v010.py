"""Native geometry/scope/audio tests; actual GL and independent review remain required."""

import json
from pathlib import Path
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule
from manimind.components.formula_motion import SemanticFormula as RealFormula

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch04-traceable-v010"


def read(name):
    return json.loads((FIXTURE / name).read_text())


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch04_traceable_v010.py")
        import derivative_ch04_chain as base
        import manimind.components.formula_motion as fm
        real_formula = fm.SemanticFormula
        class Probe(module.DerivativeChainTraceableV010):
            def semantic(self, latex, tokens, **kwargs):
                real_formula(latex, tokens=tokens, colors=kwargs.get("colors"), font_size=kwargs.get("size",44))
                return super().semantic(latex, tokens, **kwargs)
            def mark(self, identity):
                if identity in {"chain_remainders_ready", "example_variable_scope_ready"}:
                    self.observed_formulas[identity] = {node.get_tex() for mob in self.mobjects for node in mob.get_family()
                        if hasattr(node,"get_tex") and float(node.get_opacity()) > .9}
                return super().mark(identity)
        def initialize(scene):
            scene.observed_formulas = {}
            patch.setattr(base, "SemanticFormula", fm.SemanticFormula)
        with native_run(module, Probe, read("plan.json"), initialize) as scene:
            yield scene


def test_intact_audio_clock_and_references(native):
    plan = read("plan.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-6)
    rows = schedule(visual_timeline(plan), read("narration.json"),
        {"duration":native.time,"windows":native._closed_focus}, read("timings.json"))
    assert len(rows)==8 and sum(len(r["references"]) for r in rows)==26
    for got, old in zip(rows, plan["intended_full_wav_placement"], strict=True):
        assert got["start"] == pytest.approx(old["intended_start"], abs=.04)
        assert got["duration_seconds"] == old["duration_seconds"]


def test_specific_point_precedes_increment_and_leaves_before_variable_x(native):
    at_point = native.observed_formulas["chain_remainders_ready"]
    assert any(r"x=1,\quad u=2" in x for x in at_point)
    assert any(r"u=x^2+1,\qquad y=u^3" in x for x in at_point)
    assert not any("g(x)" in x or "f(u)" in x or "g'(x)" in x for x in at_point)
    at_variable = native.observed_formulas["example_variable_scope_ready"]
    assert not any(r"x=1,\quad u=2" in x or r"\Delta u=2h+h^2" in x for x in at_variable)
    assert any("g'(x)=2x" in x for x in at_variable)
    marks = {r["id"]:r["time"] for r in native.visual_events}
    assert marks["example_point_scope_ready"] < marks["chain_remainders_ready"] < marks["example_variable_scope_ready"]


def test_entire_factor_and_lhs_do_not_deform_even_during_finalization(native):
    rows = [r for r in native.motion_samples if r["kind"]=="collection_fixed_geometry"]
    final = [r for r in native.motion_samples if r["kind"]=="collection_constants_finalize"]
    assert len(rows)>40 and len(final)==1
    assert len({r["factor"] for r in rows})==len({r["lhs"] for r in rows})==1
    assert final[0]["factor"]==rows[0]["factor"] and final[0]["lhs"]==rows[0]["lhs"]
    assert rows[-1]["time"] > 296.2
    assert not native._open_focus


def test_review_selection_includes_late_stage_and_conditions():
    plan = read("plan.json")
    validate_contract(read("contract.json"))
    assert {180.427,184.053,197.9,296.067,296.1,296.2,296.3,296.4,296.5}.issubset(plan["review_times"])
    stages = {r["id"] for r in plan["substage_review_times"]}
    assert {"collect_finalize","collect_cleanup","point_bind","point_exit","variable_resume"}.issubset(stages)
    for r in plan["substage_review_times"]:
        assert r["before"]<r["during"]<r["after"]


def test_real_tex_collection_parts_have_matching_native_topology(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "examples"))
    module = load_lesson(ROOT / "examples/derivative_ch04_traceable_v010.py")
    import manimind.components.formula_motion as fm
    import derivative_ch04_chain as base
    real_formula = RealFormula
    monkeypatch.setattr(base,"SemanticFormula",real_formula)
    scene = object.__new__(module.DerivativeChainTraceableV010)
    source = scene.semantic(module.PRODUCT,{"coefficient":"4","input":"3x-1","power":("3",1),"rate":("3",2),"relation":"="},y=-.3,size=43)
    active = real_formula(module.PRODUCT,tokens={"lhs":"y'=","factor":r"(3x-1)^3","four":"4","three":("3",2),"times":r"\cdot"},font_size=43)
    factor = module.remainder(source,[source.tag(k) for k in ("prefix","relation","coefficient","rate","times")])
    module.align_native_glyphs(active.tag("factor"),factor)
    assert module.geometry_signature(active.tag("factor"))==module.geometry_signature(factor)
