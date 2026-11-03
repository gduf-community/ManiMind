"""平抛运动：水平速度改变射程，不改变落地时间。

本场景消费 outputs/projectile-independence-20261024/timeline.json（逐句配音与
真实时钟），只读；渲染时把可丢弃的字形贴图和实际几何采样写回同一输出目录。
场景不写审核、不发布成片；审核通过后由 freeform_pilot assemble 合成。

时间轴由 ManimGL 的帧时钟对齐：每个 cue 结束都等到 timeline 的绝对帧边界，
慢放只改变屏幕上的推进速度，画面时钟始终显示真实物理时间。
"""

from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from manimlib import *

from manimind.components.typography import RasterNumber, text_image
from manimind.postproduce.freeform_pilot import subtitle_segments
from manimind.postproduce.pilot import ROOT

OUTPUT = ROOT / "outputs/projectile-independence-20261024"
TIMELINE = OUTPUT / "timeline.json"
CUE_IDS = (
    "setup", "together", "freeze", "horizontal", "vertical",
    "time_rule", "range_rule", "predict", "answer", "recap",
)

BACKGROUND = "#0E1318"
INK = "#ECEFE9"
MUTED = "#9AA7AE"
QUIET = "#46525C"
SURFACE = "#1B242C"
TEAL = "#5AD7C0"
CORAL = "#F29380"
GOLD = "#EBCB86"

G = 10.0
HEAD_SIZE = 36
BODY_SIZE = 42


