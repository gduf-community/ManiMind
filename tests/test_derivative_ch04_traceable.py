"""Native vector/clock tests, not a GL or editorial review substitute."""

import hashlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch04-traceable"


def read(name):
    return json.loads((FIXTURE / name).read_text())


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch04_traceable.py")
        import derivative_ch04_chain as base
        def initialize(scene):
            patch.setattr(base, "SemanticFormula", module.SemanticFormula)
        with native_run(module, module.DerivativeChainTraceable, read("plan.json"), initialize) as scene:
            yield scene


def test_full_clock_and_original_wav_references(native):
    plan = read("plan.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-6)
    placement = schedule(visual_timeline(plan), read("narration.json"),
                         {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))
    assert len(placement) == 8
    assert sum(len(r["references"]) for r in placement) == 26
    for got, intended in zip(placement, plan["intended_full_wav_placement"], strict=True):
        assert got["start"] == pytest.approx(intended["intended_start"], abs=.04)
        assert got["duration_seconds"] == intended["duration_seconds"]


def test_copies_record_source_coordinates_before_native_travel(native):
    copies = [r for r in native.motion_samples if r["kind"] == "source_copy"]
    assert len(copies) == 17
    assert {r["role"] for r in copies} >= {"whole_inner", "intermediate_denominator", "intermediate_numerator",
        "outer_rate", "inner_rate", "affine_whole_input", "affine_rate", "practice_whole_inner", "practice_inner_rate"}
    assert all(r["end"]-r["time"] >= .95 for r in copies)
    assert all(len(r["origin"]) == len(r["destination"]) == 3 for r in copies)
    assert not native._open_focus


def test_retains_output_motion_and_all_domain_references(native):
    samples = [r for r in native.motion_samples if r["kind"] == "chain_transfer"]
    assert len(samples) > 500
    assert samples[0]["y"] == 8
    assert samples[-1]["y"] == pytest.approx(10.793861)
    assert "f(b) 有定义时，这是常数函数，导数为 0" in native.labels
    assert {r["id"] for r in native.visual_events} >= {"chain_root_domain_ready", "chain_log_domain_ready"}


def test_bound_contract_and_explicit_v431_dependencies():
    plan, contract = read("plan.json"), read("contract.json")
    validate_contract(contract)
    assert set(contract["assets"]) == {"visual_v005"}
    assert plan["author_agent"] == plan["author_context"] == "01a19f6b-1725-7be3-a4d8-bf988a308b31"
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
    assert len(plan["formula_transitions"]) == len(plan["transition_review_times"]) == 8
    for row in plan["transition_review_times"]:
        assert row["before"] < row["during"] < row["after"]
        assert all(row[p] in plan["review_times"] for p in ("before", "during", "after"))
    assert set(plan["sources"]) >= {"src/manimind/postproduce/traceable_film.py", "src/manimind/postproduce/traceable_film_v2.py",
                                   "docs/formula-continuity.md", "docs/formula-continuity-v2.md", "examples/derivative_ch04_chain_v005.py"}


def test_protected_scene_inputs_unchanged():
    for row in read("baseline-lock.json")["protected_inputs"]:
        if row["path"].startswith("examples/"):
            assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_real_native_tex_selectors_compile_without_overlap():
    from manimind.components.formula_motion import SemanticFormula as RealFormula
    checked = []
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch04_traceable.py")
        import derivative_ch04_chain as base

        class Probe(module.DerivativeChainTraceable):
            def semantic(self, latex, tokens, **kwargs):
                formula = RealFormula(latex, tokens=tokens, colors=kwargs.get("colors"), font_size=kwargs.get("size", 44))
                assert all(formula.tag(key).get_width() > 0 for key in tokens)
                checked.append(latex)
                return super().semantic(latex, tokens, **kwargs)

        def initialize(scene):
            patch.setattr(base, "SemanticFormula", module.SemanticFormula)

        with native_run(module, Probe, read("plan.json"), initialize):
            pass
    assert len(checked) >= 18
