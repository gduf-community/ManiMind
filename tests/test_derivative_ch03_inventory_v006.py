"""Observable inventory correction only, never a mathematical or media approval."""

from copy import deepcopy
import json
from pathlib import Path

from manimind.review.content_regression import validate_contract


FIXTURES = Path(__file__).parent / "fixtures/derivative-ch03-rules-v006"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_all_thirty_functions_and_exact_math_conditions_remain():
    old, new = read("previous-contract.json"), read("contract.json")
    validate_contract(new)
    assert old["assets"] == new["assets"]
    assert len(old["units"]) == len(new["units"])
    assert sum(len(u["features"]) for u in new["units"]) == 30
    for before, after in zip(old["units"], new["units"], strict=True):
        expected = deepcopy(before)
        if before["id"] == "product_limit":
            target = next(f for f in expected["features"] if f["id"] == "normalized_corner_motion")
            target["claim"] = new["baseline_inventory_corrections"][-1]["current_claim"]
        assert after == expected


def test_scene_time_focus_transport_and_all_old_input_sources_are_unchanged():
    old, new = read("previous-plan.json"), read("plan.json")
    for key in ("scene", "scene_class", "duration", "fps", "resolution", "cues", "focus_intents",
                "narration_draft", "review_times", "intended_full_wav_placement", "timing_provenance"):
        assert new.get(key) == old.get(key), key
    assert set(old["sources"]).issubset(new["sources"])
    assert new["revision_contract"].endswith("contract-v006.json")
    assert new["revision_review"].endswith("regression-v006.json")


def test_both_failed_inventory_observations_remain_explicit_without_authorization():
    old, new = read("previous-contract.json"), read("contract.json")
    corrections = new["baseline_inventory_corrections"]
    assert corrections[0] == old["baseline_inventory_correction"]
    assert new["baseline_inventory_correction"] == old["baseline_inventory_correction"]
    latest = corrections[-1]
    assert "0.025" in latest["previous_claim"]
    assert "0.025" not in latest["current_claim"]
    assert latest["features_removed"] == []
    assert latest["source_or_timing_changed"] is False
    assert latest["narration_changed"] is False
    assert latest["approval_transferred"] is False
    assert latest["inventory_audit"]["all_feature_claims_read"] == 30
    assert new["status"] == read("plan.json")["status"] == "not_reviewed"
    assert len(latest["observation"]["sha256"]) == 64


def test_precision_policy_cannot_replace_retention_or_math_conditions():
    policy = read("contract.json")["numeric_readout_scope"]
    assert "error or loss remains blocking" in policy["mathematical_statements"]
    assert "All30 functions" in policy["retention"]
    assert "rounded pixels" in policy["dynamic_readouts"]
    assert read("plan.json")["numeric_readout_scope"] == policy
