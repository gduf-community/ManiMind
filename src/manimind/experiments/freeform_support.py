"""Content-free render support: typography, measured time and subtitles.

The render process owns this state. Assets and optional sound events live only
in its explicit output directory and are invalidated by a new render.
"""

import json
import os
from pathlib import Path

import numpy as np
from manimlib import Group, Scene, Tex

from manimind.components.typography import text_image, RasterNumber


class LessonScene(Scene):
    def setup(self):
        super().setup()
        self.out = Path(os.environ["MANIMIND_FREEFORM_OUTPUT"]).resolve()
        self.timeline = json.loads((self.out / "timeline.json").read_text())
        self.cues = self.timeline["cues"]
        self.sound_events = []
        self.always_update_mobjects = True
        self._subtitle_index = -1
        self._subtitles = []
        for cue in self.cues:
            spans = cue["spoken_spans"]
            for i, span in enumerate(spans):
                end = spans[i + 1]["start"] if i + 1 < len(spans) else cue["start"] + cue["duration"]
                text = span["text"]
                # Wrap by rendered width, not by an assumed number of CJK glyphs.
                lines, current = [], ""
                for char in text:
                    if current and self.cn(current + char, 27).get_width() > 12.3:
                        lines.append(current)
                        current = char
                    else:
                        current += char
                if current:
                    lines.append(current)
                group = Group(*[self.cn(line, 27) for line in lines])
                group.arrange(np.array([0, -1, 0]), buff=.08).move_to([0, -3.48, 0])
                group.fix_in_frame()
                self._subtitles.append((span["start"], end, group))
        self._subtitle_driver = Group()
        self._subtitle_driver.add_updater(lambda _: self._update_subtitle())
        self.add(self._subtitle_driver)

    def cn(self, text, size=32, color="#EEF1F4"):
        return text_image(str(text), self.out, size=size, color=color)

    def number(self, value, size=32, color="#EEF1F4", decimals=2):
        return RasterNumber(value, self.out, size=size, color=color, decimals=decimals)

    def formula(self, latex, size=38, color="#EEF1F4"):
        return Tex(latex, font_size=size, template="basic_ctex").set_color(color)

    def _update_subtitle(self):
        time = self.get_time()
        index = next((i for i, (start, end, _) in enumerate(self._subtitles)
                      if start <= time < end), -1)
        if index != self._subtitle_index:
            if self._subtitle_index >= 0:
                self.remove(self._subtitles[self._subtitle_index][2])
            if index >= 0:
                self.add(self._subtitles[index][2])
            self._subtitle_index = index

    def get_time_progression(self, run_time, **kwargs):
        if self.skip_animations and not kwargs.get("override_skip_animations", False):
            return [run_time]
        frames = int(round(run_time * self.camera.fps))
        return np.arange(1, frames + 1, dtype=float) / self.camera.fps

    def until(self, absolute_seconds, *animations, **kwargs):
        """Animate/wait to an absolute measured boundary; never stretch audio."""
        frames = round(absolute_seconds * self.camera.fps) - round(self.get_time() * self.camera.fps)
        if frames < 0 or (frames == 0 and animations):
            raise ValueError(f"Past timing target {absolute_seconds}; scene is at {self.get_time()}")
        if frames:
            if animations:
                self.play(*animations, run_time=frames / self.camera.fps, **kwargs)
            else:
                self.wait(frames / self.camera.fps, ignore_presenter_mode=True)

    def sound(self, kind, time=None):
        self.sound_events.append({"kind": kind, "time": self.get_time() if time is None else time})

    def tear_down(self):
        if abs(self.get_time() - self.timeline["duration"]) > .1:
            raise ValueError("Scene and measured narration durations disagree")
        (self.out / "sound-events.json").write_text(json.dumps({"events": self.sound_events}))
        super().tear_down()
