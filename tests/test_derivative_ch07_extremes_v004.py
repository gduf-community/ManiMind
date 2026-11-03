"""not_reviewed: CH07-Q01 quantifier, coverage and intact-audio author checks."""

from fractions import Fraction
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_ch07_extremes_v003 import probe_class, initialize_probe
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule, transport_segments
from manimind.review.content_regression import validate_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/"tests/fixtures/derivative-ch07-extremes-v004"
SOURCE = ROOT/"examples/derivative_ch07_extremes_v004.py"


def read(name):
    return json.loads((FIXTURE/name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_production_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT/"runtime"):
            raise AssertionError("Use only new chapter-07 isolated fixtures")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    with native_run(lesson, probe_class(lesson.DerivativeCh07ExtremesV004), read("plan.json"), initialize_probe) as scene:
        yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
        {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def stage(scene, key):
    return next(s for s in scene.stage_trace if s["cue"] == "open_interval" and s["key"] == key)


def texts(snapshot):
    return {r["text"] for r in snapshot["text"]}


def test_old_global_local_increase_is_false_and_right_branch_helper_rejects_it(lesson):
    assert lesson.value(Fraction(1, 2)) == Fraction(1, 4)
    assert lesson.value(Fraction(3, 5)) == Fraction(4, 25)
    assert lesson.value(Fraction(3, 5)) < lesson.value(Fraction(1, 2))
    for x in [Fraction(1, 2), 0, 1, 3]:
        with pytest.raises(ValueError, match="1 < x < 3"):
            lesson.right_comparator(x)


@pytest.mark.parametrize("x", [Fraction(1, 1000000), Fraction(1, 2), Fraction(3, 5), Fraction(999, 1000), Fraction(1),
    Fraction(1001, 1000), Fraction(3, 2), Fraction(2), Fraction(5, 2), Fraction(2999999, 1000000)])
def test_whole_domain_higher_witness_uses_exact_values_not_only_right_moving_example(lesson, x):
    y = lesson.open_higher_witness(x)
    assert 0 < x < 3 and 1 < y < 3
    assert 0 <= lesson.value(x) < lesson.value(y) < 4
    if x <= 1:
        assert y == 2 and lesson.value(x) < 1 == lesson.value(y)
    else:
        assert x < y < 3 and y == (x+3)/2
        assert lesson.value(y)-lesson.value(x) == (y-x)*(x+y-2) > 0


@pytest.mark.parametrize("epsilon", [Fraction(1, 10), Fraction(1, 100), Fraction(1, 10000)])
def test_four_is_least_upper_bound_not_only_an_unattained_number(lesson, epsilon):
    h = min(Fraction(1, 2), epsilon/8)
    x = 3-h
    assert 1 < x < 3
    gap = 4-lesson.value(x)
    assert gap == 4*h-h*h
    assert 0 < gap < epsilon
    assert lesson.value(1) == 0


def test_right_scope_and_generic_proof_precede_the_entire_original_comparison(native, placement):
    row = next(r for r in placement if r["id"] == "ch07-open_interval")
    phrase = next(p for p in row["phrases"] if p["id"] == "open_interval-r2")
    ready = stage(native, "0.38")
    assert ready["after"] < phrase["visual_start"]
    scoped = texts(ready["native_objects_after"])
    assert "递增右支：1 < x < 3" in scoped
    assert r"y=(x+3)/2,\quad x<y<3" in scoped
    assert r"f(y)-f(x)=(y-x)(x+y-2)>0" in scoped
    assert scoped <= texts(stage(native, "0.67")["native_objects_after"])
    # The raw universal clause is unchanged; its actual on-screen x-range is
    # now restricted before, during and after that clause, not just in intent.
    assert "只要x还小于三" in phrase["text"]
    for local in [24.46, 27.3, 30.12]:
        when = row["start"]+local
        assert ready["after"] < when < stage(native, "0.67")["after"]
    assert stage(native, "0.70")["after"] > phrase["visual_end"]


def test_global_case_coverage_bound_limit_and_minimum_are_actual_native_objects(native, placement):
    row = next(r for r in placement if r["id"] == "ch07-open_interval")
    snapshot = native.focus_points["unattained_supremum"]["start"]
    visible = texts(snapshot)
    assert {
        "全域比较：左段与右支",
        r"0<x\le1:\quad f(x)<1=f(2)",
        r"1<x<3:\quad x<y<3,\ f(x)<f(y)",
        r"0\le f(x)<4\quad(0<x<3)",
        r"x\to3^-:\ f(x)\to4",
        r"\min f=0\quad(x=1)",
        "上确界为 4，无最大值；最小值仍为 0",
    } <= visible
    assert "递增右支：1 < x < 3" not in visible
    assert stage(native, "0.74")["after"] < row["start"]+37.46
    assert snapshot == native.focus_points["unattained_supremum"]["end"]
    assert any(p == pytest.approx(lesson_point(2, 1)) for p in snapshot["dots"])


def lesson_point(x, y):
    return [-5.7+1.9*x, -1.75+.8*y, 0]


def test_full_construct_same_clock_all_original_units_refs_and_complete_wavs(native, placement):
    assert native.time == pytest.approx(322.2)
    assert len(placement) == 7
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(297.44)
    assert len(native._closed_focus) == 19 and not native._open_focus
    assert transport_segments(read("narration.json")) == read("speech-plan.json")["segments"]
    assert [c["duration"] for c in read("plan.json")["cues"]] == [c["duration"] for c in read("baseline-plan.json")["cues"]]
    for row, prior in zip(placement, read("baseline-placement.json")["units"], strict=True):
        assert row["id"] == prior["id"] and row["duration_seconds"] == prior["duration_seconds"]
        assert abs(row["start"]-prior["start"]) <= 1/48000+.000001
        for p in row["phrases"]:
            assert p["focus_start"] <= p["visual_start"]+.000001
            assert p["visual_end"] <= p["focus_end"]+.000001


def test_all_other_native_methods_math_and_semantic_variable_motions_remain_inherited(lesson, native):
    import derivative_ch07_extremes_v003 as prior
    for name in ["construct", "beat", "graph", "opening", "candidates", "compare", "parameter", "conditions", "closing"]:
        assert getattr(lesson.DerivativeCh07ExtremesV004, name) is getattr(prior.DerivativeCh07ExtremesV003, name)
    moving = [r for r in native.motion_samples if r["kind"] == "moving_endpoint"]
    assert moving[0]["b"] == pytest.approx(1.25) and moving[-1]["b"] == pytest.approx(3)
    assert any(r["b"] == 2 and r["argmax"] == (0, 2) for r in moving)
    approach = [r for r in native.motion_samples if r["kind"] == "open_approach"]
    assert approach[0]["x"] == pytest.approx(2.2) and approach[-1]["x"] == pytest.approx(2.99)
    assert all(1 < r["x"] < 3 and r["value"] < 4 and r["gap"] > 0 for r in approach)


def test_true_current_v003_baseline_inventory_keeps_defect_separate_from_retention():
    contract = read("contract.json")
    validate_contract(contract)
    assert contract["assets"]["visual_v003"]["sha256"] == "2627e4f747146788939748cf0c82389da5fe003ba7caa76f5e47184b040d869b"
    assert contract["assets"]["captioned_v003"]["sha256"] == "3a45ab56516e65c0f6dfe865de566994b89a32831b50395bb60fa02febec1ba0"
    assert all(a["duration"] == 322.2 for a in contract["assets"].values())
    assert sum(len(u["features"]) for u in contract["units"]) == 23
    assert contract["known_baseline_defect"]["finding_id"] == "CH07-Q01"
    for u in contract["units"]:
        assert u["asset"] == "visual_v003"
        for f in u["features"]:
            assert "/visual-v003/" in f["baseline_samples"][0]["frame"]
            assert "outcome" not in f
            assert u["baseline_interval"][0] <= f["baseline_interval"][0] < f["baseline_interval"][1] <= u["baseline_interval"][1]
            if f["kind"] == "process":
                assert [s["phase"] for s in f["baseline_samples"]] == ["before", "during", "after"]
    assert read("plan.json")["revision_review"].endswith("/review/regression-v004.json")
    assert read("narration.json")["revision"]["text_changed"] is False
