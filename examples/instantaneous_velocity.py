"""Silent ManimGL 1.7.2 review pilot; the lead agent owns rendering and audio.

Run from the repository with the lead agent's normal ManimGL command, selecting
InstantaneousVelocity. Production is 1920 x 1080, 16:9, without an audio track;
the CLI can select lower-resolution drafts.

Read-only input: outputs/velocity-pilot/timeline.json. Only a missing file uses
the twelve 8-second fallback cues. Malformed or reordered timelines fail early.
Animation deadlines use cumulative durations, never the supplied `start` fields
or a whole-film speed adjustment. Boundaries are rounded to the nearest video
frame (at most half a frame of error, without cumulative rounding drift).

All state below is scene-local and discarded after the render: cue() owns timing
and subtitles; time/h/radius trackers own moving geometry and numeric readouts.
Updaters are cleared when their shot leaves the screen. No project/session state
is written, no third-party asset is copied, and no review gate is bypassed.
"""

from contextlib import contextmanager
import json
import math
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image as PILImage, ImageDraw, ImageFont
from manimlib import *


BACKGROUND = "#101216"
SURFACE = "#191D23"
INK = "#F0F3F6"
MUTED = "#A7AFBA"
GRID = "#343C47"
CYAN = "#55C8E8"
YELLOW = "#FFD166"
CORAL = "#FF826B"
GREEN = "#8ED9A8"
FONT = "Hiragino Sans GB"
_REPO_ROOT = next(
    (parent for parent in Path(__file__).resolve().parents
     if (parent / "AGENTS.md").is_file() and (parent / "src/manimind").is_dir()),
    None,
)
if _REPO_ROOT is None:
    raise FileNotFoundError("Cannot locate the ManiMind repository for velocity-pilot")
TIMELINE_PATH = _REPO_ROOT / "outputs/velocity-pilot/timeline.json"
CUE_IDS = (
    "hook", "model", "average", "graph", "half", "tenth", "approach",
    "zero", "algebra", "zoom", "result", "recap",
)
TITLES = (
    "某一瞬间，速度怎么算？", "先把运动说清楚", "先测一段，再谈一瞬",
    "把路上的测量，带到图上", "缩短时间间隔", "再靠近一点", "越来越近，但还没重合",
    "趋近于零，不是直接代零", "先化简，再取极限", "放大之后，曲线越来越像直线",
    "这一瞬间，汽车有多快？", "从一段时间，走向一个瞬间",
)
FALLBACK_TEXT = (
    "汽车正在加速。定格一帧，只能看见位置；某一瞬间的速度，该怎么算？",
    "选择理想运动 s(t)=4t²：时间用秒，位置用米。时间前进，汽车按这个规律移动。",
    "从第2秒到第3秒，位置从16米变到36米。用20米除以1秒，平均速度是20米每秒。",
    "横轴是时间，纵轴是位置。连接A和B的割线，斜率就是这段时间的平均速度。",
    "固定第2秒，把间隔缩短到0.5秒。B沿曲线靠近A，平均速度降到18米每秒。",
    "再缩短到0.1秒，平均速度变成16.4米每秒。我们正在逼近第2秒的速度。",
    "间隔只有0.02秒时，平均速度是16.08米每秒。割线也越来越接近这条切线。",
    "但不能直接令间隔等于零。零除以零没有定义，它不是一个速度。",
    "先在h不为零时展开、约去h，得到16+4h。再让h趋近于零，结果就趋近于16。",
    "真正放大A附近，两轴按相同尺度放大。曲线与切线越来越吻合，屏幕角度不是实际速度。",
    "所以第2秒的瞬时速度是16米每秒，也就是57.6千米每小时。图上的斜率，对应车的速度。",
    "瞬时速度，是平均速度在时间间隔趋近于零时的极限。第2秒的答案，就是16米每秒。",
)


def load_timeline(path=TIMELINE_PATH):
    """Consume the lead's timeline without modifying it or trusting its offsets."""
    if not path.exists():
        return [
            {"id": cue_id, "duration": 8.0, "text": text, "subtitle_lines": []}
            for cue_id, text in zip(CUE_IDS, FALLBACK_TEXT)
        ]
    data = json.loads(path.read_text(encoding="utf-8"))
    cues = data.get("cues")
    if not isinstance(cues, list) or [c.get("id") for c in cues] != list(CUE_IDS):
        raise ValueError(f"{path}: expected exactly these ordered cues: {CUE_IDS}")
    for cue in cues:
        duration = cue.get("duration")
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not math.isfinite(duration) or duration <= 0):
            raise ValueError(f"{path}: invalid duration for {cue['id']}")
        if not isinstance(cue.get("text"), str) or not cue["text"].strip():
            raise ValueError(f"{path}: missing subtitle text for {cue['id']}")
        lines = cue.get("subtitle_lines", [])
        if not isinstance(lines, list) or not all(isinstance(s, str) for s in lines):
            raise ValueError(f"{path}: subtitle_lines must be strings")
    total = data.get("duration")
    if total is not None and not math.isclose(
        float(total), math.fsum(c["duration"] for c in cues), abs_tol=0.05
    ):
        raise ValueError(f"{path}: total duration disagrees with cue durations")
    return cues


