"""Metadata-only inventory correction checks, never pixel or audio approval."""

from copy import deepcopy
import json
from pathlib import Path

from manimind.review.content_regression import validate_contract


FIXTURES = Path(__file__).parent / "fixtures/derivative-ch03-rules-v005"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_every_teaching_function_and_original_baseline_remains():
    old, new = read("previous-contract.json"), read("contract.json")
    validate_contract(new)
    assert old["assets"] == new["assets"]
    assert len(new["units"]) == len(old["units"])
    assert sum(len(row["features"]) for row in new["units"]) == 30
    for before, after in zip(old["units"], new["units"], strict=True):
        expected = deepcopy(before)
        if before["id"] == "linearity":
            target = next(f for f in expected["features"] if f["id"] == "linked_increment_bars")
            target["claim"] = new["baseline_inventory_correction"]["current_claim"]
        assert expected == after


def test_scene_time_focus_motion_narration_and_transport_inputs_are_unchanged():
    old, new = read("previous-plan.json"), read("plan.json")
    for key in ("scene", "scene_class", "duration", "fps", "resolution", "cues", "focus_intents",
                "narration_draft", "review_times", "intended_full_wav_placement", "timing_provenance"):
        assert new.get(key) == old.get(key), key
    assert new["revision_mode"] == old["revision_mode"] == "revision"
    assert new["revision_contract"].endswith("contract-v005.json")
    assert new["revision_review"].endswith("regression-v005.json")
    assert set(old["sources"]).issubset(new["sources"])


def test_correction_is_explicit_bound_and_not_approval():
    plan, contract = read("plan.json"), read("contract.json")
    correction = contract["baseline_inventory_correction"]
    assert plan["baseline_inventory_correction"] == correction
    assert correction["previous_claim"] != correction["current_claim"]
    assert "0.5" in correction["previous_claim"] and "0.05" in correction["previous_claim"]
    assert "0.5" not in correction["current_claim"] and "0.05" not in correction["current_claim"]
    assert correction["features_removed"] == []
    assert correction["approval_transferred"] is False
    assert correction["source_or_timing_changed"] is False
    assert correction["narration_changed"] is False
    assert len(correction["observation"]["sha256"]) == 64
    assert plan["status"] == contract["status"] == "not_reviewed"
