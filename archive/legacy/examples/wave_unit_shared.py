"""Content-neutral wave typography, geometry and per-scene measured runtime.

Palette and helpers hold no lesson clock or mutable cross-lesson state. Each
scene owns its trackers, drivers, samples and focus lifecycle via construct and
tear_down; only its own attempt directory receives measured output. Changes to
this shared implementation or the pure model invalidate all dependent lessons.
"""

import json

import numpy as np
from manimlib import Circle, Dot, FadeIn, FadeOut, Group, Line, VMobject, VGroup, linear

from manimind.experiments.understanding_support import UnderstandingScene
import wave_unit_model as model


INK = "#EEF1F4"
WAVE = "#58D5B0"
PARTICLE = "#F3D36A"
SECOND = "#FF8F98"
MUTED = "#AAB3B9"
GUIDE = "#46575C"


def polyline(points, color=WAVE, width=4):
    return VMobject().set_points_as_corners(points).set_stroke(color, width)


class WaveLessonBase(UnderstandingScene):
    def label(self, text, x, y, size=32, color=INK, width=12.2):
        obj = self.cn(text, size=size, color=color)
        if obj.get_width() > width:
            obj.set_width(width)
        return obj.move_to([x, y, 0])

    def put(self, latex, x, y, size=38, color=INK, width=11.5):
        obj = self.formula(latex, size=size, color=color)
        if obj.get_width() > width:
            obj.set_width(width)
        return obj.move_to([x, y, 0])

    def title(self, text):
        self.play(FadeIn(self.label(text, 0, 3.35, 39)), run_time=1)

    def clear_stage(self):
        for driver in self.drivers:
            driver.clear_updaters()
        self.drivers = []
        objects = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        if objects:
            self.play(*(FadeOut(obj) for obj in objects), run_time=1)

    def read(self, identity, seconds, event=None):
        if event:
            self.mark(event)
        self.focus_begin(identity)
        self.wait(seconds)
        self.focus_end(identity)

    def driver(self, callback):
        result = Group()
        result.add_updater(callback)
        self.drivers.append(result)
        self.add(result)
        callback(result)
        return result

    def sample(self, kind, **values):
        self.motion_samples.append({"kind": kind, "render_s": float(self.get_time()), **values})

    def advance(self, tracker, target):
        # One displayed physical second per animated second. Holds freeze the
        # visible clock and all dependent geometry, rather than rescaling it.
        delta = target - tracker.get_value()
        if delta <= 0:
            raise ValueError("Physical time must advance; start a new experiment to reset it")
        self.play(tracker.animate.set_value(target), run_time=delta, rate_func=linear)

    @staticmethod
    def point(x, y, baseline=.25, scale=1.0):
        return np.array([-5.5 + 1.1 * x, baseline + scale * y, 0.])

    def axes(self, point, end, x_name="x", y_name="y", ymax=1.35, ticks=(0, 2, 4, 6, 8, 10)):
        axes = VGroup(Line(point(0, 0), point(end, 0)),
                      Line(point(0, -ymax), point(0, ymax))).set_stroke(GUIDE, 2)
        x_label = self.put(x_name, 0, 0, size=27, width=1.1)
        x_label.move_to(point(end, 0) + [.45 + x_label.get_width() / 2, -.28, 0])
        labels = Group(
            x_label,
            self.put(y_name, *(point(0, ymax) + [.12, .28, 0])[:2], size=27, width=1.5),
        )
        for x in ticks:
            if x <= end:
                axes.add(Line(point(x, -.045), point(x, .045), color=MUTED, stroke_width=2))
                labels.add(self.put(str(x), *(point(x, 0) + [0, -.28, 0])[:2], size=25))
        for y in (-1, 1):
            axes.add(Line(point(-.05, y), point(.05, y), color=MUTED, stroke_width=2))
            labels.add(self.put(str(y), *(point(0, y) + [-.28, 0, 0])[:2], size=24))
        return Group(axes, labels)

    def span(self, start, end, y, text, color=PARTICLE):
        line = VGroup(Line([start, y, 0], [end, y, 0]),
                      Line([start, y - .09, 0], [start, y + .09, 0]),
                      Line([end, y - .09, 0], [end, y + .09, 0])).set_stroke(color, 3)
        return Group(line, self.put(text, (start + end) / 2, y + .32, size=34, color=color))

    def clock(self, tracker, x=4.65, y=-2.65):
        value = self.number(tracker.get_value(), size=29, decimals=1).move_to([x, y, 0])
        result = Group(self.put("t=", x - .72, y, size=29), value,
                       self.put(r"\mathrm{s}", x + .65, y, size=29))
        self.driver(lambda _: value.set_value(tracker.get_value()))
        return result

    def string_world(self, tracker, forming=False, probes=(4,), baseline=.25, scale=1.0):
        p = lambda x, y: self.point(x, y, baseline, scale)
        value = model.forming_wave if forming else model.harmonic
        xs = np.linspace(0, 10, 401)
        curve = polyline([p(x, value(x, tracker.get_value())) for x in xs])
        sites = tuple(np.linspace(0, 10, 21))
        beads = VGroup(*(Dot(p(x, value(x, tracker.get_value())), radius=.035, fill_color=MUTED) for x in sites))
        selected = VGroup(*(Dot(p(x, value(x, tracker.get_value())), radius=.085,
                               fill_color=PARTICLE if i == 0 else SECOND) for i, x in enumerate(probes)))
        guides = VGroup(*(Line(p(x, -1.2), p(x, 1.2), color=GUIDE, stroke_width=1.3) for x in probes))
        axes = self.axes(p, 10, r"x\,(\mathrm m)", r"y\,(\mathrm{cm})")
        group = Group(axes, guides, curve, beads, selected)

        def update(_):
            t = float(tracker.get_value())
            curve.set_points_as_corners([p(x, value(x, t)) for x in xs])
            for bead, x in zip(beads, sites):
                bead.move_to(p(x, value(x, t)))
            for bead, x in zip(selected, probes):
                bead.move_to(p(x, value(x, t)))
            self.sample("string", physical_s=t, forming=forming,
                        particles=[{"x_m": float(x), "y_cm": value(x, t),
                                    "screen": bead.get_center().tolist()} for x, bead in zip(probes, selected)])

        self.play(FadeIn(group), run_time=1)
        self.driver(update)
        return group, selected, p

    def phase_marker(self, tracker, point, initial_x, origin_s):
        ring = Circle(radius=.14).set_stroke(WAVE, 3)
        self.driver(lambda _: ring.move_to(point(model.crest_position(initial_x, tracker.get_value(), origin_s), 1)))
        self.play(FadeIn(ring), run_time=1)
        return ring

    def construct(self):
        self.drivers, self.motion_samples, self.chapter_times = [], [], []
        for cue, method, duration in zip(self.cues, self.chapters, self.durations, strict=True):
            if cue["duration"] != duration:
                raise ValueError("Scene and plan cue durations disagree")
            self.until(cue["start"])
            begin = float(self.get_time())
            method()
            remaining = cue["start"] + duration - self.get_time()
            if remaining > 2.01:
                raise ValueError("Unassigned cue tail; allocate a readable task, not an empty hold")
            self.until(cue["start"] + duration)
            self.chapter_times.append({"id": cue["id"], "start": begin, "end": float(self.get_time())})

    def tear_down(self):
        report = {"duration": float(self.get_time()), "chapters": self.chapter_times,
                  "samples": self.motion_samples, "writer": "WaveLessonBase native updaters",
                  "consumers": ["lead", "independent reviewer"],
                  "lifecycle": "One exact scene execution",
                  "invalidation": "Scene, model, plan, context, profile, runtime, font or timing change",
                  "limitation": "Geometry observations, not pixel, science-review or comprehension approval"}
        with (self.out / "wave-motion.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
        super().tear_down()
