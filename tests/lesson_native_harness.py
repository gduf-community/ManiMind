"""Native ManimGL timing tests with vector placeholders, never pixel approval.

This is test input/control only. No production renderer or state is replaced.
The test owns the in-memory scene and files; callers inspect after construct.
Every run expires on source, plan or native API changes.
"""

from contextlib import contextmanager
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from manimind.experiments.visual_first_data import validate_events, visual_timeline


class MemoryPath:
    def __init__(self, files=None, name=""):
        self.files = {} if files is None else files
        self.name = name

    def __truediv__(self, name):
        return MemoryPath(self.files, str(name))

    def open(self, mode, **kwargs):
        if mode == "x" and self.name in self.files:
            raise FileExistsError(self.name)
        path = self

        class Stream(io.StringIO):
            def close(self):
                path.files[path.name] = self.getvalue()
                super().close()

        return Stream()

    def write_text(self, text, **kwargs):
        self.files[self.name] = text


def load_lesson(path):
    original = sys.argv
    try:
        sys.argv = original[:1]
        path = Path(path)
        spec = importlib.util.spec_from_file_location("native_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.argv = original


@contextmanager
def native_run(module, scene_class, plan, initialize=None):
    original = sys.argv
    try:
        sys.argv = original[:1]
        import manimlib as gl
        from manimlib.animation.animation import prepare_animation
        import manimind.components.formula_motion as motion
        from manimind.experiments.visual_first_support import VisualLessonScene
    finally:
        sys.argv = original
    patcher = pytest.MonkeyPatch()

    class Formula(gl.VGroup):
        def __init__(self, latex, tokens=None, font_size=38, **kwargs):
            self.latex, self.selectors = latex, tokens or {}
            self.semantic_ids = tuple(self.selectors)
            unit = .065 * font_size / 38
            super().__init__(*(gl.Rectangle(width=.8 * unit, height=.32 * font_size / 38,
                fill_opacity=1, stroke_width=0).move_to([i * unit, 0, 0]) for i in range(len(latex))))
            self.center()

        def get_tex(self):
            return self.latex

        def get_parts_by_tex(self, literal):
            return gl.VGroup(*(gl.VGroup(*self.submobjects[m.start():m.end()])
                for m in re.finditer(re.escape(literal), self.latex)))

        def tag(self, identity):
            selector = self.selectors[identity]
            literal, index = (selector, 0) if isinstance(selector, str) else selector
            return self.get_parts_by_tex(literal)[index]

        def _resolve_tags(self):
            return {identity: self.tag(identity) for identity in self.semantic_ids}

    class Number(gl.VGroup):
        def __init__(self, value=0, **kwargs):
            super().__init__(gl.Rectangle(width=.65, height=.3, fill_opacity=1))
            self.value = value

        def set_value(self, value):
            self.value = value
            return self

        def get_value(self):
            return self.value

    class Smoke(scene_class):
        def __init__(self):
            self.time, self.frame, self.mobjects = 0., 0, []
            self.camera = SimpleNamespace(fps=30)
            self.skip_animations, self.always_update_mobjects = False, True
            self.out = MemoryPath()
            self.timeline = visual_timeline(plan)
            self.cues = self.timeline["cues"]
            self.visual_events, self.sound_events = [], []
            self._open_focus, self._closed_focus = {}, []
            self._subtitle_driver = gl.Group()
            self.labels, self.plays = [], []

        def add(self, *objects):
            for obj in objects:
                if not any(old is obj for old in self.mobjects):
                    self.mobjects.append(obj)
            return self

        def remove(self, *objects):
            self.mobjects = [obj for obj in self.mobjects if all(obj is not old for old in objects)]
            return self

        def cn(self, text, size=32, **kwargs):
            self.labels.append(str(text))
            return gl.Rectangle(width=max(.01, min(11., len(str(text)) * .11)),
                                height=.3, fill_opacity=1, stroke_width=0)

        def formula(self, latex, size=38, **kwargs):
            self.labels.append(latex)
            return Formula(latex, font_size=size)

        def number(self, value, **kwargs):
            return Number(value, **kwargs)

    def advance(scene, dt):
        scene.frame += 1
        scene.time = scene.frame / 30
        scene.update_mobjects(dt)

    def play(scene, *proto, run_time=None, rate_func=None, lag_ratio=None):
        start = scene.time
        animations = list(map(prepare_animation, proto))
        for animation in animations:
            animation.update_rate_info(run_time, rate_func, lag_ratio)
            scene.add(animation.mobject)
            animation.begin()
        duration = max(animation.run_time for animation in animations)
        previous = 0.
        for t in scene.get_time_progression(duration):
            for animation in animations:
                animation.update_mobjects(t - previous)
                animation.interpolate(t / animation.run_time)
            advance(scene, t - previous)
            previous = t
        for animation in animations:
            animation.finish()
            animation.clean_up_from_scene(scene)
        scene.update_mobjects(0)
        scene.plays.append({"start": start, "end": scene.time})

    def wait(scene, duration, **kwargs):
        for _ in scene.get_time_progression(duration):
            advance(scene, 1 / 30)

    def teardown(scene):
        value = {"duration": scene.time, "events": scene.visual_events}
        validate_events(scene.timeline, value)
        (scene.out / "visual-events.json").write_text(json.dumps(value))

    patcher.setattr(module, "SemanticFormula", Formula, raising=False)
    patcher.setattr(motion, "SemanticFormula", Formula)
    patcher.setattr(gl.Scene, "play", play)
    patcher.setattr(gl.Scene, "wait", wait)
    patcher.setattr(VisualLessonScene, "tear_down", teardown)
    try:
        scene = Smoke()
        if initialize is not None:
            initialize(scene)
        scene.construct()
        scene.tear_down()
        yield scene
    finally:
        patcher.undo()