def caption_lines(cue):
    """Keep the complete cue text, using supplied wrapping when it preserves it."""
    text = cue["text"].strip()
    supplied = [line.strip() for line in cue.get("subtitle_lines", []) if line.strip()]
    compact = lambda value: "".join(value.split())
    if 1 <= len(supplied) <= 2 and compact("".join(supplied)) == compact(text):
        return supplied
    text = " ".join(text.split())
    if len(text) <= 37:
        return [text]
    middle = len(text) // 2
    candidates = [
        i + 1 for i, char in enumerate(text)
        if char in "，。；：！？,; " and abs(i + 1 - middle) <= len(text) * 0.18
    ]
    split = min(candidates, key=lambda i: abs(i - middle)) if candidates else middle
    return [text[:split].strip(), text[split:].strip()]


def cn(text, size=28, color=INK):
    # CJK contours hit triangulation defects in this macOS/ManimGL combination.
    # Use high-resolution FreeType glyphs as textures, retaining Pango's layout.
    layout = Text(text, font=FONT, font_size=size)
    face = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", round(size * 4))
    left, top, right, bottom = face.getbbox(text)
    bitmap = PILImage.new("RGBA", (right - left + 4, bottom - top + 4))
    ImageDraw.Draw(bitmap).text((2 - left, 2 - top), text, font=face, fill=color)
    asset_dir = _REPO_ROOT / "outputs/velocity-pilot/text-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([text, size, color, FONT]).encode()).hexdigest()[:24]
    path = asset_dir / f"{key}.png"
    bitmap.save(path)
    return ImageMobject(str(path), height=layout.get_height()).set_width(layout.get_width(), stretch=True)


def formula(text, size=40, color=INK):
    # The project's installed TinyTeX toolchain exposes XeLaTeX, not latex.
    return Tex(text, font_size=size, template="basic_ctex").set_color(color)


def number(value, places=2, size=38, color=INK):
    return DecimalNumber(
        value, num_decimal_places=places, font_size=size, color=color,
        group_with_commas=False, text_config={"font": FONT},
    )


def fitted(mob, width=12.0, height=None):
    scale = min(1.0, width / max(mob.get_width(), 1e-8))
    if height is not None:
        scale = min(scale, height / max(mob.get_height(), 1e-8))
    return mob.scale(scale)


def freeze(*mobjects):
    for mob in mobjects:
        mob.clear_updaters()


class SideCar(VGroup):
    """Original side-view asset. Its centre marks the measured road position."""

    def __init__(self):
        body = Polygon(
            [-0.77, 0.02, 0], [-0.77, 0.28, 0], [-0.57, 0.35, 0],
            [-0.34, 0.64, 0], [0.28, 0.64, 0], [0.54, 0.36, 0],
            [0.76, 0.29, 0], [0.79, 0.04, 0],
            fill_color=CYAN, fill_opacity=1, stroke_color=INK, stroke_width=1.5,
        )
        windows = VGroup(
            Polygon([-0.48, 0.37, 0], [-0.28, 0.56, 0], [-0.07, 0.56, 0],
                    [-0.07, 0.37, 0], fill_color=BACKGROUND, fill_opacity=1, stroke_width=0),
            Polygon([0.0, 0.37, 0], [0.0, 0.56, 0], [0.23, 0.56, 0],
                    [0.41, 0.37, 0], fill_color=BACKGROUND, fill_opacity=1, stroke_width=0),
        )
        wheels = VGroup()
        for x in (-0.46, 0.47):
            wheel = VGroup(
                Circle(radius=0.175, fill_color=BACKGROUND, fill_opacity=1,
                       stroke_color=INK, stroke_width=2),
                Circle(radius=0.065, fill_color=MUTED, fill_opacity=1, stroke_width=0),
                Line([-0.12, 0, 0], [0.12, 0, 0], stroke_color=MUTED, stroke_width=1.5),
            ).shift(RIGHT * x)
            wheels.add(wheel)
        lamp = Line([0.68, 0.24, 0], [0.77, 0.24, 0], color=YELLOW, stroke_width=5)
        seam = Line([-0.04, 0.30, 0], [-0.04, 0.06, 0], color=BACKGROUND, stroke_width=1)
        super().__init__(body, windows, seam, lamp, wheels)
        self.wheels = wheels
        self.last_x = None

    def place_on_road(self, x, road_y):
        if self.last_x is not None:
            angle = -(x - self.last_x) / 0.175
            for wheel in self.wheels:
                wheel.rotate(angle, about_point=wheel.get_center())
        self.move_to([x, road_y + self.get_height() / 2 + 0.018, 0])
        self.last_x = x
        return self


