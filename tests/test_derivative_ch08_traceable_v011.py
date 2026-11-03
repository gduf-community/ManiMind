"""Native objects, role clocks and intact original units; never pixel approval.

Writer: 01a19f93-c389-7732-b292-5b8fc1d74f50; consumers: author/main/CI.
Lifecycle: this source/fixture version; source, plan or native API invalidates.
"""

import ast
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.postproduce.traceable_film import validate_selection
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, transport_segments

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/derivative-ch08-traceable-v011"
SOURCE = ROOT / "examples/derivative_ch08_traceable_v011.py"


def read(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def fixture_only(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        if any(path.resolve().is_relative_to(ROOT / name) for name in ("runtime", "outputs")):
            raise AssertionError("Tests must not read mutable production/review state")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    class Probe(lesson.DerivativeCh08TraceableV011):
        def mark(self, identity):
            super().mark(identity)
            self.states[identity] = [dict(tex=obj.get_tex(), center=obj.get_center().tolist(), opacity=float(obj.get_opacity()))
                for mob in self.mobjects for obj in mob.get_family() if hasattr(obj, "get_tex") and obj.get_opacity() > .9]

    def initialize(scene):
        scene.states = {}

    with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
        yield scene


def test_only_requested_lesson_methods_change(lesson):
    base = sys.modules["derivative_ch08_optimization_v004"].DerivativeCh08OptimizationV004
    for name in ("construct", "opening", "cut", "fold", "boundary", "constraint", "net", "panels", "beat"):
        assert getattr(lesson.DerivativeCh08TraceableV011, name) is getattr(base, name)
    old, new = read("baseline-plan.json"), read("plan.json")
    assert old["duration"] == new["duration"]
    assert old["intended_full_wav_placement"] == new["intended_full_wav_placement"]
    for a,b in zip(old["cues"],new["cues"],strict=True):
        if a["id"] not in ("objective","optimize","closing"):
            assert a == b


def test_complete_original_text_transport_references_and_clock(native):
    plan, narration, timing = read("plan.json"), read("narration.json"), read("timings.json")
    assert narration["units"] == read("baseline-narration.json")["units"]
    assert transport_segments(narration) == transport_segments(read("baseline-narration.json"))
    assert native.time == pytest.approx(381.366666667)
    assert not native._open_focus
    placements = schedule(visual_timeline(plan), narration, {"duration":native.time,"windows":native._closed_focus}, timing)
    assert len(placements) == 8
    assert sum(len(row["references"]) for row in placements) == 22
    assert sum(row["duration_seconds"] for row in placements) == pytest.approx(358.88)
    for placed, intended, measured in zip(placements,plan["intended_full_wav_placement"],timing["units"],strict=True):
        assert abs(placed["start"]-intended["intended_start"]) < .04
        assert intended["wav_sha256"] == measured["wav_sha256"]
        assert placed["end"]-placed["start"] == pytest.approx(measured["duration_seconds"])
        assert not any(intended[k] for k in ("audio_trimmed","speed_changed","regenerated"))


STAGES = [row["id"] for row in read("plan.json")["formula_transitions"] if not row["id"].startswith("closing_")]


@pytest.mark.parametrize("stage", STAGES)
def test_role_motion_has_true_departure_intermediate_and_arrival(native, stage):
    rows = [r for r in native.motion_samples if r["kind"] == "ch08_role_transfer" and r["stage"] == stage]
    assert len(rows) >= 40
    assert rows[-1]["time"]-rows[0]["time"] >= 1.9
    np.testing.assert_allclose(rows[0]["moving"],rows[0]["sources"],atol=1e-5)
    if stage not in ("inner_derivative", "feasible_candidate"):
        assert any(np.linalg.norm(np.array(a)-b) > .15 for a,b in zip(rows[0]["moving"],rows[0]["targets"],strict=True))
    elif stage == "inner_derivative":
        assert rows[0]["active_parent_retired_before_motion"]
        assert "(12-2x)'" in native.labels and "(-2)" in native.labels
    else:
        assert rows[0]["active_parent_retired_before_motion"]
        assert r"6\notin(0,6):\ 12-2\cdot6=0" in native.labels
    np.testing.assert_allclose(rows[-1]["moving"],rows[-1]["targets"],atol=1e-4)
    assert len(rows[0]["roles"]) == len(set(rows[0]["roles"]))


@pytest.mark.parametrize("stage", ["equal_bases_to_square","inner_derivative","combine_remainder","two_negatives_and_factor_order","feasible_candidate","optimum_evaluation"])
def test_active_expression_parent_removed_before_role_motion(native, stage):
    rows = [r for r in native.motion_samples if r["kind"] == "ch08_role_transfer" and r["stage"] == stage]
    assert all(r["active_parent_retired_before_motion"] and not r["retained_source"] for r in rows)


def test_explicit_separate_roles_for_equal_bases_and_derivative_sources(native):
    stages = {r["stage"]:r for r in native.motion_samples if r["kind"] == "ch08_role_transfer"}
    assert stages["dimensions_into_volume"]["roles"] == ["length_value","width_value","box_height"]
    assert stages["equal_bases_to_square"]["roles"] == ["second_equal_base_counts_twice","one_base","height_factor","volume_identity"]
    assert stages["product_rule_sources"]["roles"] == ["differentiate_height","retain_square","retain_height","differentiate_square"]
    assert "inner_function_derivative" in stages["outer_square_derivative"]["roles"]
    assert "same_common_from_second_product" in stages["extract_common_factor"]["roles"]
    assert "first_linear_factor_root_six" in stages["factor_signed_constants"]["roles"]
    assert "second_linear_factor_root_two" in stages["factor_signed_constants"]["roles"]


def test_intermediate_formula_operations_and_units_really_constructed(native):
    required = [r"\ell=", "w=", "h=", r"\mathrm{cm}\cdot\mathrm{cm}\cdot\mathrm{cm}=\mathrm{cm}^3",
                "(x)'", "[(12-2x)^2]'", "(12-2x)'", "(-2)", "(-6)", "(x-2)", "(x-6)",
                r"6\notin(0,6):\ 12-2\cdot6=0", r"(12-2\cdot", "8^2", r"=128\ \mathrm{cm}^3"]
    for tex in required:
        assert tex in native.labels
    assert "长度用 cm；h 是盒高" in native.labels
    assert "形状取 x = 2 示意；尺寸式适用于任意可行 x" in native.labels
    assert not any(r["tex"]=="4x" for r in native.states["factor_signed_constants_complete"])


def test_closing_rejection_moves_out_before_current_result(native):
    marks = {r["id"]:r["time"] for r in native.visual_events}
    assert marks["closing_old_values_cleared"] < marks["closing_old_solution_excluded"]
    assert not any("128" in r["tex"] or r"8\times8\times2" in r["tex"] for r in native.states["closing_old_values_cleared"])
    assert marks["closing_old_solution_excluded"] < marks["closing_rejection_relocated"] < marks["closing_current_box_ready"] < marks["closing_current_optimum_ready"]
    current = native.states["closing_current_optimum_ready"]
    assert any("108" in r["tex"] for r in current)
    assert not any("128" in r["tex"] for r in current)
    assert not any(r"8\times8\times2" in r["tex"] for r in current)
    rows = [r for r in native.motion_samples if r["kind"] == "closing_binding" and r["min_height_cm"]==3]
    assert rows[0]["x_cm"] == 2 and not rows[0]["feasible"]
    assert rows[-1]["x_cm"] == pytest.approx(3) and rows[-1]["feasible"]
    assert rows[-1]["volume_cm3"] == pytest.approx(108)
    assert all(not r["feasible"] for r in rows if r["x_cm"] < 3-1e-9)
    closing_start=sum(c["duration"] for c in read("plan.json")["cues"][:-1])
    assert all(r["x_cm"]==2 for r in rows if r["time"] < closing_start+32.4-1/30)


def test_current_v004_complete_inventory_and_frozen_gate_inputs():
    plan, contract = read("plan.json"), read("contract.json")
    validate_contract(contract)
    validate_selection(plan["formula_transitions"])
    assert set(contract["assets"]) == {"visual_v004","captioned_v004"}
    assert all(unit["asset"] == "visual_v004" for unit in contract["units"])
    assert len(contract["units"]) == 8
    assert sum(len(u["features"]) for u in contract["units"]) == 31
    assert {"original_condition_label","closing_same_box_parameter","current_result_dimensions"} <= {f["id"] for u in contract["units"] for f in u["features"]}
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19f93-c389-7732-b292-5b8fc1d74f50"
    assert contract["improvement_targets"] == plan["formula_transitions"]
    for source in ("traceable_film.py","traceable_film_v2.py","formula-continuity.md","formula-continuity-v2.md", "derivative_ch08_optimization_v004.py"):
        assert any(s.endswith(source) for s in plan["sources"])
    assert set(plan["formula_review_times"]) == {r["id"] for r in plan["formula_transitions"]}
    for times in plan["formula_review_times"].values():
        assert times["before"] < times["during"] < times["after"]
        assert set(times.values()) <= set(plan["review_times"])
    assert hashlib.sha256((FIX/"narration.json").read_bytes()).hexdigest() == plan["narration_draft_sha256"]
    for value in (plan,contract,read("narration.json")):
        assert all(value[k] for k in ("writer","consumers","lifecycle","invalidation"))


def test_no_opaque_matching_global_edit_sound_or_publish_calls():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
    names = {n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    assert not calls & {"render","add_sound","publish","align_plan","urlopen"}
    assert not names & {"TransformMatchingTex","TransformMatchingShapes","matching_transform","copy_formula_transform"}


def test_partial_signed_factor_product_never_asserts_complete_derivative(native):
    rows = [r for r in native.motion_samples if r["kind"] == "ch08_role_transfer" and r["stage"] == "factor_signed_constants"]
    assert rows and all(r["deferred_relation"] and not r["target_relation_visible"] for r in rows)
    installed = [r for r in native.motion_samples if r["kind"] == "ch08_complete_relation" and r["stage"] == "factor_signed_constants"]
    assert len(installed) == 1 and installed[0]["relation_visible"]
    assert installed[0]["installed_factor_roles"] == ["constant1", "root6", "constant2", "root2"]
    assert installed[0]["time"] >= rows[-1]["time"]
    assert "分解两个一次因子" in native.labels



def test_same_implementation_probe_reserves_positive_frame_span(lesson):
    class StrictFrames(lesson.DerivativeCh08TraceableProbeV011):
        def at(self, offset, *animations, **kwargs):
            target = round((self._cue["start"] + offset) * self.camera.fps)
            current = round(self.get_time() * self.camera.fps)
            assert target >= current
            if animations:
                assert target > current, (offset, self.get_time())
            return super().at(offset, *animations, **kwargs)
    with native_run(lesson, StrictFrames, read("probe-plan.json")) as scene:
        assert scene.time == pytest.approx(read("probe-plan.json")["duration"])

