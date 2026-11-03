import json
import sys

import pytest


@pytest.fixture
def scene(tmp_path):
    original = sys.argv
    try:
        sys.argv = [sys.argv[0]]
        from manimind.experiments.understanding_support import UnderstandingScene
    finally:
        sys.argv = original
    value = UnderstandingScene.__new__(UnderstandingScene)
    value._open_focus, value._closed_focus = {}, []
    value.out = tmp_path
    value.clock = 0
    value.get_time = lambda: value.clock
    return value


def test_focus_is_actual_runtime_time_not_declared_duration(scene, monkeypatch):
    from manimind.experiments.visual_first_support import VisualLessonScene
    monkeypatch.setattr(VisualLessonScene, "tear_down", lambda _: None)
    scene.clock = 2
    scene.focus_begin("comparison")
    scene.clock = 9
    scene.focus_end("comparison")
    scene.clock = 12
    scene.tear_down()
    value = json.loads((scene.out / "focus-events.json").read_text())
    assert value["windows"] == [{"id": "comparison", "start": 2, "end": 9}]
    assert value["duration"] == 12


def test_open_or_zero_length_focus_cannot_be_published(scene):
    scene.focus_begin("result")
    with pytest.raises(ValueError, match="Close every"):
        scene.tear_down()
    with pytest.raises(ValueError, match="nonzero"):
        scene.focus_end("result")


def test_duplicate_or_unopened_focus_is_rejected(scene):
    scene.focus_begin("result")
    with pytest.raises(ValueError, match="unique"):
        scene.focus_begin("result")
    with pytest.raises(ValueError, match="not active"):
        scene.focus_end("other")
