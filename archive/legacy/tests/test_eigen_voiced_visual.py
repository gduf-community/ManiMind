"""Reading-only native regression; no runtime media, pixels or approval."""

import ast
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import validate_events
from manimind.review.content_regression import revision_required, validate_contract
from manimind.review.semantic_focus import audit_coverage, focus_windows, schedule
import test_eigen_visual as baseline_tests


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/eigen_voiced_visual.py"
BASE_SOURCE = ROOT / "examples/eigen_visual.py"
FIXTURE = ROOT / "tests/fixtures/eigen-voiced-visual"
BASE_FIXTURE = ROOT / "tests/fixtures/eigen-visual"
BASE_SHA = "9b28098232167167d994e346f6ea2ad61172936de0244d17f8d9acb7d0b5f2e1"


def data(name, folder=FIXTURE):
    return json.loads((folder / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "examples"))
        return load_lesson(SOURCE)


@pytest.fixture(scope="module")
def scenes(lesson):
    # The inherited semantic() resolves glyphs in the BASE module. Passing that
    # module patches only test placeholders, without changing the shared helper.
    with native_run(lesson.baseline, lesson.baseline.EigenDirectionsLesson,
                    data("plan.json", BASE_FIXTURE)) as original:
        pass
    with native_run(lesson.baseline, lesson.EigenDirectionsVoicedLesson,
                    data("plan-voiced-v002.json")) as revised:
        pass
    return original, revised


def test_baseline_bytes_and_only_two_overrides(lesson):
    assert hashlib.sha256(BASE_SOURCE.read_bytes()).hexdigest() == BASE_SHA
    cls, base = lesson.EigenDirectionsVoicedLesson, lesson.baseline.EigenDirectionsLesson
    assert cls.__bases__ == (base,)
    methods = {name for name, value in cls.__dict__.items() if callable(value)}
    assert methods == {"read", "construct"}
    for name, value in base.__dict__.items():
        if callable(value) and name not in methods:
            assert getattr(cls, name) is getattr(base, name)
    assert lesson.baseline.CUE_DURATIONS == (26, 22, 26, 24, 26, 40, 26, 20)
    tree = ast.parse(SOURCE.read_text())
    assert not {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)} & {
        "play", "wait", "get_time", "get_time_progression", "render", "tear_down"}
    assert all(not isinstance(node, ast.Assign) or not any(
        isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
        and target.value.id == "baseline" for target in node.targets)
        for node in ast.walk(tree))


def test_read_budgets_are_exact_measured_case_policy(lesson):
    measured = data("measured-speech-v001.json")
    windows = {row["id"]: row for row in data("native-clock-contract.json", BASE_FIXTURE)["windows"]}
    expected = {}
    segments = measured["segments"]
    assert len(segments) == 27
    assert [row["segment"] for row in segments] == data("narration-draft-v001.json", BASE_FIXTURE)["segments"]
    for row in segments:
        assert row["duration_seconds"] == row["frames"] / row["sample_rate"]
        assert row["channels"] == 1 and row["sample_width_bytes"] == 2
        assert row["sample_rate"] == 48000
        assert all(len(row[key]) == 64 for key in ("wav_sha256", "receipt_sha256"))
        window = windows[row["segment"]["focus"]]
        original = window["end"] - window["start"]
        duration = max(original, math.ceil(row["duration_seconds"] + measured["safety_seconds"]))
        if duration > original:
            expected[window["id"]] = duration
    assert measured["safety_seconds"] == .5
    assert measured["round_up_seconds"] == 1
    assert lesson.READ_DURATIONS == expected
    assert len(expected) == 17


