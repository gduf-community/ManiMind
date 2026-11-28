import pytest

from manimind.canvas.timing import at, caption_rows, check_schedule, load_units

ALIGN = {"units": {
    "E1": {"text": "固定P，取Q。现在h等于一。", "chars": [["固", 0.1], ["定", 0.2], ["P", 0.3], ["取", 0.8], ["Q", 0.9],
                                              ["现", 1.5], ["在", 1.6], ["h", 1.8], ["等", 2.0], ["于", 2.1], ["一", 2.3]]},
    "E2": {"text": "这是拉姆达。", "chars": [["这", 0.2], ["是", 0.3], ["拉", 0.5], ["姆", 0.6], ["达", 0.7]]},
}}


def units():
    u = load_units(ALIGN, {"E1": 10.0, "E2": 14.0})
    return u["E1"], u["E2"]


def test_cue_is_the_film_time_of_the_spoken_word():
    e1, e2 = units()
    assert at(e1, "取Q") == 10.8
    assert at(e1, "h") == 11.8
    assert at(e2, "拉姆达") == 14.5
    with pytest.raises(KeyError):
        at(e1, "不存在")


def test_captions_start_on_first_spoken_character_and_merge_short_clauses():
    rows = caption_rows(units(), max_chars=8, replace={"拉姆达": " λ "})
    assert caption_rows(units()[:1])[0][2] == "固定P  取Q  现在h等于一"   # fits 15: one row
    assert rows[0] == [10.1, 11.45, "固定P  取Q"]
    assert rows[1][0] == 11.5 and rows[1][2] == "现在h等于一"
    assert rows[2][2] == "这是 λ"
    assert all(r[0] < r[1] for r in rows)


def test_alignment_must_match_text_and_move_forward():
    bad = {"units": {"E1": {"text": "固定", "chars": [["固", 0.1], ["错", 0.2]]}}}
    with pytest.raises(ValueError):
        load_units(bad, {"E1": 0.0})
    back = {"units": {"E1": {"text": "固定", "chars": [["固", 0.5], ["定", 0.2]]}}}
    with pytest.raises(ValueError):
        load_units(back, {"E1": 0.0})


def test_schedule_flags_overlaps_and_shot_overruns():
    e1, e2 = units()
    assert check_schedule([e1, e2], {"E1": 3.0, "E2": 1.0}, {"E1": 13.9, "E2": 16.0}) == []
    problems = check_schedule([e1, e2], {"E1": 3.9, "E2": 3.0}, {"E2": 16.0})
    assert any("too close" in p for p in problems) and any("after its shot" in p for p in problems)