class InstantaneousVelocity(Scene):
    timeline_path = TIMELINE_PATH
    default_camera_config = {
        "fps": 30, "background_color": BACKGROUND,
        "frame_config": {"frame_shape": (128 / 9, 8)},
    }

    def __init__(self, *args, **kwargs):
        # CLI-injected defaults otherwise override the subclass camera config.
        camera = dict(kwargs.pop("camera_config", {}))
        camera.update(background_color=BACKGROUND)
        camera["frame_config"] = dict(camera.get("frame_config", {}), frame_shape=(128 / 9, 8))
        super().__init__(*args, camera_config=camera, **kwargs)

    def get_time_progression(self, run_time, **kwargs):
        # ManimGL's np.arange(0, duration, 1/fps) can emit an extra frame at a
        # floating-point boundary. All our durations are integer frame budgets.
        if self.skip_animations and not kwargs.get("override_skip_animations", False):
            return [run_time]
        frames = int(round(run_time * self.camera.fps))
        return np.arange(1, frames + 1, dtype=float) / self.camera.fps

    @contextmanager
    def cue(self, index):
        if index != self.cue_index + 1:
            raise ValueError("Cues must run once, in timeline order")
        self.cue_index = index
        self.cue_start = math.fsum(c["duration"] for c in self.timeline[:index])
        self.cue_duration = self.timeline[index]["duration"]
        self.last_fraction = 0.0
        self.remove(self.subtitle, self.header)
        lines = Group(*[cn(line, 25) for line in caption_lines(self.timeline[index])])
        lines.arrange(DOWN, buff=0.065)
        fitted(lines, 12.35, 0.50).move_to([0, -3.35, 0])
        self.subtitle = lines
        self.header = fitted(cn(self.timeline[index].get("heading", TITLES[index]), 33), 11.9, 0.46)
        self.header.move_to([-6.12, 3.12, 0], aligned_edge=LEFT)
        for i, segment in enumerate(self.progress):
            segment.set_color(CYAN if i <= index else GRID)
        self.add(self.header, self.subtitle)
        yield
        self.beat(1.0)

    def beat(self, fraction, *animations, rate_func=smooth):
        """Animate/hold until a fractional deadline of the current cue only."""
        if not self.last_fraction <= fraction <= 1:
            raise ValueError("Cue deadlines must be monotonic and at most 1")
        self.last_fraction = fraction
        target_frame = round((self.cue_start + fraction * self.cue_duration) * self.camera.fps)
        current_frame = round(self.get_time() * self.camera.fps)
        frames = target_frame - current_frame
        if frames < 0:
            raise RuntimeError(f"Cue {CUE_IDS[self.cue_index]} overran its deadline")
        if frames == 0:
            if animations:
                raise ValueError("Cue too short to fit its animation beats at this frame rate")
            return
        duration = frames / self.camera.fps
        if animations:
            # Fade/creation copies must keep stable point arrays: a numeric
            # updater can otherwise replace glyph geometry during interpolation.
            suspended = []
            for animation in animations:
                if isinstance(animation, (FadeIn, FadeOut, ShowCreation, Write)):
                    mob = animation.mobject
                    if not mob.updating_suspended:
                        mob.suspend_updating()
                        suspended.append(mob)
            self.play(*animations, run_time=duration, rate_func=rate_func)
            for mob in suspended:
                mob.resume_updating()
        else:
            self.wait(duration, ignore_presenter_mode=True)

    def road(self, y=-0.62):
        self.road_y = y
        self.road_x = lambda s: -5.55 + 11.1 * s / 40
        line = Line([-5.85, y, 0], [5.85, y, 0], color=MUTED, stroke_width=2)
        ticks = VGroup()
        labels = VGroup()
        for s in range(0, 41, 4):
            x = self.road_x(s)
            ticks.add(Line([x, y - 0.08, 0], [x, y + 0.08, 0], color=GRID, stroke_width=2))
            if s % 8 == 0:
                labels.add(number(s, 0, 20, MUTED).move_to([x, y - 0.31, 0]))
        unit = formula(r"s\ (\mathrm{m})", 25, MUTED).move_to([5.65, y - 0.65, 0])
        return VGroup(line, ticks, labels, unit)

    def live_readout(self, prefix, tracker, value_fn, unit, center, color, places=2, size=36):
        left = formula(prefix, size, color)
        digits = number(value_fn(tracker.get_value()), places, size, color)
        right = formula(unit, size - 5, color)
        # Fix anchors using the widest expected numeric slot; changing digits
        # never pushes adjacent labels or changes the outer layout.
        slot_width = max(digits.get_width(), 1.30 if size >= 36 else 0.85)
        digits.move_to([0, 0, 0])
        left.move_to([-slot_width / 2 - 0.15, 0, 0], aligned_edge=RIGHT)
        right.move_to([slot_width / 2 + 0.15, 0, 0], aligned_edge=LEFT)
        group = VGroup(left, digits, right).move_to(center)
        anchor = digits.get_center().copy()
        digits.add_updater(lambda mob: mob.set_value(value_fn(tracker.get_value())).move_to(anchor))
        return group

    def build_graph(self):
        axes = Axes(
            x_range=(0, 3.3, 1), y_range=(0, 44, 8), width=10.6, height=3.85,
            axis_config={"stroke_color": MUTED, "stroke_width": 1.6,
                         "include_tip": False, "include_numbers": False},
        )
        axes.shift(np.array([-5.3, -1.92, 0]) - axes.c2p(0, 0))
        labels = VGroup()
        for t in (0, 1, 2, 3):
            labels.add(number(t, 0, 19, YELLOW if t == 2 else MUTED).move_to(axes.c2p(t, 0) + DOWN * 0.25))
        for s in (8, 16, 24, 32, 40):
            labels.add(number(s, 0, 19, YELLOW if s == 16 else MUTED).move_to(axes.c2p(0, s) + LEFT * 0.36))
        labels.add(formula(r"t\ (\mathrm{s})", 26, MUTED).move_to([5.86, -1.95, 0]))
        labels.add(formula(r"s\ (\mathrm{m})", 26, MUTED).move_to([-5.3, 2.18, 0]))
        grid = VGroup(*[
            Line(axes.c2p(0, s), axes.c2p(3.3, s), color=GRID, stroke_width=0.6)
            for s in (8, 16, 24, 32, 40)
        ])
        curve = axes.get_graph(lambda t: 4 * t * t, x_range=(0, 3.3), color=CYAN, stroke_width=4)
        law = formula(r"s(t)=4t^2", 35, CYAN).move_to([-3.25, 1.95, 0])
        return axes, VGroup(grid, axes, labels, curve, law)

    def construct(self):
        self.timeline = load_timeline(self.timeline_path)
        self.cue_index = -1
        self.subtitle = VGroup()
        self.header = VGroup()
        band = Rectangle(width=12.8, height=0.64, fill_color=SURFACE, fill_opacity=1, stroke_width=0)
        band.move_to([0, -3.35, 0])
        self.progress = VGroup(*[
            Line([-6.1 + i * 1.035, 2.72, 0], [-5.27 + i * 1.035, 2.72, 0],
                 color=GRID, stroke_width=2)
            for i in range(12)
        ])
        self.add(band, self.progress)

        road = self.road()
        clock = ValueTracker(0)
        car = SideCar()
        car.add_updater(lambda mob: mob.place_on_road(self.road_x(4 * clock.get_value() ** 2), self.road_y))
        car.update()
        question = cn("一张定格，能告诉你速度吗？", 43).move_to([0, 1.55, 0])
        frozen_note = cn("定格的是位置，不是速度", 30, YELLOW).move_to([0, -1.92, 0])
        hook_time = formula(r"t=2\,\mathrm{s}", 35, YELLOW).move_to([self.road_x(16), 0.65, 0])

        with self.cue(0):
            self.beat(0.14, FadeIn(road), FadeIn(car), FadeIn(question))
            self.beat(0.70, clock.animate.set_value(2), rate_func=linear)
            self.beat(0.83, FadeIn(frozen_note), FadeIn(hook_time))

        law = formula(r"s(t)=4t^2", 64, CYAN).move_to([0, 1.65, 0])
        units = cn("理想运动 · 时间用秒，位置用米", 26, MUTED).move_to([0, 0.94, 0])
        time_readout = self.live_readout("t=", clock, lambda t: t, r"\mathrm{s}", [-2.3, -2.05, 0], YELLOW)
        position_readout = self.live_readout("s=", clock, lambda t: 4 * t * t, r"\mathrm{m}", [2.3, -2.05, 0], CYAN)
        with self.cue(1):
            self.beat(0.13, FadeOut(question), FadeOut(frozen_note), FadeOut(hook_time), FadeOut(car))
            clock.set_value(0)
            car.update()
            time_readout.update()
            position_readout.update()
            self.beat(0.26, FadeIn(law), FadeIn(units), FadeIn(car), FadeIn(time_readout), FadeIn(position_readout))
            self.beat(0.87, clock.animate.set_value(3), rate_func=linear)

        a_dot = Dot([self.road_x(16), self.road_y, 0], fill_color=YELLOW, radius=0.085)
        b_dot = Dot([self.road_x(36), self.road_y, 0], fill_color=CORAL, radius=0.085)
        road_a = formula(r"t=2\,\mathrm{s},\quad s=16\,\mathrm{m}", 30, YELLOW).move_to([-1.1, 0.57, 0])
        road_b = formula(r"t=3\,\mathrm{s},\quad s=36\,\mathrm{m}", 30, CORAL).move_to([3.8, 0.57, 0])
        measurement = Line([self.road_x(16), -1.46, 0], [self.road_x(36), -1.46, 0], color=CORAL, stroke_width=3)
        caps = VGroup(*[
            Line([self.road_x(s), -1.58, 0], [self.road_x(s), -1.34, 0], color=CORAL, stroke_width=2)
            for s in (16, 36)
        ])
        deltas = VGroup(
            formula(r"\Delta s=20\,\mathrm{m}", 36, CORAL),
            formula(r"\Delta t=1\,\mathrm{s}", 36, YELLOW),
        ).arrange(RIGHT, buff=1.1).move_to([0, -2.14, 0])
        average = formula(r"\bar v=\frac{\Delta s}{\Delta t}=20\,\mathrm{m/s}", 51, CORAL).move_to([0, 1.75, 0])
        with self.cue(2):
            freeze(time_readout, position_readout)
            self.beat(0.12, FadeOut(law), FadeOut(units), FadeOut(time_readout), FadeOut(position_readout), FadeOut(car))
            clock.set_value(2)
            car.update()
            ghost = car.copy().clear_updaters().set_opacity(0.22)
            self.add(ghost)
            self.beat(0.25, FadeIn(car), FadeIn(a_dot), FadeIn(road_a))
            self.beat(0.58, clock.animate.set_value(3), ShowCreation(measurement), rate_func=linear)
            self.beat(0.74, FadeIn(b_dot), FadeIn(road_b), FadeIn(caps), FadeIn(deltas))
            self.beat(0.88, Write(average))

        axes, graph_base = self.build_graph()
        h = ValueTracker(1)
        point_a = axes.c2p(2, 16)
        point_b = lambda: axes.c2p(2 + h.get_value(), 4 * (2 + h.get_value()) ** 2)
        secant = Line(ORIGIN, RIGHT, color=CORAL, stroke_width=4.5)
        secant.add_updater(lambda mob: mob.put_start_and_end_on(
            axes.c2p(1.3, 16 + (16 + 4 * h.get_value()) * (1.3 - 2)),
            axes.c2p(3.25, 16 + (16 + 4 * h.get_value()) * (3.25 - 2)),
        ))
        horizontal = Line(ORIGIN, RIGHT, color=YELLOW, stroke_width=2)
        vertical = Line(ORIGIN, UP, color=CORAL, stroke_width=2)
        horizontal.add_updater(lambda mob: mob.put_start_and_end_on(point_a, axes.c2p(2 + h.get_value(), 16)))
        vertical.add_updater(lambda mob: mob.put_start_and_end_on(axes.c2p(2 + h.get_value(), 16), point_b()))
        for mob in (secant, horizontal, vertical):
            mob.update()
        a_label = formula(r"A(2,16)", 29, YELLOW).move_to(point_a + LEFT * 0.85 + UP * 0.44)
        b_label = formula(r"B(3,36)", 29, CORAL).move_to([4.0, 1.89, 0])
        dt_label = formula(r"\Delta t", 28, YELLOW).move_to(axes.c2p(2.5, 16) + DOWN * 0.24)
        ds_label = formula(r"\Delta s", 28, CORAL).move_to(axes.c2p(3, 26) + RIGHT * 0.37)
        slope_caption = cn("割线斜率 = 平均速度", 28, CORAL).move_to([-2.75, 0.98, 0])
        slope_readout = self.live_readout(r"\bar v=", h, lambda v: 16 + 4 * v, r"\mathrm{m/s}", [-2.75, 0.30, 0], CORAL, size=48)
        interval = self.live_readout(r"\Delta t=h=", h, lambda v: v, r"\mathrm{s}", [-2.7, -2.46, 0], YELLOW, size=28)
        interval_note = cn("固定 A，让 B 沿曲线靠近", 23, MUTED).move_to([2.55, -2.46, 0])
        with self.cue(3):
            freeze(car)
            self.beat(0.22, *[FadeOut(mob) for mob in (car, ghost, road, road_a, road_b, measurement, caps, deltas, average)],
                      FadeIn(graph_base), a_dot.animate.move_to(point_a), b_dot.animate.move_to(point_b()))
            b_dot.add_updater(lambda mob: mob.move_to(point_b()))
            self.beat(0.49, ShowCreation(secant), FadeIn(horizontal), FadeIn(vertical), FadeIn(a_label), FadeIn(b_label), FadeIn(dt_label), FadeIn(ds_label))
            self.beat(0.68, FadeIn(slope_caption), FadeIn(slope_readout), FadeIn(interval), FadeIn(interval_note))

        moving_b_label = formula("B", 28, CORAL)
        moving_b_label.add_updater(lambda mob: mob.next_to(point_b(), UR, buff=0.17))
        moving_b_label.update()
        with self.cue(4):
            self.beat(0.15, FadeOut(dt_label), FadeOut(ds_label), FadeOut(b_label), FadeIn(moving_b_label))
            self.beat(0.78, h.animate.set_value(0.5), rate_func=smooth)

        with self.cue(5):
            self.beat(0.12)
            self.beat(0.76, h.animate.set_value(0.1), rate_func=smooth)

        tangent = Line(axes.c2p(1.05, 0.8), axes.c2p(3.25, 36), color=GREEN, stroke_width=3)
        tangent.set_opacity(0.55)
        tangent_note = cn("切线预览", 24, GREEN).move_to([3.72, 1.45, 0])
        with self.cue(6):
            self.beat(0.16, FadeIn(tangent), FadeIn(tangent_note))
            self.beat(0.78, h.animate.set_value(0.02), rate_func=smooth)

        graph_objects = (
            graph_base, a_dot, b_dot, a_label, moving_b_label, secant, horizontal,
            vertical, slope_caption, slope_readout, interval, interval_note, tangent, tangent_note,
        )
        zero_condition = formula(r"h=0\quad\Longrightarrow\quad\Delta t=0,\ \Delta s=0", 40, YELLOW).move_to([0, 1.62, 0])
        undefined = formula(r"\frac{\Delta s}{\Delta t}=\frac{0}{0}", 72, CORAL).move_to([-0.65, 0.26, 0])
        undefined_label = cn("未定义", 36, CORAL).move_to([2.28, 0.24, 0])
        no_substitution = cn("不能直接代零", 39, INK).move_to([0, -1.05, 0])
        zero_note = cn("零除以零，不是一个速度", 27, MUTED).move_to([0, -1.82, 0])
        with self.cue(7):
            freeze(*graph_objects)
            self.beat(0.16, *[FadeOut(mob) for mob in graph_objects])
            self.beat(0.31, Write(zero_condition))
            self.beat(0.45, Write(undefined), FadeIn(undefined_label))
            self.beat(0.59, FadeIn(no_substitution), FadeIn(zero_note))

        restriction = formula(r"h\ne0", 36, YELLOW).move_to([4.72, 2.04, 0])
        algebra_step = cn("先保留一个非零的时间间隔", 28, MUTED).move_to([0, 1.87, 0])
        equations = [
            formula(tex, 55).move_to([0, 0.60, 0])
            for tex in (
                r"\bar v=\frac{4(2+h)^2-16}{h}",
                r"\bar v=\frac{16+16h+4h^2-16}{h}",
                r"\bar v=\frac{16h+4h^2}{h}",
                r"\bar v=16+4h",
            )
        ]
        for equation in equations:
            fitted(equation, 11.4, 1.3)
        limit_line = formula(r"h\to0\qquad\Longrightarrow\qquad\bar v\to16\,\mathrm{m/s}", 46, GREEN).move_to([0, -1.02, 0])
        two_sides = cn("从左侧或右侧靠近，得到同一个极限", 24, MUTED).move_to([0, -2.06, 0])
        with self.cue(8):
            self.beat(0.06, *[FadeOut(mob) for mob in (zero_condition, undefined, undefined_label, no_substitution, zero_note)])
            self.beat(0.18, FadeIn(restriction), FadeIn(algebra_step), Write(equations[0]))
            self.beat(0.30)
            self.beat(0.37, ReplacementTransform(equations[0], equations[1]))
            self.beat(0.43)
            self.beat(0.50, ReplacementTransform(equations[1], equations[2]))
            self.beat(0.56)
            self.beat(0.63, ReplacementTransform(equations[2], equations[3]))
            self.beat(0.69)
            self.beat(0.82, Write(limit_line), FadeIn(two_sides))

        local_objects, radius = self.local_zoom()
        with self.cue(9):
            self.beat(0.13, *[FadeOut(mob) for mob in (restriction, algebra_step, equations[3], limit_line, two_sides)])
            self.beat(0.30, FadeIn(local_objects))
            self.beat(0.40)
            self.beat(0.88, radius.animate.set_value(0.04), rate_func=lambda a: (1 - np.exp(-3 * a)) / (1 - np.exp(-3)))

        result_objects = self.result_shot()
        with self.cue(10):
            freeze(local_objects)
            self.beat(0.16, FadeOut(local_objects))
            self.beat(0.37, FadeIn(result_objects[0]))
            self.beat(0.58, ShowCreation(result_objects[1]), FadeIn(result_objects[2]))
            self.beat(0.79, FadeIn(result_objects[3]))

        conclusion = Group(
            cn("瞬时速度，是平均速度", 37),
            cn("在时间间隔趋近于零时的极限", 37),
        ).arrange(DOWN, buff=0.20).move_to([0, 1.38, 0])
        final_formula = formula(r"v(2)=s'(2)=16\,\mathrm{m/s}", 66, GREEN).move_to([0, -0.52, 0])
        final_rule = Line([-3.35, -1.32, 0], [3.35, -1.32, 0], color=GREEN, stroke_width=2)
        final_note = cn("用极限，读懂这一瞬间", 25, MUTED).move_to([0, -1.94, 0])
        with self.cue(11):
            self.beat(0.19, *[FadeOut(mob) for mob in result_objects])
            self.beat(0.42, FadeIn(conclusion))
            self.beat(0.63, Write(final_formula), ShowCreation(final_rule))
            self.beat(0.73, FadeIn(final_note))

    def local_zoom(self):
        """Redraw one shrinking mathematical window, with equal unit scaling.

        xi=(t-2s)/1s and eta=(s-16m)/16m are dimensionless. Thus eta=xi+xi^2/4
        for the curve and eta=xi for the tangent. BOTH screen axes use 2/radius;
        Tick labels convert back to physical seconds/metres; screen angle alone
        is not used to infer the physical slope.
        Geometry is clipped to this square analytically before sampling.
        """
        radius = ValueTracker(1.0)
        center = np.array([0.0, 0.0, 0.0])
        extent = 1.97
        local_point = lambda x, y: center + extent * np.array([x, y, 0.0]) / radius.get_value()
        border = Rectangle(width=2 * extent, height=2 * extent, stroke_color=GRID, stroke_width=1)
        grid = VGroup()
        for q in (-0.5, 0, 0.5):
            grid.add(Line([q * extent, -extent, 0], [q * extent, extent, 0], color=MUTED if q == 0 else GRID, stroke_width=1))
            grid.add(Line([-extent, q * extent, 0], [extent, q * extent, 0], color=MUTED if q == 0 else GRID, stroke_width=1))
        curve = VMobject(stroke_color=CYAN, stroke_width=3.5)

        def update_curve(mob):
            r = radius.get_value()
            upper = min(r, -2 + 2 * np.sqrt(1 + r))
            xs = np.linspace(-r, upper, 101)
            mob.set_points_smoothly([local_point(x, x + x * x / 4) for x in xs])

        curve.add_updater(update_curve)
        curve.update()
        tangent = Line([-extent, -extent, 0], [extent, extent, 0], color=GREEN, stroke_width=6)
        dot = Dot(ORIGIN, fill_color=YELLOW, radius=0.075)
        a_label = formula(r"A(2,16)", 27, YELLOW).move_to([-0.95, 0.29, 0])
        ticks = VGroup()
        for fraction in (-1, 1):
            for axis in (0, 1):
                digit = number(fraction, 2, 19, MUTED)
                anchor = np.array([fraction * extent, -extent - 0.24, 0]) if axis == 0 else np.array([-extent - 0.31, fraction * extent, 0])
                digit.add_updater(lambda mob, f=fraction, p=anchor, a=axis:
                                  mob.set_value((2 + f * radius.get_value()) if a == 0
                                                else (16 + 16 * f * radius.get_value())).move_to(p))
                digit.update()
                ticks.add(digit)
        xi_label = formula(r"t\ (\mathrm{s})", 26, MUTED).move_to([2.5, -0.24, 0])
        eta_label = formula(r"s\ (\mathrm{m})", 26, MUTED).move_to([0.28, 2.22, 0])
        normalization = Group(
            cn("始终看同一个点", 26, YELLOW),
            formula(r"t=2\,\mathrm{s}", 35, YELLOW),
            formula(r"s=16\,\mathrm{m}", 35, YELLOW),
            cn("横纵刻度随窗口一起缩小", 20, MUTED),
            cn("曲线与切线共用一个坐标系", 20, MUTED),
        ).arrange(DOWN, buff=0.32).move_to([-4.55, 0.64, 0])
        fitted(normalization, 3.2)
        radius_label = cn("时间半窗口", 25, MUTED).move_to([4.5, 1.48, 0])
        radius_number = self.live_readout(r"\pm", radius, lambda r: r, r"\mathrm{s}", [4.48, 0.85, 0], YELLOW, size=38)
        key = Group(
            Group(Line(LEFT * 0.24, RIGHT * 0.24, color=CYAN, stroke_width=4), cn("运动曲线", 24, CYAN)).arrange(RIGHT, buff=0.16),
            Group(Line(LEFT * 0.24, RIGHT * 0.24, color=GREEN, stroke_width=4), cn("A 点切线", 24, GREEN)).arrange(RIGHT, buff=0.16),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.28).move_to([4.5, -0.50, 0])
        angle_note = cn("放大的是局部，不是把曲线换成直线", 24, MUTED).move_to([0, -2.52, 0])
        return Group(border, grid, tangent, curve, dot, a_label, ticks, xi_label, eta_label,
                      normalization, radius_label, radius_number, key, angle_note), radius

    def result_shot(self):
        """A spatial match between the car and A, not a second dashboard."""
        road_y = -1.56
        road = VGroup(Line([-5.7, road_y, 0], [5.7, road_y, 0], color=MUTED, stroke_width=2))
        for x in np.linspace(-5.5, 5.5, 17):
            road.add(Line([x, road_y - 0.065, 0], [x, road_y + 0.065, 0], color=GRID, stroke_width=1.5))
        car = SideCar().place_on_road(-2.85, road_y)
        time_label = formula(r"t=2\,\mathrm{s}", 35, YELLOW).move_to([-2.85, -2.14, 0])
        position = formula(r"s=16\,\mathrm{m}", 27, MUTED).move_to([-2.85, -0.40, 0])
        tiny_axes = Axes(
            x_range=(0, 0.9, 0.2), y_range=(0, 17, 4), width=3.5, height=2.25,
            axis_config={"stroke_color": GRID, "stroke_width": 1.3, "include_tip": False},
        )
        tiny_axes.shift(np.array([1.3, -1.10, 0]) - tiny_axes.c2p(0, 0))
        # Offset the local axes explicitly; positive-range Axes otherwise put
        # their zero intercepts outside this inset, through the car and road.
        point = lambda t, s: tiny_axes.c2p(t - 1.6, s - 9)
        curve = tiny_axes.get_graph(lambda x: 4 * (x + 1.6) ** 2 - 9, x_range=(0, 0.9), color=CYAN, stroke_width=3)
        dot = Dot(point(2, 16), fill_color=YELLOW, radius=0.075)
        label = formula(r"A(2,16)", 26, YELLOW).next_to(dot, UL, buff=0.16)
        origin_time = number(1.6, 1, 18, MUTED).move_to([1.3, -1.34, 0])
        origin_position = number(9, 0, 18, MUTED).move_to([1.02, -1.1, 0])
        graph = VGroup(tiny_axes, curve, dot, label, origin_time, origin_position)
        graph_units = formula(r"t\ (\mathrm{s}),\quad s\ (\mathrm{m})", 24, MUTED).move_to([3.1, -1.98, 0])
        tangent = Line(point(1.6, 9.6), point(2.5, 24), color=GREEN, stroke_width=4)
        connector = Arrow([-1.78, -0.18, 0], [0.94, -0.18, 0], buff=0.1, color=YELLOW, stroke_width=2)
        meaning = cn("同一个瞬间", 23, YELLOW).move_to([-0.40, 0.21, 0])
        label_velocity = cn("瞬时速度", 29, GREEN)
        speed = number(16, 0, 66, GREEN)
        unit = formula(r"\mathrm{m/s}", 43, GREEN)
        speed_row = Group(label_velocity, speed, unit).arrange(RIGHT, buff=0.27).move_to([0, 1.84, 0])
        equals = formula("=", 33, INK)
        converted = number(57.6, 1, 40, INK)
        converted_unit = formula(r"\mathrm{km/h}", 31, INK)
        conversion = VGroup(equals, converted, converted_unit).arrange(RIGHT, buff=0.16).move_to([-2.70, 0.87, 0])
        base = VGroup(road, car, time_label, position, graph, graph_units)
        return (base, VGroup(tangent, connector), Group(speed_row, meaning), conversion)
