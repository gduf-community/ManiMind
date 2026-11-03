"""Supervised additive revision of the complete 114-second formula lesson.

The lead owns rendering, independent review, narration installation and release.
Legacy absolute wait targets are translated only while an inherited chapter is
running. get_time, geometry samples, marks and focus windows stay on real time.
Transient chapter state is written here, consumed by this scene, and discarded
at the chapter boundary; evidence expires on any source/plan/media change.
"""

import json
import math
import sys

import numpy as np

_host_argv = sys.argv
try:
    sys.argv = [sys.argv[0]]
    from manimlib import *
    from manimind.experiments.understanding_support import UnderstandingScene
    from projectile_formula_motion_full import FullFormulaLesson
    from projectile_formula_motion import play_landing_derivation
finally:
    sys.argv = _host_argv
del _host_argv


CUE_BOUNDARIES = (0, 18, 38, 60, 80, 96, 120, 168, 182, 194)
LEGACY_CUE_BOUNDARIES = (0, 18, 38, 58, 74, 102, 114)


def flight_state(height, speed, time, gravity=10.):
    """Upward-positive y; contact values are incoming, not post-impact speeds."""
    if not all(math.isfinite(v) for v in (height, speed, time, gravity)):
        raise ValueError("Finite model inputs required")
    if height <= 0 or gravity <= 0 or speed < 0 or time < 0:
        raise ValueError("Positive height/gravity and nonnegative speed/time required")
    landing = math.sqrt(2 * height / gravity)
    t = min(time, landing)
    return {"time": t, "x": speed * t, "y": max(0., height - gravity * t * t / 2),
            "drop": gravity * t * t / 2, "vy": -gravity * t,
            "landing_time": landing, "range": speed * landing}


def slice_positions(time, spread=1.):
    """Same 5m world and mapper as the frozen lesson, at fixed model time."""
    if not 0 <= time <= 1 or not 0 <= spread <= 1:
        raise ValueError("Slice time and presentation spread must be in [0,1]")
    common = np.array([-5.10, -1.55 + .60 * (5 - 5 * time * time), 0.])
    return common, [common + np.array([speed * time * spread, 0., 0.]) for speed in (4, 8)]


def speed_arrow_ends(time):
    if not math.isfinite(time) or not 0 <= time <= 2:
        raise ValueError("Velocity demonstration covers physical seconds 0 through 2")
    start = np.array([.45, 1.05, 0.])
    return start, start + np.array([0., -.085 * 10 * time, 0.])


