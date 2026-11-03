"""Shared typography and cue clock, not a subject-specific scene template.

Render-local state is owned by BenchmarkScene and discarded after rendering.
MANIMIND_BENCHMARK_DIR is explicitly passed by the experiment orchestrator.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image as PILImage, ImageDraw, ImageFont
from manimlib import Scene, Text, Tex, ImageMobject, Group, DOWN, LEFT

INK = "#F0F3F6"
CYAN = "#55C8E8"
YELLOW = "#FFD166"
CORAL = "#FF826B"
GREEN = "#8ED9A8"
MUTED = "#A7AFBA"
BACKGROUND = "#101216"
FONT = "Hiragino Sans GB"


def output_dir():
    return Path(os.environ["MANIMIND_BENCHMARK_DIR"])


def cn(text, size=28, color=INK):
    """Original pilot's FreeType workaround, shared without its scene content."""
    layout = Text(text, font=FONT, font_size=size)
    font_path = os.environ.get("MANIMIND_CJK_FONT", "/System/Library/Fonts/Hiragino Sans GB.ttc")
    face = ImageFont.truetype(font_path, round(size * 4))
    left, top, right, bottom = face.getbbox(text)
    bitmap = PILImage.new("RGBA", (max(1, right-left+4), max(1, bottom-top+4)))
    ImageDraw.Draw(bitmap).text((2-left, 2-top), text, font=face, fill=color)
    key = hashlib.sha256(json.dumps([text, size, color, font_path]).encode()).hexdigest()[:24]
    directory = output_dir() / "text-assets"
    directory.mkdir(exist_ok=True)
    path = directory / f"{key}.png"
    if not path.exists():
        bitmap.save(path)
    return ImageMobject(str(path), height=layout.get_height()).set_width(layout.get_width(), stretch=True)


def formula(text, size=38, color=INK):
    return Tex(text, font_size=size, template="basic_ctex").set_color(color)


class BenchmarkScene(Scene):
    """Subclass as GeneratedLesson; construct() owns only the lesson visuals."""

    def setup(self):
        super().setup()
        self.timeline = json.loads((output_dir() / "timeline.json").read_text())
        self.cue_index = -1
        self.subtitle = Group()
        self.header = Group()

    def get_time_progression(self, run_time, **kwargs):
        if self.skip_animations and not kwargs.get("override_skip_animations", False):
            return [run_time]
        frames = int(round(run_time * self.camera.fps))
        return np.arange(1, frames + 1, dtype=float) / self.camera.fps

    @contextmanager
    def cue(self, index, title):
        if index != self.cue_index + 1:
            raise ValueError("Cues must be visited once in timeline order")
        self.cue_index = index
        cue = self.timeline["cues"][index]
        self.cue_start, self.cue_duration, self.last_fraction = cue["start"], cue["duration"], 0.0
        self.remove(self.header, self.subtitle)
        self.header = cn(title, 32)
        if self.header.get_width() > 12:
            self.header.set_width(12)
        self.header.move_to([-6.1, 3.25, 0], aligned_edge=LEFT)
        self.subtitle = Group(*[cn(line, 25) for line in cue["subtitle_lines"]]).arrange(DOWN, buff=0.07)
        factor = min(1, 12.2 / max(self.subtitle.get_width(), 0.01), 0.6 / max(self.subtitle.get_height(), 0.01))
        self.subtitle.scale(factor).move_to([0, -3.35, 0])
        self.add(self.header, self.subtitle)
        yield
        self.beat(1)

    def beat(self, fraction, *animations, rate_func=None):
        if not self.last_fraction <= fraction <= 1:
            raise ValueError("Beat fractions must be monotonic in [0,1]")
        self.last_fraction = fraction
        frames = round((self.cue_start + fraction * self.cue_duration) * self.camera.fps) - round(self.get_time() * self.camera.fps)
        if frames < 0 or (frames == 0 and animations):
            raise ValueError("Animation exceeded its cue budget")
        if not frames:
            return
        duration = frames / self.camera.fps
        if animations:
            kwargs = {"rate_func": rate_func} if rate_func else {}
            self.play(*animations, run_time=duration, **kwargs)
        else:
            self.wait(duration, ignore_presenter_mode=True)

    def tear_down(self):
        if self.cue_index != len(self.timeline["cues"]) - 1:
            raise ValueError("Generated lesson skipped required cues")
        super().tear_down()
