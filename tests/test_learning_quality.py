from copy import deepcopy

import pytest

from manimind.review.learning_quality import (
    DIMENSIONS, quality_score, runtime_wrap, subtitle_audit, validate_learning_review,
)


def review(rating=4):
    return {"action": "review", "status": "pass",
            "viewer_test": {"can_explain": "Observed relation", "missing_links": [],
                            "transfer_question": "A new parameter", "supported_answer": "Supported by the relation"},
            "quality": {k: {"rating": rating, "evidence": "2s actual frame"} for k in DIMENSIONS}}


def test_fixed_weights_and_thresholds():
    assert sum(DIMENSIONS.values()) == 100
    assert quality_score(review()["quality"]) == 100
    assert quality_score(review(3)["quality"]) == 75
    with pytest.raises(ValueError, match="threshold"):
        validate_learning_review(review(3), whole=True)
    data = review()
    data["quality"]["causality"]["rating"] = 2
    assert quality_score(data["quality"]) > 80
    with pytest.raises(ValueError, match="critical"):
        validate_learning_review(data, whole=True)
    data["status"] = "revise"
    validate_learning_review(data, whole=True)


@pytest.mark.parametrize("changed", ["missing", "fraction", "boolean", "evidence"])
def test_quality_requires_all_evidence_backed_integer_ratings(changed):
    data = review()["quality"]
    if changed == "missing": del data["science"]
    if changed == "fraction": data["science"]["rating"] = 3.5
    if changed == "boolean": data["science"]["rating"] = True
    if changed == "evidence": data["science"]["evidence"] = ""
    with pytest.raises(ValueError): quality_score(data)


def test_viewer_test_is_not_optional_or_an_author_intent_summary():
    data = review()
    del data["viewer_test"]
    with pytest.raises(ValueError, match="viewer_test"):
        validate_learning_review(data, whole=False)
    validate_learning_review({"action": "inspect_frames"}, whole=False)


def timeline(text):
    return {"duration": 10, "cues": [{"id": "a", "start": 0, "duration": 10,
            "spoken": text, "spoken_spans": [{"start": .3, "end": 9, "text": text}]}]}


def test_wrap_and_audit_detect_orphan_punctuation_without_rewriting_text():
    data = timeline("ABCDEFGHIJKL.")
    original = deepcopy(data)
    assert runtime_wrap(data["cues"][0]["spoken"], len) == ["ABCDEFGHIJKL", "."]
    audit = subtitle_audit(data, len)
    assert len(audit["blockers"]) == 1
    assert audit["rows"][0]["lines"][-1] == "."
    assert data == original


def test_subtitle_long_span_is_advisory_not_an_arbitrary_content_limit():
    audit = subtitle_audit(timeline("A" * 41), lambda s: len(s) / 3)
    assert not audit["blockers"]
    assert audit["advisories"][0]["characters"] == 41


def test_missing_measured_subtitles_and_overlapping_spans_are_blocked():
    data = timeline("Speech")
    data["cues"][0]["spoken_spans"] = []
    assert subtitle_audit(data, len)["blockers"]
    data = timeline("Speech")
    data["cues"][0]["spoken_spans"].append({"start": .2, "end": 3, "text": "Later"})
    assert subtitle_audit(data, len)["blockers"]