class IntegratedLesson(FullFormulaLesson, UnderstandingScene):
    def setup(self):
        super().setup()
        self._legacy_offset = None
        self._reading_focus = None
        self._chapter_id = None
        self._legacy_extra = 0.
        self._height_step = 0

    def heading(self, index, text):
        return Group(self.label(text, 0, 3.35, 40, width=11.8),
                     Line(self.p(-6.65, 2.94), self.p(6.65, 2.94),
                          stroke_color=self.GRID, stroke_width=1.2))

    def cn(self, text, size=32, color="#EEF1F4"):
        if getattr(self, "_chapter_id", None) == "landing" and text in {"03", "03 / 06"}:
            return Group()
        return super().cn(text, size=size, color=color)

    def _close_focus(self):
        if self._reading_focus is not None:
            self.focus_end(self._reading_focus)
            self._reading_focus = None

    def _read(self, identity):
        self._close_focus()
        self.focus_begin(identity)
        self._reading_focus = identity

    def until(self, absolute_seconds, *animations, **kwargs):
        target = absolute_seconds
        if self._legacy_offset is not None:
            target += self._legacy_offset + self._legacy_extra
            if self._chapter_id == "height" and absolute_seconds == 102:
                target = self._chapter_start + 48
        super().until(target, *animations, **kwargs)
        if self._legacy_offset is not None and absolute_seconds in (4.7, 78.2, 85):
            self._close_focus()

    def _legacy_chapter(self, identity, old_start, method):
        if self._legacy_offset is not None:
            raise ValueError("Legacy chapter clocks cannot nest")
        self._chapter_id = identity
        self._chapter_start = float(self.get_time())
        self._legacy_extra = 0.
        if identity == "height":
            self._height_step = 0
        self._legacy_offset = float(self.get_time()) - old_start
        self._event("chapter_begin", chapter=identity, old_start=old_start,
                    wait_offset=self._legacy_offset)
        try:
            method()
        finally:
            self._close_focus()
            self._legacy_offset = None
            self._legacy_extra = 0.
        self._event("chapter_end", chapter=identity)

    def page(self, root, duration=.6):
        self._close_focus()
        super().page(root, duration)

    def standard(self, index, title, with_height=True):
        data = super().standard(index, title, with_height)
        if index == 1:
            self._model_conditions = Group(
                self.label("理想模型：质点 · 匀强重力 · 无空气阻力", -.5, -2.45, 26, self.MUTED, 11.8),
                self.tex(r"v_{y0}=0\qquad y\text{向上为正}", -.5, -3.05, 29, self.MINT, 9))
            data["root"].add(self._model_conditions)
        return data

    def mark(self, identity):
        super().mark(identity)
        focuses = {
            "launch_conditions_visible": "launch_question",
            "first_ranges_visible": "same_height_result",
            "equal_gravity_visible": "shared_vertical_conditions",
            "shared_vertical_motion_complete": "equal_vertical_result",
            "vertical_equation_linked": "vertical_position_law",
            "ground_condition_applied": "landing_algebra",
            "landing_time_derived": "positive_landing_time",
            "range_products_visible": "range_products",
            "double_range_measured": "double_range_result",
            "height_prediction_ready": "height_prediction",
            "low_ball_landed_high_ball_flying": "low_landing_observation",
            "high_ball_landed": "both_landing_observation",
            "height_scaling_verified": "height_scaling_result",
            "fixed_height_relation_highlighted": "fixed_height_summary",
            "height_relation_highlighted": "height_summary",
            "final_relations_visible": "combined_range_result",
        }
        if identity in focuses:
            self._read(focuses[identity])
        if identity == "high_ball_landed":
            self.wait(5)
            self._legacy_extra += 5
            self.mark("both_landings_full_size_held")
            self._close_focus()

    def run_standard(self, d, start, end, duration):
        if self._chapter_id == "opening" and start == 0:
            d["root"].remove(self._model_conditions)
            self.remove(self._model_conditions)
            self._read("same_height_motion")
        if self._reading_focus == "range_products":
            self._close_focus()
        super().run_standard(d, start, end, duration)
        if self._reading_focus == "same_height_motion" and end == 1:
            self._close_focus()

    def _show(self, name, formula, root, duration=.4, *extra):
        super()._show(name, formula, root, duration, *extra)
        if name == "vertical":
            self._read("vertical_equations")

    def _height_algebra(self, root):
        expected = self._legacy_offset + self._legacy_extra + 90.4
        if self.get_time() < expected - 1e-5:
            raise ValueError("Observe both complete landings before scaling algebra")
        self._read("height_scaling_chain")
        super()._height_algebra(root)

    def _height_transition(self, original_duration, action):
        identities = ("height_substitution", "root_split", "root_four_evaluated",
                      "original_time_identified", "range_time_substitution",
                      "range_factor_extracted", "original_range_identified")
        identity = identities[self._height_step]
        self._height_step += 1
        self._read(identity)
        action(1.4)
        self._legacy_extra += 1.4 - original_duration
        self.mark(identity + "_ready")
        self.wait(1.2)
        self._legacy_extra += 1.2

    def _morph(self, name, target, root, duration, operation, *, arc=0, extra=()):
        parent = super()._morph
        if self._chapter_id == "height" and name in {"height_time", "height_range"}:
            self._height_transition(duration, lambda seconds: parent(
                name, target, root, seconds, operation, arc=arc, extra=extra))
        else:
            parent(name, target, root, duration, operation, arc=arc, extra=extra)

    def _merge(self, name, target, root, sources, duration, operation, *, consume=(), arc=0, paths=None):
        parent = super()._merge
        if self._chapter_id == "height" and name in {"height_time", "height_range"}:
            self._height_transition(duration, lambda seconds: parent(
                name, target, root, sources, seconds, operation, consume=consume, arc=arc, paths=paths))
        else:
            parent(name, target, root, sources, duration, operation, consume=consume, arc=arc, paths=paths)

    def _recombine(self):
        start = float(self.get_time())
        self._chapter_id = "recombine"
        common, _ = slice_positions(0)
        bottom, _ = slice_positions(1)
        marker = Dot(common, radius=.065, fill_color=self.MINT)
        root = Group(self.heading(3, "同一时刻，接上不同的横向位移"), self.axes(False),
                     Line(common, bottom, stroke_color=self.MINT, stroke_width=3), marker,
                     self.label("同一时刻的位置分解", -.8, 2.35, 29, self.MINT, 7),
                     self.label("横向展开不是实际运动", -.5, -2.85, 28, self.MUTED, 8),
                     self.tex(r"x=v_x t", 5.12, -.65, 37, width=2.7),
                     self.tex(r"v_x=4\,\mathrm{m/s}", 5.12, .65, 30, self.BLUE, 2.7),
                     self.tex(r"v_x=8\,\mathrm{m/s}", 5.12, .05, 30, self.ORANGE, 2.7))
        self.page(root)
        self.mark("position_decomposition_ready")
        self._read("position_decomposition")
        self.until(start + 2.5)
        previous, time_label, prior = None, None, 0.
        for index, (time, identity) in enumerate(((.25, "slice_025_ready"), (.5, "slice_050_ready"),
                                                  (.75, "slice_075_ready"), (1., "slice_100_ready"))):
            if previous is not None:
                self.play(previous.animate.set_opacity(.22), FadeOut(time_label), run_time=.3)
                root.remove(time_label)

            def descend(obj, alpha, begin=prior, end=time):
                point, _ = slice_positions(begin + (end - begin) * alpha)
                obj.move_to(point)

            self.play(UpdateFromAlphaFunc(marker, descend), run_time=.6, rate_func=linear)
            projection, _ = slice_positions(time)
            tick = Line(projection + .12 * LEFT, projection + .12 * RIGHT,
                        stroke_color=self.MINT, stroke_width=2)
            stamp = self.tex(f"{time:.2f}\\,\\mathrm s", -6.10, projection[1] - .05, 23, self.MINT, 1.25)
            dots = Group(Dot(projection, radius=.09, fill_color=self.BLUE),
                         Circle(radius=.15, stroke_color=self.ORANGE, stroke_width=3,
                                fill_opacity=0).move_to(projection))
            rail = Line(projection, projection + .001 * RIGHT, stroke_color=self.MINT, stroke_width=1.2)
            time_label = self.tex(f"t={time:.2f}\\,\\mathrm s", 5.12, 1.65, 33, self.MINT, 2.65)
            previous = Group(tick, stamp, rail, dots)
            root.add(previous, time_label)
            self.play(FadeIn(previous), FadeIn(time_label), run_time=.3)

            def expand(obj, alpha, physical_time=time, guide=rail):
                point, targets = slice_positions(physical_time, alpha)
                for dot, target in zip(obj, targets):
                    dot.move_to(target)
                guide.put_start_and_end_on(point, targets[-1] if alpha else point + .001 * RIGHT)

            self.play(UpdateFromAlphaFunc(dots, expand), run_time=1.4, rate_func=linear)
            self.mark(identity)
            if index == 0:
                self._read("shared_time_slices")
            self.until(start + 6 + 3.6 * index)
            prior = time
        self.mark("shared_time_slices_ready")
        self.until(start + 21.8)
        self._close_focus()
        self.until(start + 22)

    def _height_steps(self):
        start = float(self.get_time())
        self._chapter_id = "height_steps"
        x, ground, scale = -4.25, -1.65, .18

        def position(time):
            return self.p(x, ground + scale * flight_state(20, 0, time)["y"])

        ball = Dot(position(0), radius=.115, fill_color=self.MINT)
        clock = self.number(0, size=38, color=self.WHITE, decimals=2).move_to(self.p(3.8, 1.85))
        speed = self.number(0, size=38, color=self.MINT, decimals=2).move_to(self.p(3.8, .25))
        a, _ = speed_arrow_ends(0)
        velocity = Arrow(a, a + .001 * DOWN, buff=0, fill_color=self.MINT,
                         thickness=3).set_opacity(0)
        root = Group(self.heading(6, "第二秒，不是再落同样远"), ball, velocity, clock, speed,
                     Arrow(self.p(x, ground), self.p(x, 2.25), buff=0, fill_color=self.MUTED, thickness=1.6),
                     Line(self.p(x - .5, ground), self.p(x + 1.2, ground), stroke_color=self.MUTED),
                     self.tex(r"y/\mathrm m", x - .15, 2.55, 26, self.MUTED),
                     self.label("向上为正", -5.8, 2.4, 25, self.MUTED, 1.6),
                     self.label("模型时钟", 3.55, 2.45, 27, self.MUTED),
                     self.tex("t=", 2.55, 1.85, 34), self.tex(r"\mathrm s", 4.95, 1.85, 31),
                     self.label("竖直速度（负号表示向下）", 3.55, .95, 26, self.MINT, 4.6),
                     self.tex("v_y=", 2.3, .25, 34, self.MINT),
                     self.tex(r"\mathrm{m/s}", 5.5, .25, 29, self.MINT),
                     self.tex("v_y=-10t", 3.6, -1.7, 39, self.MINT, 4.3),
                     self.label("箭头表示速度，不是重力", 3.6, -2.65, 25, self.MUTED, 4.7))
        for y in (0, 5, 10, 15, 20):
            point = self.p(x, ground + scale * y)
            root.add(Line(point + .07 * LEFT, point + .07 * RIGHT, stroke_color=self.MUTED),
                     self.tex(str(y), x - .4, point[1], 24, self.MUTED, .5))
        self.page(root)
        self.mark("upward_velocity_scale_ready")
        self.until(start + 2)
        self._read("velocity_growth")

        def at_time(time):
            time = round(time, 2)
            state = flight_state(20, 0, time)
            ball.move_to(position(time))
            clock.set_value(state["time"])
            speed.set_value(state["vy"])
            a, b = speed_arrow_ends(state["time"])
            if time > 0:
                velocity.set_points_by_ends(a, b)
                velocity.set_opacity(1)
            else:
                velocity.set_opacity(0)

        self.play(UpdateFromAlphaFunc(ball, lambda _, alpha: at_time(alpha)), run_time=4, rate_func=linear)
        first = Group(Line(position(0) + .4 * RIGHT, position(1) + .4 * RIGHT,
                           stroke_color=self.BLUE, stroke_width=6),
                      self.label("第1秒：5米", -1.8, 1.75, 29, self.BLUE, 3.2))
        self.reveal(root, first, .6)
        self.mark("first_second_ready")
        self._read("first_second")
        self.until(start + 10)
        self._read("second_velocity_growth")
        self.play(UpdateFromAlphaFunc(ball, lambda _, alpha: at_time(1 + alpha)), run_time=4, rate_func=linear)
        second = Group(Line(position(1) + .4 * RIGHT, position(2) + .4 * RIGHT,
                            stroke_color=self.ORANGE, stroke_width=6),
                       self.label("第2秒：再落15米", -1.7, -.2, 29, self.ORANGE, 3.5),
                       self.tex(r"20\,\mathrm m=5\,\mathrm m+15\,\mathrm m", -2.3, -2.65, 35, width=5.1),
                       self.tex(r"0\to-10\to-20", 3.6, -.7, 33, self.MINT, 4.5))
        self.reveal(root, second, .6)
        self.mark("second_second_ready")
        self._read("second_second")
        self.until(start + 19)
        self.play(Indicate(first, color=self.BLUE, scale_factor=1.03), run_time=.7)
        self.play(Indicate(second, color=self.ORANGE, scale_factor=1.03), run_time=.7)
        self.mark("unequal_second_drops_compared")
        self.until(start + 23.8)
        self._close_focus()
        self.until(start + 24)

    def _transfer(self):
        start = float(self.get_time())
        self._chapter_id = "transfer"
        root = Group(self.heading(8, "换成45米，先想时间，再想射程"),
                     self.tex(r"h:5\to45\,\mathrm m\qquad v_x=4\,\mathrm{m/s}", 0, 1.85, 41, width=11),
                     self.tex(r"T:\ 1\,\mathrm s\to\ ?\qquad R:\ 4\,\mathrm m\to\ ?", 0, .4, 43, width=11))
        self.page(root)
        self.mark("ninefold_question_ready")
        self._read("ninefold_prediction")
        self.until(start + 5)
        self._close_focus()
        self.mark("prediction_pause_started")
        self._read("prediction_space")
        self.until(start + 7)
        self._close_focus()
        check = self._formula(r"T'=\sqrt{\frac{2\cdot45}{10}}=3\,\mathrm s",
                              {"new_time": "T'"}, 0, -1., size=41, width=10)
        self._show("transfer_time", check, root, .6)
        answer = self._formula(r"R'=4\,\mathrm{m/s}\times3\,\mathrm s=12\,\mathrm m",
                               {"new_range": "R'"}, 0, -2.3, size=39, width=11)
        self._show("transfer_range", answer, root, .6)
        self.mark("ninefold_answer_ready")
        self._read("ninefold_check")
        self.until(start + 13.8)
        self._close_focus()
        self.until(start + 14)

    def construct(self):
        self.current_page = None
        self.add(Rectangle(width=14.3, height=8.1, fill_color=self.BG, fill_opacity=1, stroke_width=0))
        self._legacy_chapter("opening", 0, self._opening)
        self._legacy_chapter("vertical", 18, self._vertical)
        self._clear_formulas()
        self._recombine()
        self._chapter_id = "landing"
        self.current_page = play_landing_derivation(self, start=float(self.get_time()), previous_page=self.current_page)
        self._close_focus()
        self._legacy_chapter("horizontal", 58, self._horizontal)
        self._clear_formulas()
        self._height_steps()
        self._legacy_chapter("height", 74, self._height)
        self._clear_formulas()
        self._transfer()
        self._clear_formulas()
        self._legacy_chapter("conclusion", 102, self._conclusion)
        self._event("complete", duration=float(self.get_time()))

    def tear_down(self):
        self._close_focus()
        report = {"schema_version": 1, "duration": float(self.get_time()),
                  "cue_boundaries": CUE_BOUNDARIES, "source_cue_boundaries": LEGACY_CUE_BOUNDARIES,
                  "events": self.full_formula_events, "samples": self.full_formula_frames,
                  "writer": "IntegratedLesson actual supervised render",
                  "consumers": ["independent pixel/formula reviewer", "lead regression gate"],
                  "lifecycle": "This exact visual render; landing has separate motion-samples.json",
                  "invalidation": "Any source, helper, plan, profile, TeX, timing or media change",
                  "limitations": "Native geometry is not pixel review, audio approval or release"}
        with (self.out / "full-formula-motion.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
        UnderstandingScene.tear_down(self)