def load_timeline(path=TIMELINE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cues = data.get("cues")
    if not isinstance(cues, list) or any(not isinstance(c, dict) for c in cues):
        raise ValueError("ProjectileIndependence needs a list of cue objects")
    if [c.get("id") for c in cues] != list(CUE_IDS):
        raise ValueError(f"ProjectileIndependence requires cue order {CUE_IDS}")
    if data.get("fps", 30) != 30:
        raise ValueError("ProjectileIndependence's production clock is 30 fps")
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
        if not cue.get("spoken_spans"):
            raise ValueError(f"{cue['id']}: sentence spans are required")
    if not math.isclose(data.get("duration", end), end, abs_tol=0.001):
        raise ValueError("Timeline total disagrees with its cues")
    return cues


def cn(text, size=30, color=INK, *, font_index=3):
    return text_image(text, OUTPUT, size=size, color=color, font_index=font_index)


def tex(text, size=38, color=INK):
    return Tex(text, font_size=size, template="basic_ctex").set_color(color)


class View:
    """Physical (m) to screen mapping, shared by one stage."""

    def __init__(self, scale, x0, ground):
        self.scale, self.x0, self.ground = float(scale), float(x0), float(ground)

    def point(self, x, y):
        return np.array([self.x0 + self.scale * x,
                         self.ground + self.scale * y, 0.0])

    def physical(self, point):
        return ((float(point[0]) - self.x0) / self.scale,
                (float(point[1]) - self.ground) / self.scale)


def disc_dot(point, color, radius=.05, opacity=1.0):
    return Circle(radius=radius, fill_color=color, fill_opacity=opacity,
                  stroke_width=0).move_to(point)


def chip(text, size=28, color=INK, radius=0.33):
    disc = Circle(radius=radius, fill_color=SURFACE, fill_opacity=1,
                  stroke_color=QUIET, stroke_width=1.4)
    return Group(disc, cn(text, size, color).move_to(disc))


class Flight:
    """One projectile; the visible centre is the model point."""

    def __init__(self, scene, view, vx, h, color, *, radius=0.135,
                 dim=False, wall_ring=False):
        self.scene, self.view = scene, view
        self.vx, self.h, self.color = float(vx), float(h), color
        self.T = math.sqrt(2 * h / G)
        self.radius = radius
        self.dim = dim
        self.active = True
        self.arrow_visible = True
        self.wall_visible = False
        self.trail = VMobject(fill_opacity=0, stroke_color=color,
                              stroke_width=1.9 if dim else 3.1)
        self.trail.set_fill(opacity=0)
        self.trail.set_stroke(opacity=0)
        self.orb = Circle(radius=radius, fill_color=color,
                          fill_opacity=.5 if dim else 1, stroke_width=0)
        self.shine = Dot(ORIGIN, radius=radius * .32, color="#FFFFFF")
        self.shine.set_opacity(.22 if dim else .5)
        self.body = VGroup(self.orb, self.shine)
        self.ground_shadow = Ellipse(width=radius * 1.9, height=radius * .42,
                                     fill_color="#000000", fill_opacity=.4,
                                     stroke_width=0)
        if wall_ring:
            self.wall_shadow = Circle(radius=radius * .72, fill_color=color,
                                      fill_opacity=0, stroke_color=color,
                                      stroke_width=2.4)
        else:
            self.wall_shadow = Dot(ORIGIN, radius=radius * .42, color=color)
        self.wall_shadow.set_opacity(0)
        self.arrow = Arrow(ORIGIN, RIGHT * .8, buff=0, stroke_width=4.2,
                           color=color, max_tip_length_to_length_ratio=.24)
        self.group = VGroup(self.trail, self.ground_shadow, self.wall_shadow,
                            self.body, self.arrow)
        self.group.add_updater(lambda mob: self.refresh())
        self.refresh()

    def refresh(self):
        t = min(max(self.scene.clock.get_value(), 0.0), self.T)
        x, y = self.vx * t, self.h - G * t * t / 2
        point = self.view.point(x, y)
        self.orb.move_to(point)
        self.shine.move_to(point + UP * self.radius * .30 + LEFT * self.radius * .28)
        self.ground_shadow.move_to(self.view.point(x, 0) + DOWN * self.radius * .55)
        self.wall_shadow.move_to(self.view.point(0, y))
        if t <= 1e-3:
            self.trail.set_stroke(opacity=0)
        else:
            samples = np.linspace(0, t, 64)
            points = [self.view.point(self.vx * s, self.h - G * s * s / 2)
                      for s in samples]
            self.trail.set_points_smoothly(points)
            self.trail.set_stroke(opacity=.42 if self.dim else .82)
        self.arrow.put_start_and_end_on(point, point + RIGHT * (.16 * self.vx))
        self.arrow.set_opacity(1 if self.arrow_visible else 0)
        self.wall_shadow.set_opacity(.95 if self.wall_visible else 0)
        return self

    def show_wall(self, visible):
        self.wall_visible = visible
        self.wall_shadow.set_opacity(.95 if visible else 0)

    def retire(self):
        self.active = False
        self.arrow.set_opacity(0)
        self.group.clear_updaters()


class ProjectileIndependence(Scene):
    timeline_path = TIMELINE
    default_camera_config = {
        "fps": 30, "resolution": (1920, 1080), "background_color": BACKGROUND,
        "frame_config": {"frame_shape": (128 / 9, 8)},
    }

    def __init__(self, *args, **kwargs):
        camera = dict(kwargs.pop("camera_config", {}))
        camera.update(background_color=BACKGROUND, fps=30)
        camera["frame_config"] = dict(camera.get("frame_config", {}),
                                      frame_shape=(128 / 9, 8))
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
        self.cue_index, self.stage_name = index, cue_id
        cue = self.timeline[index]
        self.cue_start, self.cue_duration = cue["start"], cue["duration"]
        self.last_fraction = 0.0
        self.remove(self.header, self.subtitle)
        self.header = Group(
            Rectangle(width=.055, height=.27, fill_color=GOLD, fill_opacity=1,
                      stroke_width=0).move_to([-6.99, 3.45, 0]),
            cn(cue["heading"], HEAD_SIZE, MUTED, font_index=7)
            .move_to([-6.80, 3.45, 0], aligned_edge=LEFT),
        )
        self.subtitle = Group()
        for part in subtitle_segments(cue):
            caption = self.caption(part["text"])
            caption.move_to([0, -3.42, 0])
            caption.set_opacity(0)
            caption.add_updater(
                lambda mob, start=part["start"], stop=part["end"]:
                mob.set_opacity(1 if start <= self.get_time() < stop else 0))
            self.subtitle.add(caption)
        self.add(self.header, self.subtitle)
        yield
        self.beat(1)
        self.subtitle.clear_updaters()

    def caption(self, text):
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) == 1 and len(text) > 24:
            for mark in ("，", "、", "："):
                if mark in text:
                    left, right = text.split(mark, 1)
                    if len(left) >= 6 and len(right) >= 6:
                        lines = [left + mark, right]
                        break
        caption = Group(*[cn(line, BODY_SIZE, INK) for line in lines])
        caption.arrange(DOWN, buff=.07)
        if caption.get_width() > 12.7:
            raise ValueError(f"Subtitle line too wide at body size: {text}")
        return caption

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
                    mob.update(0)
                    mob.suspend_updating()
                    suspended.append(mob)
        if animations:
            self.play(*animations, run_time=frames / self.camera.fps, rate_func=rate_func)
        else:
            self.wait(frames / self.camera.fps, ignore_presenter_mode=True)
        for mob in suspended:
            mob.resume_updating()

    def at(self, seconds, *animations, rate_func=smooth):
        if animations and all(isinstance(a, (FadeIn, FadeOut)) for a in animations):
            self.reveal(seconds, *animations, rate_func=rate_func)
        else:
            self.beat(seconds / self.cue_duration, *animations, rate_func=rate_func)

    def reveal(self, seconds, *animations, duration=.32, rate_func=smooth):
        """Short fade ending at a narration anchor, never a slow ghost fade."""
        target = seconds / self.cue_duration
        current = self.get_time() - self.cue_start
        start = max(0.0, seconds - duration)
        if start > current + 1e-6 and start / self.cue_duration >= self.last_fraction:
            self.beat(start / self.cue_duration)
            run = duration
        else:
            run = max(.12, min(duration, seconds - current))
        self.play(*animations, run_time=run, rate_func=rate_func)
        self.last_fraction = max(self.last_fraction, target)

    def speech_fraction(self, index, *, edge="start", offset=0):
        span = self.timeline[self.cue_index]["spoken_spans"][index]
        return (span[edge] + offset - self.cue_start) / self.cue_duration

    def event(self, kind):
        self.sound_events.append({"time": round(self.get_time(), 6), "kind": kind})

    # ---------- geometry ----------
    def ground(self, view, x_left=-6.55, x_right=6.55):
        y = view.ground
        line = Line([x_left, y, 0], [x_right, y, 0], color=QUIET, stroke_width=3)
        hatches = VGroup()
        x = x_left
        while x < x_right:
            hatches.add(Line([x, y - .02, 0], [x - .17, y - .20, 0],
                             color=QUIET, stroke_width=1.4, stroke_opacity=.65))
            x += .26
        return VGroup(line, hatches)

    def build_stage5(self):
        view = View(scale=.68, x0=-5.35, ground=-2.02)
        top = view.point(0, 5)[1]
        tower = Polygon(
            [-5.76, view.ground, 0], [-5.76, top, 0], [-5.35, top, 0],
            [-5.35, view.ground, 0], fill_color=SURFACE, fill_opacity=1, stroke_width=0)
        cap = Line([-5.86, top, 0], [-5.26, top, 0], color=MUTED, stroke_width=3.2)
        face = Line([-5.35, view.ground, 0], [-5.35, top, 0], color=QUIET, stroke_width=1.6)
        ruler = VGroup(
            Line([-6.32, view.ground, 0], [-6.32, top, 0], color=QUIET, stroke_width=1.5),
            Line([-6.40, view.ground, 0], [-6.24, view.ground, 0], color=QUIET, stroke_width=1.5),
            Line([-6.40, top, 0], [-6.24, top, 0], color=QUIET, stroke_width=1.5),
        )
        height = tex(r"h=5\,\mathrm{m}", 30, MUTED).move_to([-6.22, top + .27, 0])
        note = cn("忽略空气阻力 · g = 10 m/s²（教学近似）", 21, MUTED).move_to(
            [6.52, -2.52, 0], aligned_edge=RIGHT)
        return Group(self.ground(view), tower, cap, face, ruler, height, note), view

    def build_stage20(self):
        view = View(scale=.27, x0=-5.75, ground=-2.40)
        top = view.point(0, 20)[1]
        ghost_top = view.point(0, 5)[1]
        tower = Polygon(
            [-6.12, view.ground, 0], [-6.12, top, 0], [-5.75, top, 0],
            [-5.75, view.ground, 0], fill_color=SURFACE, fill_opacity=1, stroke_width=0)
        cap = Line([-6.22, top, 0], [-5.66, top, 0], color=MUTED, stroke_width=3.2)
        face = Line([-5.75, view.ground, 0], [-5.75, top, 0], color=QUIET, stroke_width=1.6)
        ghost = Group(
            DashedLine([-5.75, view.ground, 0], [-5.75, ghost_top, 0],
                       dash_length=.10, color=QUIET, stroke_width=1.6),
            DashedLine([-6.10, ghost_top, 0], [-5.75, ghost_top, 0],
                       dash_length=.10, color=QUIET, stroke_width=1.6),
            cn("5 m 对照", 22, MUTED).move_to([-5.02, ghost_top + .10, 0]),
        )
        high = cn("20 m", 28, MUTED).move_to([-6.56, 2.90, 0])
        note = cn("忽略空气阻力 · g = 10 m/s²（教学近似）", 21, MUTED).move_to(
            [6.52, -2.86, 0], aligned_edge=RIGHT)
        return Group(self.ground(view), tower, cap, face, ghost, high, note), view

    def clock_display(self):
        digits = RasterNumber(0.0, OUTPUT, size=46, color=INK, decimals=2)
        digits.move_to([6.30, 3.43, 0], aligned_edge=RIGHT)
        prefix = cn("t =", 30, MUTED, font_index=7).move_to([5.02, 3.43, 0],
                                                          aligned_edge=RIGHT)
        suffix = cn("s", 30, MUTED, font_index=7).move_to([6.46, 3.43, 0],
                                                         aligned_edge=LEFT)
        mode = cn("慢放 · 显示真实时间", 23, MUTED).move_to([6.55, 2.98, 0],
                                                      aligned_edge=RIGHT)
        digits.add_updater(lambda mob: mob.set_value(self.clock.get_value()))
        return Group(prefix, digits, suffix, mode), digits

    # ---------- construction ----------
    def construct(self):
        start = time.time()
        self.timeline = load_timeline(self.timeline_path)
        self.cue_index = -1
        self.stage_name = None
        self.header, self.subtitle = Group(), Group()
        self.clock = ValueTracker(0.0)
        self.sound_events = []
        self.samples = []
        self.sample_frame = -1
        self.flights = {}
        self.connector = None
        self.range_marks = VGroup()

        self.play_setup()
        self.play_together()
        self.play_freeze()
        self.play_horizontal()
        self.play_vertical()
        self.play_time_rule()
        self.play_range_rule()
        self.play_predict()
        self.play_answer()
        self.play_recap()

        for mob in self.mobjects:
            mob.clear_updaters()
        OUTPUT.mkdir(parents=True, exist_ok=True)
        provenance = {
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "timeline_sha256": hashlib.sha256(Path(self.timeline_path).read_bytes()).hexdigest(),
            "fps": self.camera.fps,
            "duration": round(self.get_time(), 9),
        }
        (OUTPUT / "sound-events.json").write_text(json.dumps(
            {**provenance, "events": self.sound_events}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        (OUTPUT / "science-samples.json").write_text(json.dumps({
            **provenance,
            "description": "Actual flight-body centres inverse-mapped from scene geometry after each rendered frame; evidence only, not approval.",
            "model": {"g": G, "initial_vy": 0, "radius_is_illustrative": True},
            "samples": self.samples,
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"scene finished at {self.get_time():.3f}s, {time.time()-start:.1f}s wall", flush=True)

    def add_flight(self, name, vx, color, h=5, view=None, **kwargs):
        flight = Flight(self, view or self.view, vx, h, color, **kwargs)
        self.flights[name] = flight
        return flight

    def reset_flights(self):
        self.clock.set_value(0.0)
        for flight in self.flights.values():
            flight.refresh()

    def show_connector(self):
        line = Line(ORIGIN, RIGHT * 1.0, color=GOLD,
                    stroke_width=1.6).set_opacity(0)
        label = cn("同一高度", 26, GOLD).move_to([0, 0, 0]).set_opacity(0)

        def update(mob):
            slow, fast = self.flights["slow"], self.flights["fast"]
            if self.clock.get_value() <= .04 or self.clock.get_value() >= 1.0:
                mob[0].set_opacity(0)
                mob[1].set_opacity(0)
                return
            a, b = slow.orb.get_center(), fast.orb.get_center()
            mob[0].put_start_and_end_on(a, b)
            mob[1].move_to((a + b) / 2 + DOWN * .38)
            mob[0].set_opacity(.55)
            mob[1].set_opacity(.92)

        group = Group(line, label)
        group.add_updater(update)
        self.connector = group
        self.add(group)

    def play_setup(self):
        with self.cue("setup"):
            self.stage5, self.view = self.build_stage5()
            self.play(FadeIn(self.stage5, shift=UP * .08), run_time=.45)
            slow = self.add_flight("slow", 3, CORAL, wall_ring=True)
            fast = self.add_flight("fast", 6, TEAL)
            slow.arrow_visible = False
            fast.arrow_visible = False
            self.play(FadeIn(slow.group), FadeIn(fast.group), run_time=.35)
            slow_arrow = Arrow([-5.28, 1.18, 0], [-4.68, 1.18, 0], buff=0,
                               stroke_width=4.6, color=CORAL,
                               max_tip_length_to_length_ratio=.30)
            fast_arrow = Arrow([-5.28, 1.50, 0], [-4.20, 1.50, 0], buff=0,
                               stroke_width=4.6, color=TEAL,
                               max_tip_length_to_length_ratio=.20)
            slow_label = tex(r"3\,\mathrm{m/s}", 29, CORAL).move_to([-4.50, 1.18, 0],
                                                                   aligned_edge=LEFT)
            fast_label = tex(r"6\,\mathrm{m/s}", 29, TEAL).move_to([-4.02, 1.50, 0],
                                                                  aligned_edge=LEFT)
            overlap = Circle(radius=.20, fill_opacity=0, stroke_color=CORAL,
                             stroke_width=2.0).move_to(self.view.point(0, 5))
            overlap_label = cn("两球重合", 21, MUTED).move_to(
                self.view.point(0, 5) + DOWN * .44)
            self.setup_labels = Group(slow_arrow, fast_arrow, slow_label, fast_label)
            self.overlap_marker = Group(overlap, overlap_label)
            self.at(1.0, FadeIn(self.overlap_marker))
            self.at(2.8, FadeIn(slow_arrow), FadeIn(fast_arrow))
            self.at(4.55, FadeIn(slow_label), FadeIn(fast_label))
            question = cn("谁先落地？", 62, GOLD, font_index=11).move_to([2.45, 1.35, 0])
            prompt = cn("先凭直觉猜一猜", 27, MUTED).move_to([2.45, .55, 0])
            underline = Line([1.05, .92, 0], [3.85, .92, 0], color=GOLD,
                             stroke_width=1.6, stroke_opacity=.55)
            self.question = Group(question, prompt, underline)
            self.at(7.6, FadeIn(self.question))

    def play_together(self):
        with self.cue("together"):
            self.play(FadeOut(self.question), FadeOut(self.setup_labels), run_time=.38)
            self.show_connector()
            clock, self.clock_digits = self.clock_display()
            self.clock_group = clock
            self.play(FadeIn(clock), run_time=.35)
            self.at(.78, FadeOut(self.overlap_marker))
            self.reset_flights()
            for flight in self.flights.values():
                flight.arrow_visible = False
            self.at(.9)
            self.event("launch")
            self.at(7.5, self.clock.animate.set_value(1.0), rate_func=linear)
            self.event("land")
            rings = VGroup(*[
                Circle(radius=.17, stroke_color=f.color, stroke_width=3.4)
                .move_to(f.view.point(f.vx * f.T, 0)) for f in self.flights.values()])
            self.landing_rings = rings
            self.play(*[GrowFromCenter(ring) for ring in rings], run_time=.35)
            self.connector[0].set_opacity(0)
            self.connector[1].set_opacity(0)
            self.range_marks = VGroup()
            for flight in self.flights.values():
                x = flight.vx * flight.T
                point = flight.view.point(x, 0)
                tick = DashedLine(point + DOWN * .02, point + DOWN * .42,
                                  dash_length=.07, color=flight.color, stroke_width=1.8)
                label = tex(rf"{x:g}\,\mathrm{{m}}", 27, flight.color)
                label.move_to(point + DOWN * .74)
                self.range_marks.add(tick, label)
            self.at(8.55, FadeIn(self.range_marks))
            self.together_note = Group()

    def play_freeze(self):
        with self.cue("freeze"):
            self.play(FadeOut(self.range_marks), FadeOut(self.landing_rings), run_time=.30)
            self.connector.clear_updaters()
            self.connector[0].set_opacity(0)
            self.connector[1].set_opacity(0)
            rewind = cn("回看", 24, GOLD).move_to([3.92, 3.43, 0])
            self.at(.45, FadeIn(rewind))
            # Rewind the shared physical clock instead of teleporting the balls.
            self.at(1.55, self.clock.animate.set_value(.5), rate_func=linear)
            slow, fast = self.flights["slow"], self.flights["fast"]
            guides = VGroup()
            labels = Group()
            for flight, x, side in ((slow, 1.5, LEFT), (fast, 3.0, RIGHT)):
                point = flight.view.point(x, 0)
                guides.add(DashedLine(point, flight.orb.get_center(), dash_length=.10,
                                      color=flight.color, stroke_width=1.5,
                                      stroke_opacity=.45))
                label = tex(rf"x={x:g}\,\mathrm{{m}}", 26, flight.color)
                label.next_to(point + DOWN * .55, side, buff=.16)
                labels.add(label)
            fast_center = fast.orb.get_center()
            same_height = DashedLine(slow.orb.get_center(), fast.orb.get_center(),
                                     dash_length=.08, color=GOLD,
                                     stroke_width=1.6, stroke_opacity=.60)
            y_label = tex(r"y=3.75\,\mathrm{{m}}", 26, GOLD).move_to(
                fast_center + RIGHT * 1.05 + UP * .26)
            self.at(2.0, FadeIn(guides), FadeIn(labels), FadeIn(same_height))
            self.at(5.35, FadeIn(y_label))
            self.at(6.2, FadeOut(rewind))
            self.freeze_labels = Group(guides, labels, y_label, same_height)

    def spacing_ruler(self, flight, total, y, color):
        start_x = flight.view.point(0, 0)[0]
        end_x = flight.view.point(total, 0)[0]
        group = Group(Line([start_x, y, 0], [end_x, y, 0], color=color,
                           stroke_width=1.4, stroke_opacity=.6))
        for index in range(5):
            x = start_x + (end_x - start_x) * index / 4
            group.add(Line([x, y - .065, 0], [x, y + .065, 0], color=color,
                           stroke_width=1.4, stroke_opacity=.6))
        label = cn(f"每段 {total/4:g} m", 22, color).move_to(
            [end_x + .58, y, 0], aligned_edge=LEFT)
        group.add(label)
        return group

    def play_horizontal(self):
        with self.cue("horizontal"):
            self.play(FadeOut(self.freeze_labels), run_time=.30)
            self.connector[0].set_opacity(0)
            self.at(1.35, self.clock.animate.set_value(1.0), rate_func=linear)
            marks = VGroup()
            for flight in self.flights.values():
                for t in (.25, .5, .75, 1.0):
                    point = flight.view.point(flight.vx * t, flight.h - G * t * t / 2)
                    marks.add(disc_dot(point, flight.color, radius=.05, opacity=.95))
            self.quarter_marks = marks
            self.at(2.05, FadeIn(marks), FadeOut(self.clock_group))
            title = cn("横向：匀速", 38, TEAL, font_index=7).move_to([2.75, 2.55, 0])
            law = tex(r"\Delta x=v_x\,\Delta t", 42, INK).move_to([2.75, 1.52, 0])
            no_force = Group(
                Circle(radius=.38, stroke_color=GOLD, stroke_width=2).move_to([1.05, .42, 0]),
                cn("F=0", 24, GOLD).move_to([1.05, .42, 0]),
            )
            no_force_text = cn("离手后水平方向没有力", 27, MUTED).move_to([2.95, .42, 0])
            self.at(4.2, FadeIn(title), FadeIn(law))
            self.at(5.6, FadeIn(no_force), FadeIn(no_force_text))
            rulers = Group(
                self.spacing_ruler(self.flights["fast"], 6.0, -2.34, TEAL),
                self.spacing_ruler(self.flights["slow"], 3.0, -2.70, CORAL),
            )
            self.at(11.3, FadeIn(rulers))
            equal = cn("等距，就是速度不变", 27, INK).move_to([2.75, -.55, 0])
            self.at(14.3, FadeIn(equal))
            self.horizontal_panel = Group(title, law, no_force, no_force_text, rulers, equal)

    def play_vertical(self):
        with self.cue("vertical"):
            self.play(FadeOut(self.horizontal_panel), run_time=.35)
            title = cn("竖直：下落相同", 38, GOLD, font_index=7).move_to([2.75, 2.85, 0])
            self.at(1.7, FadeIn(title))
            wall = Group()
            face_x = self.view.point(0, 0)[0]
            wall.add(Line([face_x, self.view.ground, 0], self.view.point(0, 5),
                          color=MUTED, stroke_width=2.4, stroke_opacity=.55))
            wall.add(cn("墙", 20, MUTED).move_to([face_x - .22, .22, 0]))
            projection = Group()
            for t in (.25, .5, .75, 1.0):
                y = self.view.point(0, 5 - G * t * t / 2)[1]
                wall.add(Line([face_x - .08, y, 0], [face_x + .08, y, 0],
                              color=MUTED, stroke_width=1.2, stroke_opacity=.5))
                wall.add(Circle(radius=.085, fill_opacity=0, stroke_color=CORAL,
                                stroke_width=2.0).move_to([face_x, y, 0]))
                wall.add(disc_dot([face_x, y, 0], TEAL, radius=.036))
                fast_point = self.view.point(6 * t, 5 - G * t * t / 2)
                projection.add(DashedLine(fast_point, [face_x, y, 0],
                                          dash_length=.08, color=GOLD,
                                          stroke_width=1.1, stroke_opacity=.28))
            wall.add(projection)
            self.at(5.7, FadeIn(wall))
            ladder = Group()
            x_axis, y_top = 1.15, 2.05
            scale = 2.5 / 5.0
            drops = [0, .3125, 1.25, 2.8125, 5.0]
            points = [y_top - d * scale for d in drops]
            ladder.add(Line([x_axis, points[0], 0], [x_axis, points[-1], 0],
                            color=QUIET, stroke_width=1.6))
            for index, y in enumerate(points):
                ladder.add(Line([x_axis, y, 0], [x_axis + .14, y, 0],
                                color=QUIET, stroke_width=1.2))
                ladder.add(Circle(radius=.07, fill_opacity=0, stroke_color=CORAL,
                                  stroke_width=1.8).move_to([x_axis, y, 0]))
                ladder.add(disc_dot([x_axis, y, 0], TEAL, radius=.030))
            for index in range(4):
                label = tex(rf"{drops[index+1]-drops[index]:.2f}\,\mathrm{{m}}", 22, MUTED)
                label.move_to([x_axis + .30, (points[index] + points[index + 1]) / 2, 0],
                              aligned_edge=LEFT)
                ladder.add(label)
            ratio = tex(r"1:3:5:7", 44, GOLD).move_to([4.95, 1.85, 0])
            faster = cn("墙面投影：每 0.25 s 下落距离", 23, MUTED).move_to([4.95, 2.43, 0])
            legend_dots = Group(
                Circle(radius=.09, fill_opacity=0, stroke_color=CORAL, stroke_width=2.2),
                disc_dot(ORIGIN, TEAL, radius=.034))
            legend_dots.move_to([3.55, .55, 0])
            legend = cn("两个投影始终重合", 25, INK).move_to([4.90, .55, 0])
            self.at(8.45, FadeIn(ladder), FadeIn(ratio), FadeIn(faster),
                    FadeIn(legend_dots), FadeIn(legend))
            self.vertical_panel = Group(title, wall, ladder, ratio, faster,
                                        legend_dots, legend)

    def play_time_rule(self):
        with self.cue("time_rule"):
            old_flights = list(self.flights.values())
            self.play(self.stage5.animate.set_opacity(.32), FadeOut(self.connector),
                      FadeOut(self.quarter_marks), FadeOut(self.vertical_panel),
                      *[FadeOut(flight.group) for flight in old_flights],
                      run_time=.45)
            for flight in old_flights:
                flight.retire()
            self.flights = {}
            fall_line = Line(self.view.point(0, 5), self.view.point(0, 0),
                             color=GOLD, stroke_width=1.2, stroke_opacity=.38)
            fall_dot = disc_dot(self.view.point(0, 5), GOLD, radius=.075)
            self.add(fall_line, fall_dot)
            self.at(3.62, fall_dot.animate.move_to(self.view.point(0, 0)),
                    rate_func=lambda t: t * t)
            zero = cn("0", 22, MUTED).move_to(self.view.point(0, 0) + RIGHT * .26 + DOWN * .17)
            self.add(zero)
            context = cn("h = 5 m，g = 10 m/s²", 26, MUTED).move_to([2.85, 2.55, 0])
            eq1 = tex(r"h=\tfrac12 gT^2", 50, INK).move_to([2.85, 1.62, 0])
            arrow = Arrow([2.85, 1.02, 0], [2.85, .66, 0], buff=0,
                          stroke_width=2.2, color=QUIET)
            eq2 = tex(r"T=\sqrt{\frac{2h}{g}}", 50, GOLD).move_to([2.85, -.10, 0])
            eq3 = tex(r"T=\sqrt{\frac{2\times 5}{10}}=1\,\mathrm{s}", 36, TEAL).move_to(
                [2.85, -1.42, 0])
            self.at(3.70, FadeIn(context), FadeIn(eq1))
            self.at(5.40, FadeIn(arrow), FadeIn(eq2))
            self.at(6.95, FadeIn(eq3))
            vx = tex(r"v_x", 36, MUTED).move_to([4.72, .55, 0])
            strike = Line([4.42, .41, 0], [5.02, .69, 0], color=CORAL,
                          stroke_width=3)
            no_vx = cn("不出现", 22, CORAL).move_to([4.72, .05, 0])
            self.at(8.35, FadeIn(vx), FadeIn(strike), FadeIn(no_vx))
            self.time_panel = Group(context, eq1, arrow, eq2, eq3, vx, strike, no_vx,
                                    fall_line, fall_dot, zero)

    def play_range_rule(self):
        with self.cue("range_rule"):
            self.play(FadeOut(self.time_panel),
                      self.stage5.animate.set_opacity(.55), run_time=.45)
            view = self.view
            law = tex(r"R=v_x\,T", 54, INK).move_to([3.05, 1.55, 0])
            fixed = cn("T = 1 s，不变", 28, GOLD).move_to([3.05, .55, 0])
            self.at(1.1, FadeIn(law), FadeIn(fixed))
            bars = []
            bar_mobs = VGroup()
            guides = Group()
            for vx, color, y in ((3, CORAL, -1.45), (6, TEAL, -1.75)):
                start = np.array([view.point(0, 0)[0], y, 0])
                end = np.array([view.point(vx * 1.0, 0)[0], y, 0])
                bar = Line(start, start + RIGHT * .015, color=color, stroke_width=13)
                self.add(bar)
                bar_mobs.add(bar)
                bars.append((bar, start, end))
                guides.add(DashedLine([end[0], y, 0], [end[0], view.ground, 0],
                                      dash_length=.06, color=color,
                                      stroke_width=1.3, stroke_opacity=.35))
            labels = VGroup()
            for vx, color, y in ((3, CORAL, -1.45), (6, TEAL, -1.75)):
                end = np.array([view.point(vx * 1.0, 0)[0], y, 0])
                labels.add(tex(rf"{vx}\,\mathrm{{m}}", 34, color).move_to(
                    [end[0] + .24, y, 0], aligned_edge=LEFT))
            for bar, start, end in bars:
                bar.target = end
            self.at(3.6, *[bar.animate.put_start_and_end_on(start, end)
                           for bar, start, end in bars], rate_func=linear)
            self.at(4.25, FadeIn(labels), FadeIn(guides))
            self.range_panel = Group(law, fixed, labels, bar_mobs, guides)

    def play_predict(self):
        with self.cue("predict"):
            self.play(FadeOut(self.range_panel), FadeOut(self.stage5), run_time=.45)
            self.stage20, self.view20 = self.build_stage20()
            self.play(FadeIn(self.stage20, shift=UP * .06), run_time=.55)
            ghost = Flight(self, self.view20, 6, 5, TEAL, radius=.075, dim=True)
            tall = Flight(self, self.view20, 6, 20, TEAL, radius=.135)
            ghost.arrow_visible = False
            self.flights = {"ghost5": ghost, "tall20": tall}
            self.clock.set_value(0)
            ghost.refresh()
            tall.refresh()
            self.play(FadeIn(ghost.group), FadeIn(tall.group), run_time=.35)
            speed = Group(tex(r"v_x=6\,\mathrm{m/s}", 27, TEAL),
                          cn("不变", 26, MUTED)).arrange(RIGHT, buff=.16)
            speed.move_to([-3.72, 2.83, 0])
            self.play(FadeIn(speed), run_time=.25)
            title = cn("先想一想", 34, MUTED, font_index=7).move_to([2.95, 2.55, 0])
            row1 = cn("落地时间 T", 31, INK).move_to([1.95, 1.55, 0], aligned_edge=LEFT)
            row2 = cn("射程 R", 31, INK).move_to([1.95, .35, 0], aligned_edge=LEFT)
            c1, c2, c3, c4 = chip("×2"), chip("×4"), chip("×2"), chip("×4")
            c1.move_to([4.75, 1.55, 0])
            c2.move_to([5.75, 1.55, 0])
            c3.move_to([4.75, .35, 0])
            c4.move_to([5.75, .35, 0])
            self.at(6.35, FadeIn(title), FadeIn(row1), FadeIn(c1), FadeIn(c2))
            self.at(9.95, FadeIn(row2), FadeIn(c3), FadeIn(c4))
            self.predict_panel = Group(title, row1, row2, c1, c2, c3, c4, speed)

    def play_answer(self):
        with self.cue("answer"):
            self.play(FadeOut(self.predict_panel), run_time=.35)
            self.clock.set_value(0.0)
            for flight in self.flights.values():
                flight.refresh()
                flight.arrow_visible = False
            clock, self.clock_digits = self.clock_display()
            self.clock_group = clock
            self.play(FadeIn(clock), run_time=.30)
            ghost, tall = self.flights["ghost5"], self.flights["tall20"]
            ghost_path = VMobject(stroke_color=TEAL, stroke_width=1.8)
            ghost_path.set_fill(opacity=0)
            ghost_path.set_points_smoothly([
                self.view20.point(6 * s, 5 - G * s * s / 2)
                for s in np.linspace(0, 1, 60)])
            ghost_path.set_stroke(opacity=.30)
            self.add(ghost_path)
            base = Group(
                cn("5 m 时", 26, MUTED).move_to([1.95, 2.35, 0]),
                tex(r"T=1\,\mathrm{s}", 32, MUTED).move_to([2.95, 1.45, 0]),
                tex(r"R=6\,\mathrm{m}", 32, MUTED).move_to([2.95, .25, 0]),
            )
            self.at(.9)
            self.event("launch")
            self.at(1.0, FadeIn(base), FadeIn(ghost_path))
            note = tex(r"T\propto\sqrt{h}", 30, MUTED).move_to([2.55, -1.05, 0])
            note_stamp = cn("高度 4 倍 → 时间 2 倍", 24, MUTED).move_to([5.00, -1.05, 0])
            # The 5 m reference lands at physical t=1, halfway through the tall flight.
            self.at(3.4, self.clock.animate.set_value(1.0), rate_func=linear)
            ghost_ring = Circle(radius=.13, stroke_color=TEAL, stroke_width=2.6).move_to(
                self.view20.point(6, 0))
            ghost_time = cn("1 s", 24, TEAL).move_to(
                self.view20.point(6, 0) + RIGHT * .40 + UP * .26)
            self.event("land")
            self.play(GrowFromCenter(ghost_ring), FadeIn(ghost_time), run_time=.30)
            self.at(5.9, self.clock.animate.set_value(2.0), rate_func=linear)
            tall_ring = Circle(radius=.18, stroke_color=TEAL, stroke_width=3.4).move_to(
                self.view20.point(12, 0))
            tall_time = cn("2 s", 24, TEAL).move_to(
                self.view20.point(12, 0) + RIGHT * .42 + UP * .26)
            self.event("land")
            self.play(GrowFromCenter(tall_ring), FadeIn(tall_time), run_time=.30)
            tall_t = tex(r"T=2\,\mathrm{s}", 36, TEAL).move_to([5.18, 1.45, 0])
            tall_r = tex(r"R=12\,\mathrm{m}", 36, TEAL).move_to([5.18, .25, 0])
            times2_t = cn("×2", 30, GOLD).move_to([6.55, 1.45, 0])
            times2_r = cn("×2", 30, GOLD).move_to([6.55, .25, 0])
            link_t = tex(r"\rightarrow", 26, QUIET).move_to([4.02, 1.45, 0])
            link_r = tex(r"\rightarrow", 26, QUIET).move_to([4.02, .25, 0])
            self.at(6.2, FadeIn(tall_t), FadeIn(times2_t), FadeIn(link_t))
            self.at(6.4, FadeIn(note))
            self.at(8.6, FadeIn(note_stamp))
            marks = Group()
            for x, text in ((6, "6 m"), (12, "12 m")):
                point = self.view20.point(x, 0)
                marks.add(DashedLine(point + DOWN * .03, point + DOWN * .34,
                                     dash_length=.07, color=TEAL, stroke_width=1.7))
                marks.add(cn(text, 25, TEAL).move_to(point + DOWN * .55))
            self.at(11.9, FadeIn(tall_r), FadeIn(times2_r), FadeIn(link_r),
                    FadeIn(marks))
            self.answer_panel = Group(base, tall_t, tall_r, times2_t, times2_r,
                                      link_t, link_r, note, note_stamp, marks,
                                      ghost_path, ghost_ring, tall_ring,
                                      ghost_time, tall_time)

    def play_recap(self):
        with self.cue("recap"):
            self.play(FadeOut(self.stage20), FadeOut(self.answer_panel),
                      FadeOut(self.clock_group),
                      *[FadeOut(flight.group) for flight in self.flights.values()],
                      run_time=.45)
            divider = Line([0, 2.55, 0], [0, -.30, 0], color=QUIET, stroke_width=1.3)
            left_title = cn("横向", 40, TEAL, font_index=7).move_to([-3.45, 2.25, 0])
            right_title = cn("竖直", 40, GOLD, font_index=7).move_to([3.45, 2.25, 0])
            rail = Line([-5.55, 1.25, 0], [-1.35, 1.25, 0], color=TEAL,
                        stroke_width=3, stroke_opacity=.8)
            rail_dots = VGroup(*[disc_dot([-5.55 + i * 1.05, 1.25, 0], TEAL, .055)
                                for i in range(5)])
            fall = Line([3.45, 1.90, 0], [3.45, -.10, 0], color=GOLD,
                        stroke_width=2, stroke_opacity=.6)
            fall_dots = VGroup(*[
                disc_dot([3.45, 1.90 - d, 0], GOLD, .06)
                for d in (0, .125, .50, 1.125, 2.0)])
            left_text = Group(tex(r"v_x", 30, TEAL),
                              cn("决定每秒走多远", 29, INK)).arrange(RIGHT, buff=.16)
            left_text.move_to([-3.45, .35, 0])
            right_text = Group(tex(r"h", 30, GOLD),
                               cn("决定能走多久", 29, INK)).arrange(RIGHT, buff=.16)
            right_text.move_to([3.45, -.45, 0])
            law = tex(r"R=v_x\times T", 64, INK).move_to([0, -1.75, 0])
            law_label = cn("射程", 24, MUTED).move_to([0, -1.02, 0])
            self.at(1.1, FadeIn(divider), FadeIn(left_title), FadeIn(right_title))
            self.at(2.0, FadeIn(rail), FadeIn(rail_dots), FadeIn(fall), FadeIn(fall_dots),
                    FadeIn(left_text))
            self.at(4.2, FadeIn(right_text))
            self.at(6.2, FadeIn(law_label), FadeIn(law))

    def update_frame(self, dt=0, force_draw=False):
        super().update_frame(dt, force_draw=force_draw)
        if not getattr(self, "flights", None) or dt <= 0:
            return
        frame = round(self.get_time() * self.camera.fps)
        if frame == self.sample_frame:
            return
        self.sample_frame = frame
        if frame % 2:
            return
        for name, flight in self.flights.items():
            if not flight.active:
                continue
            x, y = flight.view.physical(flight.orb.get_center())
            self.samples.append({
                "frame": frame, "time": round(self.get_time(), 6),
                "cue": CUE_IDS[self.cue_index] if self.cue_index >= 0 else None,
                "ball": name,
                "t": round(min(max(self.clock.get_value(), 0.0), flight.T), 6),
                "vx": flight.vx, "h": flight.h,
                "x": round(x, 6), "y": round(y, 6),
                "clock": round(self.clock.get_value(), 6),
            })
