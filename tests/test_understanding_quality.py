import copy
import json
from pathlib import Path

import pytest

from manimind.review import understanding_quality as subject
from manimind.review.learning_quality import DIMENSIONS


def review():
    return {"action": "review", "status": "pass", "release_authorized": True,
            "listening_reviewed": False, "student_tested": False, "blocking_findings": [],
            "viewer_test": {"can_explain": "A visible causal reason", "missing_links": [],
                            "transfer_question": "A new instance", "supported_answer": "Reason supported by pixels, not tested students"},
            "quality": {name: {"rating": 4, "evidence": "3s actual state"} for name in DIMENSIONS},
            "editorial_checks": {name: {"status": "pass", "evidence": [{"time": 3, "finding": "Actual visible evidence"}]}
                                 for name in subject.CHECKS}}


def test_complete_editorial_verdict_with_real_time_references():
    subject.validate_editorial_review(review(), duration=20)


@pytest.mark.parametrize("change", ["missing", "outside", "no_evidence", "blocker", "revoke", "hearing", "students", "weak", "contradiction"])
def test_engineering_pass_cannot_replace_editorial_approval(change):
    value = review()
    if change == "missing":
        del value["editorial_checks"]["mechanism"]
    elif change == "outside":
        value["editorial_checks"]["attention"]["evidence"][0]["time"] = 25
    elif change == "no_evidence":
        value["editorial_checks"]["pacing"]["evidence"] = []
    elif change == "blocker":
        value["blocking_findings"] = ["A result becomes unreadable during its explanation"]
    elif change == "revoke":
        value["release_authorized"] = False
    elif change == "hearing":
        value["listening_reviewed"] = True
    elif change == "students":
        value["student_tested"] = True
    elif change == "weak":
        value["quality"]["causality"]["rating"] = 2
    else:
        value["editorial_checks"]["mechanism"]["status"] = "revise"
    with pytest.raises(ValueError):
        subject.validate_editorial_review(value, duration=20)


def test_silent_review_can_distinguish_absent_audio_from_audio_approval():
    value = review()
    value["editorial_checks"]["meaning_alignment"]["status"] = "not_applicable"
    subject.validate_editorial_review(value, stage="visual", duration=20)
    with pytest.raises(ValueError):
        subject.validate_editorial_review(value, stage="narration", duration=20)


def test_guidance_has_no_fixed_shot_or_voice_contract_and_legacy_profile_is_untouched():
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root / "configs/visual-first-workflow-v2.json").read_text())
    assert set(profile["review_checks"]) == set(subject.CHECKS)
    assert not {"shot_count", "voice", "palette", "fixed_duration", "mandatory_character"} & profile.keys()
    assert json.loads((root / "configs/visual-first-workflow-v1.json").read_text())["version"] == "visual-first-v1"


def test_editorial_revision_preserves_review_contract_without_new_production_limits():
    root = Path(__file__).resolve().parents[1]
    base = json.loads((root / "configs/visual-first-workflow-v3.json").read_text())
    profile = json.loads((root / "configs/visual-first-workflow-v3.1.json").read_text())
    assert profile["version"] == base["version"]
    assert profile["review"] == base["review"]
    assert profile["revision_policy"] == base["revision_policy"]
    assert set(profile["review_checks"]) == set(subject.CHECKS)
    assert len(profile["author_guidance"]) > len(base["author_guidance"])
    assert not {"shot_count", "voice", "palette", "fixed_duration", "mandatory_character"} & profile.keys()
