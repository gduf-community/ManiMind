"""Word-estimated caption groups preserve source text and actual timing inputs."""

from copy import deepcopy

import pytest

from manimind.postproduce import focus_captions, unit_film, word_captions


def data():
    words = [
        {"word": " 甲乙", "start": .1, "end": .2},
        {"word": "丙丁", "start": .2, "end": .4},
        {"word": "戊己", "start": .4, "end": 4.0},
        {"word": "庚辛壬", "start": 4.0, "end": 4.3},
        {"word": "癸。", "start": 4.3, "end": 4.6},
    ]
    return {"duration": 20, "units": [{"id": "U01", "start": 10, "phrases": [{
        "id": "r1", "text": "甲乙丙丁戊己庚辛壬癸。", "start": .1, "end": 4.6,
        "visual_start": 10.1, "visual_end": 14.6, "words": words}]}]}


def test_whole_words_and_nonuniform_timing_replace_character_ratios():
    source = data()
    before = deepcopy(source)
    result = word_captions.make_captions(source, {"max_width": 8})
    first, second = result["events"]
    assert first["text"] == "甲乙丙丁戊己"
    assert (first["start_cs"], first["end_cs"]) == (1010, 1400)
    assert (second["start_cs"], second["end_cs"]) == (1400, 1460)
    assert first["last_word_index"] == 2 and second["first_word_index"] == 3
    assert "".join(event["text"] for event in result["events"]) == source["units"][0]["phrases"][0]["text"]
    assert all(event["timing"] == "model_estimated_word_group" for event in result["events"])
    assert all(focus_captions.text_width(event["text"]) <= 16 for event in result["events"])
    assert source == before
    assert unit_film._caption_data(source, {"max_width": 8}, "word_estimates") == result


def test_original_whitespace_is_preserved_without_copying_asr_leading_spaces():
    source = data()
    source["units"][0]["phrases"][0]["text"] = " 甲乙丙丁 戊己庚辛壬癸。 "
    result = word_captions.make_captions(source, {"max_width": 8})
    assert "".join(event["text"] for event in result["events"]) == " 甲乙丙丁 戊己庚辛壬癸。 "


def test_instantaneous_word_stays_an_explicit_uncertainty_inside_positive_group():
    source = data()
    source["units"][0]["phrases"][0]["words"][1]["end"] = .2
    result = word_captions.make_captions(source, {"max_width": 8})
    assert result["events"][0]["instantaneous_word_indices"] == [1]
    assert "uncertain" in result["timing_scope"]


@pytest.mark.parametrize("mutation", ("missing", "text", "overlap", "outside", "nan", "empty", "zero_group"))
def test_invalid_estimates_fail_without_inventing_caption_times(mutation):
    source = data()
    phrase = source["units"][0]["phrases"][0]
    if mutation == "missing":
        phrase.pop("words")
    elif mutation == "text":
        phrase["words"][0]["word"] = "错误"
    elif mutation == "overlap":
        phrase["words"][1]["start"] = .19
    elif mutation == "outside":
        phrase["words"][-1]["end"] = 5
    elif mutation == "nan":
        phrase["words"][0]["start"] = float("nan")
    elif mutation == "empty":
        phrase["words"][0]["word"] = " "
    else:
        for word in phrase["words"]:
            word["start"] = word["end"] = .1
    with pytest.raises(ValueError):
        word_captions.make_captions(source, {"max_width": 8})


def test_unknown_caption_mode_is_rejected():
    with pytest.raises(ValueError, match="timing mode"):
        unit_film._caption_data(data(), None, "invented")


def test_rounding_noise_does_not_move_captions_outside_phrase():
    source = data()
    source["units"][0]["phrases"][0]["visual_end"] = 14.599999999999998
    result = word_captions.make_captions(source, {"max_width": 8})
    assert result["events"][-1]["end_cs"] == 1459
