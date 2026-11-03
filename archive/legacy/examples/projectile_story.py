"""Original silent ManimGL scene; the lead owns rendering, audio and review.

Input: outputs/projectile-story-20261020/timeline.json (read-only).
The only writes are disposable text textures and measured media-event/geometry
JSON in that same output directory. Scene-local clocks, actor poses and samples
live for one render; changing the scene or timeline invalidates those outputs.
No approval, project context, audio track or final movie is produced here.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from manimlib import *

from manimind.components.typography import RasterNumber, text_image
from manimind.postproduce.freeform_pilot import subtitle_segments
from manimind.postproduce.pilot import ROOT


OUTPUT = ROOT / "outputs/projectile-story-20261020"
TIMELINE = OUTPUT / "timeline.json"
CUE_IDS = (
    "mission", "first_try", "faster", "question", "compare", "freeze",
    "horizontal", "gravity", "calculation", "transfer", "payoff",
)
BACKGROUND = "#15181C"
INK = "#EEEFEA"
MUTED = "#ADB4B6"
QUIET = "#4B545B"
SURFACE = "#242B30"
TEAL = "#65D7BF"
CORAL = "#F49782"
GOLD = "#E9CD88"
RADIUS = 0.145
G = 10.0


def load_timeline(path=TIMELINE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cues = data.get("cues")
    if not isinstance(cues, list) or any(not isinstance(c, dict) for c in cues):
        raise ValueError("ProjectileStory needs a list of cue objects")
    if [c.get("id") for c in cues] != list(CUE_IDS):
        raise ValueError(f"ProjectileStory requires cue order {CUE_IDS}")
    if data.get("fps", 30) != 30:
        raise ValueError("ProjectileStory's production clock is 30 fps")
    end = 0.0
    for cue in cues:
        for key in ("start", "duration", "speech_start", "audio_duration"):
            value = cue.get(key)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"{cue['id']}: invalid {key}")
        if cue["duration"] < 5 or abs(cue["start"] - end) > 0.001:
            raise ValueError(f"{cue['id']}: cues must be contiguous and at least 5 s")
        end = cue["start"] + cue["duration"]
        if (cue["speech_start"] < cue["start"] - 0.001
                or cue["speech_start"] + cue["audio_duration"] > end + 0.001):
            raise ValueError(f"{cue['id']}: speech is outside its cue")
        lines = cue.get("subtitle_lines")
        if (not isinstance(lines, list) or not 1 <= len(lines) <= 2
                or not all(isinstance(line, str) and line.strip() for line in lines)):
            raise ValueError(f"{cue['id']}: provide one or two subtitle lines")
        if not all(isinstance(cue.get(k), str) and cue[k].strip()
                   for k in ("text", "heading")):
            raise ValueError(f"{cue['id']}: missing text or heading")
    if not math.isclose(data.get("duration", end), end, abs_tol=0.001):
        raise ValueError("Timeline total disagrees with its cues")
    return cues


def cn(text, size=30, color=INK, *, font_index=3):
    return text_image(text, OUTPUT, size=size, color=color, font_index=font_index)


def tex(text, size=38, color=INK):
    return Tex(text, font_size=size, template="basic_ctex").set_color(color)


def fit(mob, width, height=None):
    factor = min(1.0, width / max(mob.get_width(), 1e-8))
    if height is not None:
        factor = min(factor, height / max(mob.get_height(), 1e-8))
    return mob.scale(factor)


def flight_position(t, vx, h):
    """Analytic point-particle position, clamped only at the receiving plane."""
    t = min(max(float(t), 0.0), math.sqrt(2 * h / G))
    return np.array([vx * t, max(0.0, h - G * t * t / 2), 0.0])


@dataclass(frozen=True)
class View:
    scale: float = 0.84
    x0: float = -3.85
    ground: float = -2.10

    def point(self, x, y):
        return np.array([self.x0 + self.scale * x, self.ground + self.scale * y, 0.0])

    def physical(self, point):
        return ((float(point[0]) - self.x0) / self.scale,
                (float(point[1]) - self.ground) / self.scale)


class Probe(VGroup):
    """The centre pin is the model point; the surrounding shell is illustrative."""

    def __init__(self, color):
        shell = Circle(radius=RADIUS, fill_color=color, fill_opacity=1,
                       stroke_color=INK, stroke_width=1.2)
        rim = Arc(start_angle=0.2, angle=2.1, radius=RADIUS * 0.76,
                  stroke_color=INK, stroke_width=1.2).set_opacity(0.65)
        centre = Dot(ORIGIN, radius=0.026, color=BACKGROUND)
        super().__init__(shell, rim, centre)
        self.pin = centre


class Launcher(VGroup):
    """Original one-eyed survey instrument with a horizontal contact plunger."""

    def __init__(self, muzzle):
        shell = Polygon(
            [-2.18, 0.08, 0], [-2.30, 0.44, 0], [-2.12, 0.78, 0],
            [-1.44, 0.84, 0], [-1.14, 0.56, 0], [-1.17, 0.12, 0],
            fill_color=SURFACE, fill_opacity=1, stroke_color=MUTED, stroke_width=2.3,
        )
        brow = Line([-2.08, 0.73, 0], [-1.54, 0.77, 0], color=INK, stroke_width=3)
        eye = Circle(radius=0.205, fill_color=BACKGROUND, fill_opacity=1,
                     stroke_color=INK, stroke_width=2.4).move_to([-1.55, 0.45, 0])
        self.pupil = Dot([-1.48, 0.42, 0], radius=0.074, color=TEAL)
        self.eye = eye
        neck = Polygon([-1.86, 0.1, 0], [-1.61, 0.1, 0], [-1.42, -0.13, 0],
                       [-2.04, -0.13, 0], fill_color=QUIET, fill_opacity=1, stroke_width=0)
        rail = Line([-1.3, -RADIUS, 0], [0.10, -RADIUS, 0],
                    color=INK, stroke_width=3.4)
        return_rail = Line([-1.35, -0.29, 0], [0.06, -0.29, 0],
                           color=QUIET, stroke_width=2.4)
        muzzle_mark = Line([0, -0.25, 0], [0, -0.07, 0], color=TEAL, stroke_width=2.5)
        self.plunger = VGroup(
            Line([-1.35, 0, 0], [-0.6 - RADIUS, 0, 0], color=MUTED, stroke_width=4),
            Line([-0.6 - RADIUS, -0.105, 0], [-0.6 - RADIUS, 0.105, 0],
                 color=INK, stroke_width=3),
        )
        self.lamp = Circle(radius=0.046, fill_color=TEAL, fill_opacity=1,
                           stroke_width=0).move_to([-2.06, 0.25, 0])
        super().__init__(neck, shell, brow, eye, self.pupil, self.lamp,
                         return_rail, rail, self.plunger, muzzle_mark)
        self.shift(muzzle)

    def gaze(self, point):
        centre = self.eye.get_center()
        direction = np.array(point) - centre
        direction /= max(np.linalg.norm(direction), 1e-8)
        return self.pupil.animate.move_to(centre + 0.075 * direction)


class Flight(VGroup):
    def __init__(self, clock, view, vx, h, color, orb=None):
        self.clock, self.view, self.vx, self.h = clock, view, float(vx), float(h)
        self.probe_color = color
        self.trail = VMobject(fill_opacity=0, stroke_color=color,
                              stroke_width=3.0, stroke_opacity=0.75)
        self.shadow = Ellipse(width=0.30, height=0.045, fill_color="#080A0C",
                              fill_opacity=0.75, stroke_width=0)
        self.orb = Probe(color) if orb is None else orb
        super().__init__(self.trail, self.shadow, self.orb)
        self.add_updater(lambda mob: mob.refresh())

    def refresh(self):
        t = min(max(self.clock.get_value(), 0), math.sqrt(2 * self.h / G))
        x, y, _ = flight_position(t, self.vx, self.h)
        self.orb.move_to(self.view.point(x, y))
        self.shadow.move_to(self.view.point(x, 0) + DOWN * (RADIUS + 0.02))
        times = np.linspace(0, max(t, 1e-7), 65)
        points = [self.view.point(*flight_position(s, self.vx, self.h)[:2]) for s in times]
        self.trail.set_points_smoothly(points)
        return self


class ProjectileStory(Scene):
    timeline_path = TIMELINE
    default_camera_config = {
        "fps": 30, "resolution": (1920, 1080), "background_color": BACKGROUND,
        "frame_config": {"frame_shape": (128 / 9, 8)},
    }

    def __init__(self, *args, **kwargs):
        camera = dict(kwargs.pop("camera_config", {}))
        camera.update(background_color=BACKGROUND, fps=30)
        camera["frame_config"] = dict(camera.get("frame_config", {}), frame_shape=(128 / 9, 8))
        super().__init__(*args, camera_config=camera, **kwargs)

    def get_time_progression(self, run_time, **kwargs):
        if self.skip_animations and not kwargs.get("override_skip_animations", False):
            return [run_time]
        return np.arange(1, round(run_time * self.camera.fps) + 1, dtype=float) / self.camera.fps

    @contextmanager
    def cue(self, cue_id):
        index = CUE_IDS.index(cue_id)
        if index != self.cue_index + 1:
            raise ValueError("Cues must be consumed in order")
        self.cue_index, self.stage = index, cue_id
        cue = self.timeline[index]
        self.cue_start, self.cue_duration = cue["start"], cue["duration"]
        self.last_fraction = 0.0
        self.remove(self.header, self.subtitle)
        self.header = fit(cn(cue["heading"], 29, font_index=7), 11.7, 0.36)
        self.header.move_to([-6.38, 3.52, 0], aligned_edge=LEFT)
        self.subtitle = Group()
        for part in subtitle_segments(cue):
            caption = Group(*[cn(line, 30) for line in part["text"].splitlines()])
            caption.arrange(DOWN, buff=0.095)
            fit(caption, 12.45, 0.64).move_to([0, -3.53, 0])
            caption.set_opacity(0)
            caption.add_updater(
                lambda mob, start=part["start"], stop=part["end"]:
                mob.set_opacity(1 if start <= self.get_time() < stop else 0))
            self.subtitle.add(caption)
        self.add(self.header, self.subtitle)
        yield
        self.beat(1)
        self.subtitle.clear_updaters()

    def beat(self, fraction, *animations, rate_func=smooth):
        if not self.last_fraction <= fraction <= 1:
            raise ValueError("Cue deadlines must be monotonic")
        self.last_fraction = fraction
        deadline = round((self.cue_start + fraction * self.cue_duration) * self.camera.fps)
        frames = deadline - round(self.get_time() * self.camera.fps)
        if frames < 0 or (frames == 0 and animations):
            raise RuntimeError(f"{CUE_IDS[self.cue_index]}: insufficient animation frames")
        if frames == 0:
            return
        suspended = []
        for animation in animations:
            if isinstance(animation, (FadeIn, FadeOut, ShowCreation, Write)):
                mob = animation.mobject
                if not mob.updating_suspended:
                    # Initialize followers before FadeIn copies/fixes their geometry.
                    mob.update(0)
                    mob.suspend_updating()
                    suspended.append(mob)
        if animations:
            self.play(*animations, run_time=frames / self.camera.fps, rate_func=rate_func)
        else:
            self.wait(frames / self.camera.fps, ignore_presenter_mode=True)
        for mob in suspended:
            mob.resume_updating()

    def speech_fraction(self, index, *, edge="start", offset=0):
        span = self.timeline[self.cue_index]["spoken_spans"][index]
        return (span[edge] + offset - self.cue_start) / self.cue_duration

    def update_frame(self, dt=0, force_draw=False):
        super().update_frame(dt, force_draw=force_draw)
        if not hasattr(self, "science_samples") or dt <= 0:
            return
        frame = round(self.get_time() * self.camera.fps)
        if frame == self.sample_frame:
            return
        self.sample_frame = frame
        for name, flight in self.active_flights.items():
            point = flight.orb.pin.get_center().copy()
            x, y = flight.view.physical(point)
            opacity = float(flight.orb[0].get_fill_opacity())
            if opacity < 0.01:
                continue
            self.science_samples.append({
                "frame": frame, "time": round(self.get_time(), 6),
                "cue": CUE_IDS[self.cue_index], "stage": self.stage, "ball": name,
                "t": round(flight.clock.get_value(), 9), "vx": flight.vx, "h": flight.h,
                "x": round(x, 9), "y": round(y, 9),
                "screen_center": [round(float(v), 9) for v in point],
                "units_to_screen": flight.view.scale, "screen_origin": flight.view.point(0, 0).tolist(),
                "clock_display": self.clock_digits.get_value(),
            })

    def event(self, kind):
        self.sound_events.append({"time": round(self.get_time(), 6), "kind": kind})

    def platform(self, view, h):
        top = view.point(0, h)[1] - RADIUS
        floor = view.ground - RADIUS
        return VGroup(
            Polygon([-6.32, floor, 0], [-6.32, top, 0], [-3.73, top, 0],
                    [-3.93, top - 0.18, 0], [-5.95, top - 0.18, 0], [-5.95, floor, 0],
                    fill_color=SURFACE, fill_opacity=1, stroke_width=0),
            Line([-6.32, top, 0], [-3.73, top, 0], color=MUTED, stroke_width=2),
            Line([-6.12, floor + 0.1, 0], [-6.12, top - 0.25, 0],
                 color=QUIET, stroke_width=1.4),
        )

    def receiver(self, view, x=6):
        centre = view.point(x, 0)
        belt = RoundedRectangle(width=1.05, height=0.24, corner_radius=0.055,
                                fill_color=SURFACE, fill_opacity=1,
                                stroke_color=TEAL, stroke_width=2.3)
        belt.move_to(centre + DOWN * (RADIUS + 0.12))
        rollers = VGroup(*[
            Circle(radius=0.038, fill_color=MUTED, fill_opacity=1, stroke_width=0)
            .move_to(centre + np.array([dx, -RADIUS - 0.13, 0]))
            for dx in (-0.35, -0.175, 0, 0.175, 0.35)
        ])
        ends = VGroup(*[
            Line(centre + [dx, -RADIUS - 0.1, 0], centre + [dx, 0.11, 0],
                 color=TEAL, stroke_width=2.3)
            for dx in (-0.56, 0.56)
        ])
        return VGroup(belt, rollers, ends)

    def height_ruler(self, view, h):
        low, high = view.point(0, 0)[1], view.point(0, h)[1]
        x = -5.56
        lines = VGroup(
            Line([x, low, 0], [x, high, 0], color=MUTED, stroke_width=1.5),
            *[Line([x - 0.09, y, 0], [x + 0.09, y, 0], color=MUTED, stroke_width=1.5)
              for y in (low, high)],
        )
        label = tex(rf"h={h:g}\,\mathrm{{m}}", 31).move_to([-4.66, (low + high) / 2, 0])
        return Group(lines, label)

    def numeric_row(self, prefix, value_fn, unit, center, color=INK, size=31, places=2):
        prefix_mob = tex(prefix, size, color)
        digits = RasterNumber(value_fn(), OUTPUT, size=size, color=color, decimals=places)
        suffix = tex(unit, size - 2, color)
        digits.move_to([0.32, 0, 0], aligned_edge=RIGHT)
        prefix_mob.move_to([-0.65, 0, 0], aligned_edge=RIGHT)
        suffix.move_to([0.47, 0, 0], aligned_edge=LEFT)
        row = Group(prefix_mob, digits, suffix).move_to(center)
        anchor = digits.get_right().copy()
        digits.add_updater(lambda mob: mob.set_value(value_fn()).move_to(anchor, aligned_edge=RIGHT))
        return row, digits

    def clock_mode(self, text):
        self.remove(self.mode)
        self.mode = fit(cn(text, 22, MUTED), 4.7).move_to([3.65, 2.83, 0])
        self.add(self.mode)

    def load_probe(self, color, h=5):
        return Probe(color).move_to(self.view.point(0, h) + LEFT * 0.6)

    def attach_flight(self, name, vx, color, h=5, orb=None):
        flight = Flight(self.physics, self.view, vx, h, color, orb)
        if orb is not None:
            self.remove(orb)
        self.active_flights[name] = flight
        self.add(flight)
        return flight

    def retire(self, *flights):
        for flight in flights:
            flight.clear_updaters()
            self.remove(flight)
            self.active_flights = {k: v for k, v in self.active_flights.items() if v is not flight}

    def reset_time(self, value):
        self.physics.set_value(value)
        for flight in self.active_flights.values():
            flight.refresh()
        self.clock_row.update()

    def pulse(self, point, color, fraction):
        ring = Circle(radius=0.18, stroke_color=color, stroke_width=2.0).move_to(point)
        self.add(ring)
        self.beat(fraction, ring.animate.scale(2.4).set_opacity(0))
        self.remove(ring)

    def velocity_arrows(self, flights):
        group = Group()
        for flight in flights:
            length = flight.vx * 0.19
            arrow = Arrow(ORIGIN, RIGHT * length, buff=0, stroke_width=3).set_color(flight.probe_color)
            arrow.add_updater(lambda mob, f=flight, n=length: mob.put_start_and_end_on(
                f.orb.pin.get_center(), f.orb.pin.get_center() + RIGHT * n))
            label = tex(rf"v_x={flight.vx:g}\,\mathrm{{m/s}}", 26, flight.probe_color)
            label.add_updater(lambda mob, f=flight, n=length: mob.move_to(
                f.orb.pin.get_center() + RIGHT * (n / 2) + UP * 0.30))
            group.add(arrow, label)
        return group.update(0)

    def construct(self):
        self.timeline = load_timeline(self.timeline_path)
        self.cue_index, self.sample_frame = -1, -1
        self.sound_events, self.science_samples, self.active_flights = [], [], {}
        self.header, self.subtitle, self.mode = Group(), Group(), Group()
        self.view = View()
        self.physics = ValueTracker(0)
        self.add(self.physics)
        subtitle_band = Rectangle(width=128 / 9, height=0.9, fill_color=BACKGROUND,
                                  fill_opacity=1, stroke_width=0).move_to([0, -3.55, 0])
        fine_rule = Line([-6.38, 3.19, 0], [6.38, 3.19, 0], color=QUIET, stroke_width=0.7)
        self.add(subtitle_band, fine_rule)
        floor = Rectangle(width=12.9, height=0.32, fill_color="#20262B",
                          fill_opacity=1, stroke_width=0).move_to([0, -2.405, 0])
        floor_edge = Line([-6.45, -2.245, 0], [6.45, -2.245, 0],
                          color=QUIET, stroke_width=1.8)
        receiving_plane = DashedLine([-3.85, -2.10, 0], [6.35, -2.10, 0],
                                    dash_length=0.075, color=MUTED, stroke_width=0.9).set_opacity(0.5)
        self.base = self.platform(self.view, 5)
        self.rig = Launcher(self.view.point(0, 5))
        self.belt = self.receiver(self.view)
        self.ruler = self.height_ruler(self.view, 5)
        ground_label = tex(r"y=0", 25, MUTED).move_to([5.95, -1.81, 0])
        point_note = cn("球心为质点，球的大小仅作示意", 22, MUTED).move_to([3.97, -2.82, 0])
        approx = Group(tex(r"g=10\,\mathrm{m/s^2}", 26, MUTED),
                       cn("教学近似", 21, MUTED)).arrange(DOWN, buff=0.12)
        approx.move_to([-4.75, -1.25, 0])
        goal = cn("接收区", 27, TEAL).move_to([1.19, -1.52, 0])
        range3 = tex(r"3\,\mathrm{m}", 27, TEAL).move_to(self.view.point(3, 0) + DOWN * 0.69)
        range6 = tex(r"6\,\mathrm{m}", 27, CORAL).move_to(self.view.point(6, 0) + DOWN * 0.69)
        self.clock_row, self.clock_digits = self.numeric_row(
            "t=", self.physics.get_value, r"\mathrm{s}", [0, 2.83, 0], size=32)
        staged = self.load_probe(TEAL)
        horizontal_hint = Arrow(self.view.point(0, 5), self.view.point(0, 5) + RIGHT * 1.25,
                                buff=0, stroke_width=3).set_color(TEAL)
        hint_text = cn("水平出发", 25, TEAL).next_to(horizontal_hint, UP, buff=0.16)
        with self.cue("mission"):
            self.beat(0.15, FadeIn(floor), FadeIn(floor_edge), FadeIn(self.base), FadeIn(self.rig))
            self.beat(0.33, FadeIn(self.belt), FadeIn(goal), self.rig.gaze(self.view.point(6, 0)))
            self.beat(0.59, FadeIn(self.ruler), FadeIn(approx), FadeIn(receiving_plane),
                      FadeIn(ground_label), FadeIn(point_note))
            self.beat(0.79, FadeIn(staged), ShowCreation(horizontal_hint), FadeIn(hint_text))

        speed3 = tex(r"v_x=3\,\mathrm{m/s}", 37, TEAL).move_to([-1.2, 2.11, 0])
        with self.cue("first_try"):
            self.beat(0.13, FadeOut(horizontal_hint), FadeOut(hint_text), FadeIn(speed3),
                      FadeOut(goal), FadeIn(self.clock_row))
            self.clock_mode("慢放 · 时钟为实际经过时间")
            self.beat(0.23, staged.animate.shift(RIGHT * 0.6),
                      self.rig.plunger.animate.shift(RIGHT * 0.6))
            first = self.attach_flight("first", 3, TEAL, orb=staged)
            self.event("launch")
            self.beat(0.55, self.physics.animate.set_value(1),
                      self.rig.plunger.animate.shift(LEFT * 0.6), rate_func=linear)
            self.event("land")
            self.pulse(self.view.point(3, 0), TEAL, 0.61)
            self.event("fail")
            shortfall = Line(self.view.point(3, 0) + UP * 0.37,
                             self.view.point(6, 0) + UP * 0.37, color=MUTED, stroke_width=1.6)
            short_note = cn("还差一段", 29, MUTED).move_to([-0.07, -1.38, 0])
            self.beat(0.77, FadeIn(range3), ShowCreation(shortfall), FadeIn(short_note),
                      self.rig.lamp.animate.set_color(GOLD), self.rig.gaze(self.view.point(3, 0)))

        speed6 = tex(r"v_x=6\,\mathrm{m/s}", 37, CORAL).move_to([-1.2, 2.11, 0])
        first.clear_updaters()
        self.active_flights.clear()
        staged = self.load_probe(CORAL)
        with self.cue("faster"):
            self.reset_time(0)
            landing = self.speech_fraction(1, offset=0.04)
            launch = landing - 1.25 / self.cue_duration
            self.beat(0.05, FadeOut(speed3), FadeIn(speed6), FadeIn(staged),
                      FadeOut(shortfall), FadeOut(short_note),
                      first.trail.animate.set_stroke(opacity=0.24),
                      first.orb[0].animate.set_opacity(0.38),
                      first.orb[1].animate.set_stroke(opacity=0.65 * 0.38),
                      first.orb.pin.animate.set_fill(opacity=0.38),
                      first.shadow.animate.set_fill(opacity=0.75 * 0.38))
            self.beat(launch, staged.animate.shift(RIGHT * 0.6),
                      self.rig.plunger.animate.shift(RIGHT * 0.6))
            second = self.attach_flight("second", 6, CORAL, orb=staged)
            self.event("launch")
            self.beat(landing, self.physics.animate.set_value(1),
                      self.rig.plunger.animate.shift(LEFT * 0.6), rate_func=linear)
            self.event("land")
            self.event("success")
            self.pulse(self.view.point(6, 0), TEAL, landing + 0.045)
            delivered = cn("接住了", 32, TEAL, font_index=7).move_to([2.7, -1.48, 0])
            self.beat(landing + 0.10, FadeIn(range6), FadeIn(delivered),
                      self.rig.lamp.animate.set_color(TEAL), self.rig.gaze(self.view.point(6, 0)))

        question = Group(cn("更远，", 55, font_index=7),
                         cn("也更久？", 55, GOLD, font_index=7)).arrange(DOWN, buff=0.23)
        question.move_to([2.48, 0.87, 0])
        with self.cue("question"):
            self.beat(0.21, FadeOut(speed6), FadeOut(delivered), FadeOut(self.clock_row),
                      FadeOut(self.mode), FadeIn(question))
            self.beat(0.43, self.rig.gaze([2.5, 1.3, 0]), self.rig.lamp.animate.set_color(GOLD))
            self.beat(0.82)

        legend = Group(
            tex(r"v_x=3\,\mathrm{m/s}", 29, TEAL),
            tex(r"v_x=6\,\mathrm{m/s}", 29, CORAL),
        ).arrange(RIGHT, buff=0.55).move_to([2.65, 2.15, 0])
        with self.cue("compare"):
            self.beat(0.10, FadeOut(question), FadeOut(first), FadeOut(second),
                      FadeIn(self.clock_row), FadeIn(legend))
            self.retire(first, second)
            self.reset_time(0)
            slow = self.attach_flight("slow", 3, TEAL)
            fast = self.attach_flight("fast", 6, CORAL)
            self.clock_mode("同步慢放 · 实际时间")
            start_note = cn("同一位置，同时释放", 26, MUTED).move_to([-1.5, 1.43, 0])
            self.beat(0.22, FadeIn(start_note))
            self.event("launch")
            self.beat(0.84, self.physics.animate.set_value(1), FadeOut(start_note), rate_func=linear)
            self.event("land")
            simultaneous = cn("同一刻，到达接收平面", 31, INK, font_index=7).move_to([2.75, -1.28, 0])
            self.beat(0.92, FadeIn(simultaneous))
            self.event("reveal")

        with self.cue("freeze"):
            self.stage = "replay_seek"
            self.beat(0.08, FadeOut(simultaneous), FadeOut(slow), FadeOut(fast), FadeOut(legend))
            self.reset_time(0.5)
            self.clock_mode("回看 · 暂停在半秒")
            self.stage = "freeze"
            same_height = DashedLine([-3.1, 1.05, 0], [4.75, 1.05, 0],
                                     dash_length=0.09, color=INK, stroke_width=1.6)
            x_slow = tex(r"x=1.5\,\mathrm{m}", 29, TEAL).move_to([-3.12, 1.57, 0])
            x_fast = tex(r"x=3\,\mathrm{m}", 29, CORAL).move_to([-0.80, 1.57, 0])
            y_readout, _ = self.numeric_row(
                "y=", lambda: slow.view.physical(slow.orb.pin.get_center())[1],
                r"\mathrm{m}", [3.35, 0.49, 0], size=35)
            same = cn("一前一后，仍在同一高度", 32, font_index=7).move_to([2.3, -0.3, 0])
            self.beat(0.18, FadeIn(slow), FadeIn(fast), ShowCreation(same_height))
            self.beat(0.35, FadeIn(x_slow), FadeIn(x_fast), FadeIn(y_readout))
            self.beat(0.49, FadeIn(same))
            self.event("reveal")
            self.beat(0.94)

        arrows = self.velocity_arrows((slow, fast))
        no_force = tex(r"F_x=0\quad\Longrightarrow\quad a_x=0", 43).move_to([2.3, 1.38, 0])
        inertia = cn("保留速度，不是持续受推力", 29, font_index=7).move_to([2.4, 0.69, 0])
        sample_note = cn("每 0.2 s 留下一点", 24, MUTED).move_to([3.4, -1.25, 0])
        strobes = VGroup()
        for flight in (slow, fast):
            for sample_t in (0.2, 0.4, 0.6, 0.8, 1.0):
                point = flight.view.point(*flight_position(sample_t, flight.vx, 5)[:2])
                dot = Dot(point, radius=0.035, color=flight.probe_color)
                dot.add_updater(lambda mob, at=sample_t: mob.set_opacity(
                    0.7 if self.physics.get_value() >= at else 0))
                strobes.add(dot)
        with self.cue("horizontal"):
            y_readout.clear_updaters()
            self.beat(0.14, *[FadeOut(m) for m in (same_height, x_slow, x_fast, y_readout, same)],
                      FadeIn(no_force), FadeIn(inertia))
            self.clock_mode("分解观察 · 继续慢放")
            self.beat(0.31, FadeIn(arrows), FadeIn(sample_note))
            self.add(strobes)
            self.beat(0.82, self.physics.animate.set_value(0.9), rate_func=linear)
            self.beat(0.94)

        g_arrows = Group()
        for flight in (slow, fast):
            arrow = Arrow(ORIGIN, DOWN * 0.69, buff=0, stroke_width=3).set_color(GOLD)
            arrow.add_updater(lambda mob, f=flight: mob.put_start_and_end_on(
                f.orb.pin.get_center(), f.orb.pin.get_center() + DOWN * 0.69))
            tag = tex("g", 31, GOLD)
            tag.add_updater(lambda mob, f=flight: mob.move_to(
                f.orb.pin.get_center() + DOWN * 0.36 + RIGHT * 0.22))
            g_arrows.add(arrow, tag)
        projection_line = Line([4.75, -2.1, 0], [4.75, 2.1, 0],
                               color=QUIET, stroke_width=1.3)
        projection_label = cn("竖直投影", 24, MUTED).move_to([4.75, 2.32, 0])
        projections = VGroup(
            Circle(radius=0.12, stroke_color=TEAL, stroke_width=2.7),
            Dot(radius=0.055, color=CORAL),
        )
        projections[0].add_updater(lambda mob: mob.move_to([4.75, slow.orb.pin.get_center()[1], 0]))
        projections[1].add_updater(lambda mob: mob.move_to([4.75, fast.orb.pin.get_center()[1], 0]))
        links = VGroup(*[Line(ORIGIN, RIGHT, color=f.probe_color, stroke_width=0.8).set_stroke(opacity=0.3)
                         for f in (slow, fast)])
        for link, flight in zip(links, (slow, fast)):
            link.add_updater(lambda mob, f=flight: mob.put_start_and_end_on(
                f.orb.pin.get_center(), [4.75, f.orb.pin.get_center()[1], 0]))
        initial = tex(r"v_{y0}=0,\qquad a_y=-g", 40).move_to([1.4, 1.59, 0])
        equal_fall = cn("竖直初始条件相同，加速度也相同", 29, font_index=7).move_to([1.25, 0.94, 0])
        with self.cue("gravity"):
            self.stage = "replay_seek"
            arrows.clear_updaters()
            self.beat(0.10, FadeOut(arrows), FadeOut(no_force), FadeOut(inertia),
                      FadeOut(sample_note), FadeOut(strobes), FadeOut(slow), FadeOut(fast))
            strobes.clear_updaters()
            self.reset_time(0)
            self.clock_mode("重新回放 · 只比较竖直变化")
            self.stage = "gravity"
            self.beat(0.24, FadeIn(slow), FadeIn(fast), FadeIn(g_arrows),
                      FadeIn(initial), FadeIn(equal_fall), FadeIn(projection_line), FadeIn(projection_label))
            self.add(links, projections)
            self.beat(0.84, self.physics.animate.set_value(0.8), rate_func=linear)
            projection_same = cn("两次投影重合", 24, INK).move_to([4.75, -2.78, 0])
            self.beat(0.95, FadeIn(projection_same), FadeOut(point_note))

        vertical_law = tex(r"h=\frac12 gT^2", 53).move_to([2.6, 1.65, 0])
        substitution = tex(r"5=\frac12\times10\times T^2", 46).move_to([2.6, 0.58, 0])
        time_result = tex(r"T=\sqrt{\frac{2h}{g}}=1\,\mathrm{s}", 55).move_to([2.6, 1.55, 0])
        range_law = tex(r"R=v_xT", 48, CORAL).move_to([2.6, 0.23, 0])
        which_variable = cn("横向速度进入射程，不进入落地时间", 30, font_index=7).move_to([2.6, -0.65, 0])
        with self.cue("calculation"):
            g_arrows.clear_updaters()
            links.clear_updaters()
            projections.clear_updaters()
            self.beat(0.12, *[FadeOut(m) for m in
                      (g_arrows, initial, equal_fall, links, projections, projection_line,
                       projection_label, projection_same)], FadeIn(point_note))
            self.beat(0.25, Write(vertical_law))
            self.beat(0.46, Write(substitution))
            result_start = self.speech_fraction(2)
            self.beat(result_start, self.physics.animate.set_value(1), rate_func=linear)
            self.event("land")
            self.clock_mode("落地 · 实际经过 1.00 s")
            self.beat(result_start + 0.035, FadeOut(vertical_law), FadeOut(substitution))
            self.beat(result_start + 0.09, FadeIn(time_result))
            self.event("reveal")
            self.beat(0.88, Write(range_law), FadeIn(which_variable))

        smaller_view = View(scale=0.21)
        scale_note = cn("新视图：每米长度缩为原图 1/4；设备与球大小示意", 22, MUTED)
        scale_note.move_to([1.2, 2.36, 0])
        old_height = DashedLine([-3.85, -1.05, 0], [-0.15, -1.05, 0],
                                dash_length=0.08, color=QUIET, stroke_width=1.3)
        old_height_label = cn("原高度 5 m", 24, MUTED).move_to([-0.65, -0.78, 0])
        high_h = tex(r"20\,\mathrm{m}=4h", 40).move_to([2.55, 1.5, 0])
        high_t = tex(r"T'=2T=2\,\mathrm{s}", 44).move_to([2.55, 0.62, 0])
        prediction = cn("预计落地用时", 22, MUTED).move_to([2.55, 1.04, 0])
        high_r = tex(r"R'=2R=12\,\mathrm{m}", 42, CORAL).move_to([2.55, -0.24, 0])
        unchanged_v = tex(r"v_x=6\,\mathrm{m/s}", 30, CORAL).move_to([2.55, -1.05, 0])
        with self.cue("transfer"):
            self.beat(0.08, *[FadeOut(m) for m in
                      (time_result, range_law, which_variable, slow, fast, range3, range6, approx, self.ruler)],
                      FadeIn(scale_note))
            self.retire(slow, fast)
            self.view = smaller_view
            self.reset_time(0)
            self.clock_mode("刻度缩小 · 物理条件随后改变")
            self.ruler = self.height_ruler(self.view, 5)
            self.beat(0.14, Transform(self.base, self.platform(self.view, 5)),
                      self.rig.animate.shift(DOWN * 3.15),
                      FadeIn(self.ruler),
                      Transform(self.belt, self.receiver(self.view, 6)))
            self.beat(0.18, FadeOut(self.ruler))
            self.ruler = self.height_ruler(self.view, 20)
            self.beat(self.speech_fraction(0, edge="end", offset=-0.1),
                      Transform(self.base, self.platform(self.view, 20)),
                      self.rig.animate.shift(UP * 3.15),
                      FadeIn(self.ruler),
                      Transform(self.belt, self.receiver(self.view, 12)),
                      FadeIn(old_height), FadeIn(old_height_label), FadeIn(high_h))
            self.clock_mode("高处试验 · 慢放实际时间")
            staged = self.load_probe(CORAL, h=20)
            self.beat(self.speech_fraction(1, offset=0.65), FadeIn(staged), FadeIn(unchanged_v),
                      FadeIn(high_t), FadeIn(prediction))
            self.beat(self.speech_fraction(1, offset=1.0), staged.animate.shift(RIGHT * 0.6),
                      self.rig.plunger.animate.shift(RIGHT * 0.6))
            high = self.attach_flight("high", 6, CORAL, h=20, orb=staged)
            self.event("launch")
            self.beat(self.speech_fraction(2, edge="end", offset=-0.58),
                      self.physics.animate.set_value(2),
                      self.rig.plunger.animate.shift(LEFT * 0.6), rate_func=linear)
            self.event("land")
            self.clock_mode("高处落地 · 实际经过 2.00 s")
            self.beat(self.speech_fraction(2, edge="end", offset=-0.28),
                      FadeIn(high_r), FadeOut(prediction))
            self.event("reveal")

        returned = cn("回到 5 m 发射台 · 恢复原视图尺度", 23, MUTED).move_to([2.2, 2.19, 0])
        horizontal_result = cn("横向速度：这段时间走多远", 35, CORAL, font_index=7).move_to([2.1, 1.2, 0])
        vertical_result = cn("竖直条件：什么时候落地", 35, INK, font_index=7).move_to([2.1, 0.51, 0])
        final_success = cn("送达", 42, TEAL, font_index=7).move_to([3.1, -1.14, 0])
        with self.cue("payoff"):
            self.beat(0.12, *[FadeOut(m) for m in
                      (high, high_h, high_t, high_r, unchanged_v, old_height, old_height_label,
                       scale_note, self.ruler)],
                      FadeIn(returned))
            self.retire(high)
            self.view = View()
            self.reset_time(0)
            self.ruler = self.height_ruler(self.view, 5)
            self.beat(0.20, Transform(self.base, self.platform(self.view, 5)),
                      FadeIn(self.ruler),
                      Transform(self.belt, self.receiver(self.view, 6)), FadeIn(approx), FadeIn(range6))
            self.beat(self.speech_fraction(1, offset=0.4), FadeIn(horizontal_result))
            self.clock_mode("最后一次送达 · 实际时间")
            staged = self.load_probe(CORAL)
            self.add(staged)
            self.beat(0.31, staged.animate.shift(RIGHT * 0.6),
                      self.rig.plunger.animate.shift(RIGHT * 0.6))
            final_flight = self.attach_flight("delivery", 6, CORAL, orb=staged)
            self.event("launch")
            launch_frame = round(self.get_time() * self.camera.fps)
            landing_frame = round((self.cue_start + 0.61 * self.cue_duration) * self.camera.fps)
            vertical_frame = round(self.timeline[self.cue_index]["spoken_spans"][2]["start"] * self.camera.fps)
            t_at_vertical = (vertical_frame - launch_frame) / (landing_frame - launch_frame)
            self.beat(self.speech_fraction(2), self.physics.animate.set_value(t_at_vertical),
                      self.rig.plunger.animate.shift(LEFT * 0.6), rate_func=linear)
            self.beat(0.61, self.physics.animate.set_value(1), FadeIn(vertical_result), rate_func=linear)
            self.event("land")
            self.event("success")
            self.pulse(self.view.point(6, 0), TEAL, 0.67)
            self.beat(0.77, FadeIn(final_success),
                      self.rig.gaze(self.view.point(6, 0)), self.rig.lamp.animate.set_color(TEAL))
            self.beat(0.96)

        for mob in self.mobjects:
            mob.clear_updaters()
        OUTPUT.mkdir(parents=True, exist_ok=True)
        provenance = {
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "timeline_sha256": hashlib.sha256(Path(self.timeline_path).read_bytes()).hexdigest(),
            "fps": self.camera.fps,
            "duration": round(self.get_time(), 9),
        }
        (OUTPUT / "sound-events.json").write_text(
            json.dumps({**provenance, "events": self.sound_events}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (OUTPUT / "science-samples.json").write_text(json.dumps({
            **provenance,
            "description": "Actual orb centre inverse-mapped from scene geometry after each frame update; not an approval.",
            "model": {"g": G, "ball_radius_is_illustrative": True, "initial_vy": 0},
            "samples": self.science_samples,
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
