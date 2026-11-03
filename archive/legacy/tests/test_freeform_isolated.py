import json
from pathlib import Path

import pytest

from manimind.experiments.freeform_isolated import (
    CONTRACT, SYSTEM, Experiment, check_source, decode_object, source_text,
)


def test_fenced_output_only_mechanically_unwrapped():
    assert source_text("```python\nx = 1\n```") == "x = 1\n"
    assert decode_object('```json\n{"title":"test"}\n```') == {"title": "test"}
    with pytest.raises(json.JSONDecodeError):
        decode_object('Explanation\n{"title":"test"}')


@pytest.mark.parametrize("source", [
    "import os", "from pathlib import Path", "open('x')",
    "eval('1')", "import requests", "x.__class__",
    "def setup(self): pass", "from manimind.postproduce import pilot",
])
def test_candidate_cannot_import_reference_or_io(source):
    with pytest.raises(ValueError):
        check_source(source)


def test_native_scene_allowed():
    check_source("""
from manimlib import *
import numpy as np
from manimind.experiments.freeform_support import LessonScene
class GeneratedLesson(LessonScene):
    def construct(self):
        dot = Dot()
        self.add(dot)
        self.until(self.timeline["duration"])
""")


def test_prompt_has_no_reference_narrative():
    for forbidden in ("接收区", "探测球", "projectile_story.py", "projectile-story-20261020"):
        assert forbidden not in SYSTEM + CONTRACT


def test_freeze_inputs_include_media_and_support():
    experiment = Experiment()
    names = {p.name for p in experiment.frozen_paths()}
    assert {"freeform_support.py", "freeform_isolated.py", "freeform_pilot.py",
            "typography.py", "client.py", "pilot.py", "deepseek-freeform.json"} <= names


def test_task_does_not_copy_reference_example_parameters():
    config = json.loads((Path(__file__).parents[1] / "configs/deepseek-freeform.json").read_text())
    assert "example" not in config["brief"]["facts"]
    assert config["max_repairs"] == 2
    assert config["max_requests"] == 5


def test_real_multiline_subtitle_setup(tmp_path, monkeypatch):
    from manimind.experiments.freeform_support import LessonScene
    monkeypatch.setenv("MANIMIND_FREEFORM_OUTPUT", str(tmp_path))
    (tmp_path / "timeline.json").write_text(json.dumps({
        "duration": 4, "cues": [{"start": 0, "duration": 4,
                               "spoken_spans": [{"start": .3, "end": 3.5,
                                                 "text": "An intentionally long subtitle. " * 12}]}]}))
    scene = LessonScene.__new__(LessonScene)
    scene.add = lambda *args: None
    scene.setup()
    assert len(scene._subtitles[0][2].submobjects) > 1