def test_read_preserves_events_minima_and_unknown_ids(lesson, monkeypatch):
    calls = []
    monkeypatch.setattr(lesson.baseline.EigenDirectionsLesson, "read",
                        lambda self, identity, duration, event=None: calls.append((identity, duration, event)))
    scene = lesson.EigenDirectionsVoicedLesson.__new__(lesson.EigenDirectionsVoicedLesson)
    tree = ast.parse(BASE_SOURCE.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "read":
            identity, duration, event = map(ast.literal_eval, node.args)
            scene.read(identity, duration, event)
            assert calls[-1] == (identity, max(duration, lesson.READ_DURATIONS.get(identity, duration)), event)
    scene.read("future_unknown_focus", 13, "unchanged_event")
    assert calls[-1] == ("future_unknown_focus", 13, "unchanged_event")
    scene.read("definition", 99)
    assert calls[-1] == ("definition", 99, None)


def test_actual_native_clock_every_chapter_events_and_focus(scenes, lesson):
    original, scene = scenes
    plan, frozen = data("plan-voiced-v002.json"), data("native-clock-contract.json")
    assert scene.time == plan["duration"] == frozen["duration"] == 254
    assert scene.frame == frozen["frames"] == 7620
    assert tuple(cue["duration"] for cue in scene.cues) == lesson.CUE_DURATIONS
    assert sum(lesson.CUE_DURATIONS) == scene.time
    validate_events(scene.timeline, {"duration": scene.time, "events": scene.visual_events})
    assert not scene._open_focus
    for key, actual in (("chapters", scene.chapter_times), ("events", scene.visual_events),
                        ("windows", scene._closed_focus), ("symbol_transitions", scene.symbol_transitions),
                        ("plays", scene.plays)):
        assert frozen[key] == actual
    for chapter, cue in zip(scene.chapter_times, scene.cues, strict=True):
        assert chapter == {"id": cue["id"], "start": cue["start"], "end": cue["start"] + cue["duration"]}
    windows = focus_windows(json.loads(scene.out.files["focus-events.json"]), scene.time)
    assert set(windows) == {row["id"] for row in plan["focus_intents"]}
    for intent in plan["focus_intents"]:
        cue = next(cue for cue in scene.cues if cue["id"] == intent["cue"])
        window = windows[intent["id"]]
        assert cue["start"] <= window["start"] < window["end"] <= cue["start"] + cue["duration"]
    before = {row["id"]: row for row in original._closed_focus}
    extended = set()
    for identity, row in windows.items():
        prior = before[identity]
        old_length, new_length = prior["end"] - prior["start"], row["end"] - row["start"]
        assert new_length >= old_length
        if new_length > old_length:
            extended.add(identity)
    assert extended == set(lesson.READ_DURATIONS)
    assert json.loads(scene.out.files["eigen-motion.json"])["chapters"] == scene.chapter_times


@pytest.mark.parametrize("edge_margin", [.12, .25])
def test_all_27_complete_wavs_fit_production_scheduler(scenes, edge_margin):
    _, scene = scenes
    rows = data("measured-speech-v001.json")["segments"]
    focuses = json.loads(scene.out.files["focus-events.json"])
    durations = [row["frames"] / row["sample_rate"] for row in rows]
    aligned = schedule(scene.timeline, {"segments": [row["segment"] for row in rows]},
                       focuses, durations, edge_margin=edge_margin)
    assert len(aligned) == 27
    assert audit_coverage(aligned, focuses, scene.time)["passed"]
    windows = focus_windows(focuses, scene.time)
    previous = -.25
    for actual, measured in zip(aligned, rows, strict=True):
        window = windows[actual["focus"]]
        assert actual["text"] == measured["segment"]["text"]
        assert actual["duration_seconds"] == measured["duration_seconds"]
        assert actual["start"] >= window["start"] + edge_margin - 1e-9
        assert actual["end"] <= window["end"] - edge_margin + 1 / 48000
        assert actual["start"] >= previous + .25 - 1e-9
        previous = actual["end"]


def trajectories(scene):
    groups = defaultdict(list)
    for row in scene.motion_samples:
        key = (row["kind"], row.get("stage"))
        payload = {key: value for key, value in row.items() if key != "time"}
        rows = groups[key]
        # Extra static frames are the only permitted sample-count difference.
        if not rows or rows[-1][1] != payload:
            rows.append((row["time"], payload))
    return groups


def test_original_animation_durations_intermediate_forms_and_paths(scenes):
    original, revised = scenes
    assert len(original.plays) == len(revised.plays)
    for old, new in zip(original.plays, revised.plays, strict=True):
        assert new["end"] - new["start"] == pytest.approx(old["end"] - old["start"], abs=1e-12)
    assert original.labels == revised.labels
    for old, new in zip(original.symbol_transitions, revised.symbol_transitions, strict=True):
        assert {key: value for key, value in old.items() if key not in {"start", "end"}} == {
            key: value for key, value in new.items() if key not in {"start", "end"}}
        assert new["end"] - new["start"] == old["end"] - old["start"]
    before, after = trajectories(original), trajectories(revised)
    assert set(before) == set(after)
    for key in before:
        old, new = before[key], after[key]
        assert [row[1] for row in old] == [row[1] for row in new], key
        np.testing.assert_allclose([row[0] - old[0][0] for row in old],
                                   [row[0] - new[0][0] for row in new], atol=1e-12, rtol=0)


def test_revised_geometry_still_obeys_original_mathematical_invariants(scenes, lesson):
    _, scene = scenes
    baseline_tests.test_native_every_grid_endpoint_and_basis_share_one_matrix(scene, lesson.baseline)
    baseline_tests.test_native_recomposition_and_direct_image_agree_throughout(scene, lesson.baseline)
    baseline_tests.test_native_rotation_uses_a_true_turn_not_a_length_change(scene, lesson.baseline)
    baseline_tests.test_native_symbol_routes_settle_before_reading(scene)


def test_plan_keeps_teaching_and_revision_gate_contract():
    plan, previous = data("plan-voiced-v002.json"), data("plan.json", BASE_FIXTURE)
    assert revision_required(plan)
    assert plan["scene_class"] == "EigenDirectionsVoicedLesson"
    assert plan["sources"] == ["examples/eigen_visual.py", "src/manimind/components/catalog.py"]
    for key in ("title", "workflow_profile", "subtitle_reserve", "audience", "prior_knowledge",
                "understanding_goals", "source_references", "mathematical_facts", "focus_intents"):
        assert plan[key] == previous[key]
    for old, new in zip(previous["cues"], plan["cues"], strict=True):
        assert {key: value for key, value in old.items() if key != "duration"} == {
            key: value for key, value in new.items() if key != "duration"}
        assert new["duration"] >= old["duration"]
    contract = validate_contract(data("revision-contract-voiced-v002.json"))
    assert len(contract["units"]) == 8
    assert [unit["baseline_interval"] for unit in contract["units"]] == [
        [0, 26], [26, 48], [48, 74], [74, 98], [98, 124], [124, 164], [164, 190], [190, 210]]
    assert contract["assets"]["v001"]["duration"] == 210
    assert contract["assets"]["v001"]["sha256"] == "d2ebebb3dc365d95791ce94fb723935765e854796a82a6a94618ec3ba21676f2"
    assert all(any(feature["kind"] == "process" for feature in unit["features"]) for unit in contract["units"])
    assert not {"status", "release_authorized", "bindings", "outcome"} & set(contract)
    assert plan["revision_review"] == "runtime/sessions/knowledge-trio-voice-20261028/review-eigen-regression-v002.json"
    for value in [contract, *plan["state_contracts"]]:
        assert all(value.get(key) for key in ("writer", "consumers", "lifecycle", "invalidation"))
    boundary = plan["production_boundary"]
    assert all(boundary[key] is False for key in (
        "rendered", "visual_approved", "content_regression_approved", "narration_approved", "audio_generated"))


def test_renderer_watches_wrapper_base_catalog_and_revision_contract():
    from manimind.postproduce.understanding_render import sources

    plan = data("plan-voiced-v002.json")
    watched = sources(plan)
    assert all(ROOT / name in watched for name in (
        plan["scene"], "examples/eigen_visual.py", "src/manimind/components/catalog.py",
        plan["revision_contract"], "src/manimind/review/content_regression.py"))
    assert plan["review_times"] == sorted(set(plan["review_times"]))
    assert all(0 <= time < plan["duration"] for time in plan["review_times"])
    frozen = data("native-clock-contract.json")
    for transition in frozen["symbol_transitions"]:
        assert all(time in plan["review_times"] for time in (
            transition["start"], (transition["start"] + transition["end"]) / 2, transition["end"]))


@pytest.mark.parametrize("mutation", ["mismatch", "missing", "extra"])
def test_construct_rejects_incompatible_cue_budgets(lesson, mutation):
    plan = deepcopy(data("plan-voiced-v002.json"))
    if mutation == "mismatch":
        plan["cues"][0]["duration"] -= 1
    elif mutation == "missing":
        plan["cues"].pop()
    else:
        plan["cues"].append({**plan["cues"][-1], "id": "unexpected"})
    with pytest.raises(ValueError):
        with native_run(lesson.baseline, lesson.EigenDirectionsVoicedLesson, plan):
            pass
