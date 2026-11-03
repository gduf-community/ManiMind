from copy import deepcopy

import pytest

from manimind.postproduce.freeform_pilot import (
    Production,
    cue_seconds,
    require_coverage,
    subtitle_segments,
    validate_spec,
)


def spec():
    return {"project_id": "original-pilot", "fps": 30,
            "cues": [{"id": "opening", "spoken": "A question",
                      "subtitle_lines": ["A question"]}]}


def test_does_not_impose_shot_count_or_layout():
    data = spec()
    validate_spec(data)
    data["cues"] = [{**data["cues"][0], "id": f"cue_{i}",
                     "min_duration": i * 10} for i in range(23)]
    validate_spec(data)


@pytest.mark.parametrize("key,value", [
    ("project_id", "../escape"), ("fps", True), ("fps", 0), ("cues", [])])
def test_invalid_asset_boundary(key, value):
    data = spec()
    data[key] = value
    with pytest.raises(ValueError):
        validate_spec(data)


@pytest.mark.parametrize("key,value", [
    ("id", "../escape"), ("spoken", ""), ("subtitle_lines", "not a list"),
    ("min_duration", -1), ("tail", float("nan")), ("lead_in", True)])
def test_invalid_cue(key, value):
    data = spec()
    data["cues"][0][key] = value
    with pytest.raises(ValueError):
        validate_spec(data)


def test_duplicate_asset_names_rejected():
    data = spec()
    data["cues"] *= 2
    with pytest.raises(ValueError, match="Duplicate"):
        validate_spec(data)


def test_audio_sets_frame_aligned_length():
    assert cue_seconds({}, 6.017, 30) == pytest.approx(7)
    assert cue_seconds({"min_duration": 12}, 2, 30) == 12
    assert cue_seconds({"lead_in": 1, "tail": 2}, 4, 30) == 7


@pytest.mark.parametrize("seconds,fps", [(0, 30), (-1, 30), (float("inf"), 30),
                                         (1, 0), (1, True)])
def test_invalid_audio_duration(seconds, fps):
    with pytest.raises(ValueError):
        cue_seconds({}, seconds, fps)


def test_review_must_cover_every_cue_and_declare_limits():
    evidence = {"cue_ids": ["one", "two"], "frames": [
        {"cue": "one", "path": "one.png"}, {"cue": "two", "path": "two.png"}]}
    review = {"inspected_frames": ["one.png", "two.png"],
              "approval_scope": "supervised_preview", "limitations": []}
    require_coverage(review, evidence)
    for field, value in [("inspected_frames", ["one.png"]),
                         ("approval_scope", "automated_classroom_release"),
                         ("limitations", None)]:
        invalid = deepcopy(review)
        invalid[field] = value
        with pytest.raises(ValueError):
            require_coverage(invalid, evidence)


def test_local_source_does_not_escape_repository():
    with pytest.raises(ValueError, match="inside the repository"):
        Production.local_path("../outside.py")


def test_subtitles_do_not_show_result_before_its_spoken_sentence():
    cue = {"start": 17, "duration": 8, "speech_start": 17.3,
           "subtitle_lines": ["Launch. Caught!"],
           "spoken_spans": [{"start": 17.5, "end": 19.3, "text": "Launch."},
                            {"start": 19.25, "end": 20.4, "text": "Caught!"}]}
    assert subtitle_segments(cue) == [
        {"start": 17.5, "end": 19.25, "text": "Launch."},
        {"start": 19.25, "end": 25, "text": "Caught!"}]


def test_subtitles_support_provider_without_sentence_metadata():
    cue = {"start": 0, "duration": 8, "speech_start": .3,
           "subtitle_lines": ["One", "Two"]}
    assert subtitle_segments(cue) == [{"start": .3, "end": 8, "text": "One\nTwo"}]


def test_subtitles_reject_out_of_order_sentences():
    cue = {"start": 0, "duration": 8, "spoken_spans": [
        {"start": 3, "text": "One"}, {"start": 1, "text": "Two"}]}
    with pytest.raises(ValueError, match="ordered"):
        subtitle_segments(cue)


def test_optional_delivery_names_must_be_plain_files():
    data = spec()
    data["video_name"] = "lesson.mp4"
    data["subtitle_name"] = "lesson.srt"
    validate_spec(data)
    for value in ("../lesson.mp4", "assets/lesson.mp4", ""):
        invalid = spec()
        invalid["video_name"] = value
        with pytest.raises(ValueError, match="plain file name"):
            validate_spec(invalid)
