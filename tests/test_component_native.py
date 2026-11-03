import json
from copy import deepcopy
from pathlib import Path

import pytest

pytest.importorskip("manimlib")

from manimlib import Arrow, Dot, Line, Rectangle, VGroup
from manimind.components.catalog import COLORS
from manimind.components.renderer import ComponentScene, SIDEBAR, _row_layout, _visible_colors
from manimind.components import renderer


@pytest.mark.parametrize("factory", [lambda: Arrow([0, 0, 0], [1, 1, 0]), Dot,
                                    lambda: Line([0, 0, 0], [1, 1, 0])])
def test_visible_component_color_is_explicit_and_measured(factory):
    obj = factory().set_color(COLORS["cyan"])
    assert _visible_colors(obj) == [COLORS["cyan"]]
    obj.set_color(COLORS["coral"])
    assert _visible_colors(obj) != [COLORS["cyan"]]


def test_color_measurement_covers_child_objects():
    group = VGroup(Dot().set_color(COLORS["cyan"]), Dot().set_color(COLORS["yellow"]))
    assert _visible_colors(group) == sorted([COLORS["cyan"], COLORS["yellow"]])


def axes_scene(shot_index):
    scene = ComponentScene.__new__(ComponentScene)
    plan = json.loads((Path(__file__).parents[1] / "configs/component-foundation.json").read_text())
    scene.shot = plan["shots"][shot_index]
    scene.labels = {}
    scene.add = lambda *objects: None
    scene._text = lambda *args, **kwargs: Rectangle(width=.15, height=.2)
    scene._build_axes()
    return scene


@pytest.mark.parametrize("shot", [0, 1, 2])
def test_ticks_and_labels_share_native_values_in_protected_gutters(shot):
    scene = axes_scene(shot)
    ticks, issues = scene._tick_evidence()
    assert not issues
    if shot == 2:
        assert [t["value"] for t in ticks if t["axis"] == "x"] == [-2.5, -1.5, -.5, .5, 1.5, 2.5]


def test_shifted_tick_is_detected():
    scene = axes_scene(2)
    scene.axis_ticks[0]["mark"].shift([.2, 0, 0])
    assert any("tick_label_mismatch" in issue for issue in scene._tick_evidence()[1])


def test_label_moving_into_plot_is_detected():
    scene = axes_scene(2)
    scene.labels[scene.axis_ticks[1]["label"]].shift([0, .5, 0])
    assert any("tick_label_inside_plot" in issue for issue in scene._tick_evidence()[1])


@pytest.mark.parametrize("kinds", [
    ["formula", "curve", "point", "readout"],
    ["vector", "vector", "vector", "readout", "readout"],
    ["curve", "segment", "point", "point", "formula", "readout"],
    ["formula"] * 6,
    ["readout"] * 6,
])
def test_visual_groups_keep_stable_non_overlapping_rows(kinds):
    components = [{"id": str(i), "kind": kind} for i, kind in enumerate(kinds)]
    rows = _row_layout(components)
    assert {c["id"] for c, _ in rows} == {c["id"] for c in components}
    for index, (component, bounds) in enumerate(rows):
        assert SIDEBAR[2] - 1e-7 <= bounds[2] < bounds[3] <= SIDEBAR[3] + 1e-7
        if index:
            assert bounds[3] <= rows[index - 1][1][2] + 1e-7
    priorities = [{"formula": 0, "readout": 2}.get(c["kind"], 1) for c, _ in rows]
    assert priorities == sorted(priorities)


def test_compact_formula_labels_stay_in_assigned_rows(monkeypatch):
    plan = json.loads((Path(__file__).parents[1] / "configs/component-foundation.json").read_text())
    shot = deepcopy(plan["shots"][0])
    curve, formula = shot["components"][:2]
    shot["components"] = [curve, *[{**formula, "id": f"formula-{i}"} for i in range(5)]]
    scene = ComponentScene.__new__(ComponentScene)
    scene.add = lambda *objects: None
    scene.clear = lambda: None
    scene._text = lambda *args, **kwargs: Rectangle(width=.6, height=.18)
    scene.shot_records, scene.frames_checked = [], 0
    monkeypatch.setattr(renderer, "Tex", lambda *args, **kwargs: Rectangle(width=1, height=.3))
    scene._build_shot(shot)
    for cid, members in scene.row_members.items():
        lower, upper = scene.row_bounds[cid][2:]
        assert all(obj.get_bottom()[1] >= lower - 1e-7 and obj.get_top()[1] <= upper + 1e-7
                   for obj in members)
