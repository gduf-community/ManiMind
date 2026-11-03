import copy

import pytest

from manimind.review import semantic_focus as subject


def data(topic="projectile"):
    return ({"duration": 20, "cues": [{"id": topic, "start": 0, "duration": 20}]},
            {"segments": [{"id": "N01", "cue": topic, "focus": "result", "text": "A complete explanation."}]},
            {"duration": 20, "windows": [{"id": "result", "start": 6, "end": 12}]})


@pytest.mark.parametrize("topic", ["projectile", "derivative", "eigenvectors", "chemistry"])
def test_same_rule_applies_across_topics_without_a_lesson_template(topic):
    timeline, narration, focuses = data(topic)
    result = subject.schedule(timeline, narration, focuses, [3])
    assert result[0]["start"] == pytest.approx(6.12)
    assert result[0]["end"] < 12
    assert subject.audit_coverage(result, focuses, 20)["passed"]


def test_after_anchor_is_insufficient_if_the_result_has_already_left():
    timeline, narration, focuses = data()
    with pytest.raises(ValueError, match="exceeds readable focus"):
        subject.schedule(timeline, narration, focuses, [8])
    audit = subject.audit_coverage([{"id": "N01", "focus": "result", "start": 7, "end": 15}], focuses, 20)
    assert not audit["passed"]


def test_previous_start_anchor_rule_reproduces_the_known_false_positive():
    from manimind.postproduce.visual_narration import schedule as legacy_schedule
    timeline, narration, focuses = data()
    old_segment = {"id": "N01", "cue": "projectile", "anchor_time": 6, "relation": "after", "text": "The result is still being explained."}
    old = legacy_schedule(timeline, [old_segment], [8])
    assert old[0]["start"] >= 6 and old[0]["end"] > focuses["windows"][0]["end"]
    with pytest.raises(ValueError, match="exceeds readable focus"):
        subject.schedule(timeline, narration, focuses, [8])


def test_prediction_question_cannot_extend_past_answer_reveal():
    timeline, narration, focuses = data()
    focuses["windows"][0].update(id="predict", start=0, end=4)
    narration["segments"][0]["focus"] = "predict"
    with pytest.raises(ValueError, match="never silently speed up"):
        subject.schedule(timeline, narration, focuses, [5])


def test_arbitrary_sentence_count_and_multiple_sentences_per_focus():
    timeline, narration, focuses = data()
    narration["segments"] = [{"id": f"N{i:02d}", "cue": "projectile", "focus": "result", "text": str(i)}
                             for i in range(1, 4)]
    rows = subject.schedule(timeline, narration, focuses, [1, 1, 1])
    assert len(rows) == 3 and rows[-1]["end"] < 12
    assert rows[1]["start"] - rows[0]["end"] >= .25


@pytest.mark.parametrize("change", ["duplicate", "reverse", "nan", "duration", "empty"])
def test_invalid_measured_windows_cannot_be_used(change):
    _, _, focuses = data()
    if change == "duplicate":
        focuses["windows"].append(copy.deepcopy(focuses["windows"][0]))
    elif change == "reverse":
        focuses["windows"][0]["end"] = 2
    elif change == "nan":
        focuses["windows"][0]["start"] = float("nan")
    elif change == "duration":
        focuses["duration"] = 19
    else:
        focuses["windows"] = []
    with pytest.raises(ValueError):
        subject.focus_windows(focuses, 20)


@pytest.mark.parametrize("field,value", [("id", "N01"), ("focus", "stale"), ("text", " ")])
def test_stale_or_ambiguous_narration_is_rejected(field, value):
    timeline, narration, focuses = data()
    if field == "id":
        narration["segments"].append(dict(narration["segments"][0]))
    else:
        narration["segments"][0][field] = value
    with pytest.raises(ValueError):
        subject.validate_narration(narration, timeline, focuses)
