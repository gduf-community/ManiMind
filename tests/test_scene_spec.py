from copy import deepcopy
import json
import math
from pathlib import Path
import random

import pytest

from manimind.scene_spec.schema import validate_spec, parse_spec, SpecError, values, polynomial_tex
from manimind.scene_spec.geometry import clip_line, on_segment, axis_plan, audit_frame, map_point


@pytest.fixture
def spec():
    return {"schema_version": "1.0", "title": "观察平均速度", "learning_goal": "理解割线趋近切线",
            "model": {"kind": "polynomial", "coefficients": [0, 0, 4], "focus": 2, "domain": [0, 3.3]},
            "initial_h": 1, "primitives": ["graph", "moving_point", "increment_triangle", "secant", "tangent", "ratio"],
            "readouts": [{"bind": "delta_t", "decimals": 4}, {"bind": "delta_s", "decimals": 4}, {"bind": "average_slope", "decimals": 2}],
            "stages": [{"title": "缩短间隔", "h_to": h, "focus": "convergence" if i == 2 else "ratio", "pace": "early"} for i, h in enumerate([0.5, 0.1, 0.02])]}


def test_spec_round_trip_and_frozen_facts(spec):
    task = {"model": spec["model"], "h_sequence": [1, 0.5, 0.1, 0.02]}
    assert parse_spec(json.dumps(spec), task) == spec
    assert parse_spec("```json\n" + json.dumps(spec) + "\n```") == spec
    with pytest.raises(SpecError, match="frozen"):
        validate_spec(spec, {**task, "h_sequence": [1, 0.4, 0.1, 0.02]})


@pytest.mark.parametrize("path,value", [
    (("code",), "import os"), (("schema_version",), "2.0"), (("title",), r"\input{/etc/passwd}"),
    (("model", "coefficients"), "4*t**2"), (("initial_h",), True), (("initial_h",), math.nan),
    (("initial_h",), 0), (("initial_h",), 1.4), (("model", "coefficients"), [0, 0]),
    (("model", "coefficients"), [0, 0, -4]), (("stages", 0, "h_to"), 1.1),
    (("stages", 1, "h_to"), 0), (("stages", 2, "focus"), "ratio"),
    (("stages", 0, "pace"), "balanced"), (("readouts", 0, "bind"), "eval(h)"),
    (("readouts", 1, "decimals"), 2), (("primitives",), ["graph", "python"]),
])
def test_unsafe_or_inconsistent_specs_rejected(spec, path, value):
    target = spec
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(SpecError):
        validate_spec(spec)


def test_duplicate_and_nonfinite_json_rejected():
    for text in ['{"x":1,"x":2}', '{"x":NaN}', '[]', '```python\npass\n```']:
        with pytest.raises(SpecError):
            parse_spec(text)


def test_truth_tables_and_formula_generation(spec):
    for h, ds, slope in [(1, 20, 20), (.5, 9, 18), (.1, 1.64, 16.4), (.02, .3216, 16.08)]:
        result = values(spec["model"], h)
        assert result["delta_s"] == pytest.approx(ds)
        assert result["average_slope"] == pytest.approx(slope)
        assert result["tangent_slope"] == 16
    assert polynomial_tex([12, 8, -1]) == "s(t)=-t^{2}+8t+12"
    assert polynomial_tex([0, 0, 0, 1]) == "s(t)=t^{3}"


def test_clip_retains_both_points_across_500_random_lines():
    rng = random.Random(17)
    bounds = [-5.4, -.4, -1.8, 1.5]
    for _ in range(500):
        p = [rng.uniform(bounds[0], bounds[1]), rng.uniform(bounds[2], bounds[3])]
        q = [rng.uniform(bounds[0], bounds[1]), rng.uniform(bounds[2], bounds[3])]
        ends = clip_line(p, [q[i] - p[i] for i in range(2)], bounds)
        assert on_segment(p, ends) and on_segment(q, ends)
        for x, y in ends:
            assert bounds[0] - 1e-8 <= x <= bounds[1] + 1e-8
            assert bounds[2] - 1e-8 <= y <= bounds[3] + 1e-8
    assert clip_line([0, 0], [0, 1], [-1, 1, -2, 2]) == [[0, -2], [0, 2]]
    with pytest.raises(ValueError):
        clip_line([0, 0], [0, 0], bounds)


def test_frame_audit_detects_old_failures_and_rounded_values(spec):
    model = spec["model"]
    mapping = {"origin": [-5.4, -1.8], "scale": [5 / 3.3, 3.3 / 50], "plot": [-5.4, -.4, -1.8, 1.5]}
    for h in [1, .5, .1, .0235921, .02]:
        v = values(model, h)
        p, q, r = [map_point(v[key], mapping) for key in ["p", "q", "r"]]
        record = {"h": h, "boxes": {"test": [1, 2, 0, 1]}, "p": p, "q": q, "r": r,
                  "readouts": {key: v[key] for key in ["delta_t", "delta_s", "average_slope"]},
                  "increments": {"delta_t": [p, r], "delta_s": [r, q]},
                  "secant": clip_line(p, [q[i] - p[i] for i in range(2)], mapping["plot"]),
                  "tangent": clip_line(p, [mapping["scale"][0], 16 * mapping["scale"][1]], mapping["plot"])}
        assert audit_frame(record, model, mapping, ["test"]) == []
        broken = deepcopy(record)
        broken["readouts"]["average_slope"] = 123
        assert "readout_mismatch:average_slope" in audit_frame(broken, model, mapping, ["test"])
        broken = deepcopy(record)
        broken["secant"] = [p, [p[0] + .0001, p[1] + .0001]]
        assert "secant_does_not_cover_point" in audit_frame(broken, model, mapping, ["test"])


def test_all_suite_tasks_are_supported(spec):
    tasks = json.loads((Path(__file__).parents[1] / "configs/scene-spec-suite.json").read_text())["tasks"]
    for task in tasks.values():
        spec["model"] = task["model"]
        validate_spec(spec, task)
        plan = axis_plan(task["model"])
        assert plan["y_max"] > 0
