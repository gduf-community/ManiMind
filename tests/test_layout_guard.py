import math

import pytest

from manimind.experiments.layout_guard import check_boxes, validate_report


CONTRACT = {"bounds": [-6.3, 6.3, -2.5, 2.5], "required_labels": ["a", "b"], "gap": 0.04}
BOXES = {"a": [-2, -1, 0, 1], "b": [0, 1, 0, 1]}


def test_spaced_labels_pass_and_collision_is_named():
    assert check_boxes(BOXES, CONTRACT["bounds"]) == []
    assert check_boxes({**BOXES, "b": [-1.02, 0, 0, 1]}, CONTRACT["bounds"]) == ["label_collision:a:b"]


def test_invalid_and_outside_boxes_fail():
    assert check_boxes({"a": [-7, -6, 0, 1]}, CONTRACT["bounds"]) == ["out_of_bounds:a"]
    assert check_boxes({"a": [0, math.nan, 0, 1]}, CONTRACT["bounds"]) == ["invalid_box:a"]
    assert check_boxes({"a": [0, 0, 0, 1]}, CONTRACT["bounds"]) == ["invalid_box:a"]


def test_report_requires_each_cue_and_real_measurements():
    report = {"contract": CONTRACT, "checkpoints": [{"cue": i, "fraction": 1, "boxes": BOXES} for i in range(3)]}
    validate_report(report, CONTRACT, 3)
    with pytest.raises(ValueError, match="Incomplete"):
        validate_report(report, CONTRACT, 4)
    with pytest.raises(ValueError, match="contract"):
        validate_report(report, {**CONTRACT, "gap": 1}, 3)
    report["checkpoints"][0]["boxes"] = {"a": BOXES["a"]}
    with pytest.raises(ValueError, match="Missing"):
        validate_report(report, CONTRACT, 3)
    report["checkpoints"][0]["boxes"] = {"a": BOXES["a"], "b": BOXES["a"]}
    report["checkpoints"][0]["issues"] = []
    with pytest.raises(ValueError, match="blocked"):
        validate_report(report, CONTRACT, 3)
