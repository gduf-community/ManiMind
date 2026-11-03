"""Source/intent handoff only; the lead owns pixels, review, voice and release.

Scene-local physical time is written by native animation interpolation and read
by both the fall and rate graph. Drivers are cleared at chapter end. Live
geometry reports expire with any source, plan, font, timing or media change.
"""

import json
import math
import sys

_host_argv = sys.argv
try:
    sys.argv = sys.argv[:1]
    from manimlib import *
    from projectile_precise import PreciseLesson
    from projectile_paced import PacedLandingChapter
    from projectile_integrated import IntegratedLesson, LEGACY_CUE_BOUNDARIES
    from projectile_formula_motion_full import FullFormulaLesson, matching_transform
    from manimind.experiments.understanding_support import UnderstandingScene
finally:
    sys.argv = _host_argv
del _host_argv


def fall_state(time, gravity=10.):
    """Free fall from rest; upward-positive velocity, positive downward speed."""
    if not all(math.isfinite(v) for v in (time, gravity)) or time < 0 or gravity <= 0:
        raise ValueError("Finite nonnegative time and positive gravity required")
    return {"time": time, "drop": gravity * time ** 2 / 2,
            "vy": -gravity * time, "speed": gravity * time}


def interval_distance(start, end, gravity=10.):
    first, last = fall_state(start, gravity), fall_state(end, gravity)
    if end <= start:
        raise ValueError("A positive time interval is required")
    average = (first["speed"] + last["speed"]) / 2
    return {"start": start, "end": end, "duration": end - start,
            "initial_speed": first["speed"], "final_speed": last["speed"],
            "average_speed": average, "distance": average * (end - start),
            "units": {"average_speed": "m/s", "duration": "s", "distance": "m"}}


def simultaneous_positions(time):
    if not math.isfinite(time) or not 0 <= time <= 1:
        raise ValueError("The common flight covers zero through one second")
    y = 5 - fall_state(time)["drop"]
    return ((4 * time, y), (8 * time, y))


class NonlinearLesson(PreciseLesson):
    def setup(self):
        super().setup()
        self.nonlinear_samples = []
        self._nonlinear_probe = None

    def clock(self, x=5.12, y=1.94, state=None):
        number = self.number(0, size=35).move_to(self.p(x + .04, y - .02))
        return {"root": Group(self.label("时间", x, y + .43, 25, self.MUTED),
                              self.tex("t=", x - .78, y - .02, 34), number,
                              self.tex(r"\mathrm{s}", x + .87, y - .02, 31)),
                "number": number, "status": Group(), "x": x, "y": y}

    def state(self, clock, text, color=None):
        # Frozen chapters still call this hook; there is no viewer-facing status.
        pass

    def cn(self, text, size=32, color="#EEF1F4"):
        if text == "理想模型：质点 · 匀强重力 · 无空气阻力":
            text = "小球视为质点，忽略空气阻力，重力加速度不变"
        return super().cn(text, size=size, color=color)

    def mark(self, identity):
        if identity in {"fixed_height_relation_highlighted", "height_relation_highlighted"}:
            return IntegratedLesson.mark(self, identity)
        return super().mark(identity)

    def _event(self, kind, **data):
        if kind == "time_correspondence":
            FullFormulaLesson._event(self, kind, **data)
            self._read("final_time_correspondence")
            self._hold_legacy(1.4)
        else:
            super()._event(kind, **data)

    def update_mobjects(self, dt):
        super().update_mobjects(dt)
        probe = getattr(self, "_nonlinear_probe", None)
        if probe is not None:
            self.nonlinear_samples.append({"time": float(self.get_time()), **probe()})

    def _at(self, start, local):
        UnderstandingScene.until(self, start + local)

    def _recombine(self):
        start = float(self.get_time())
        self._chapter_id = "recombine"
        balls = Group(Dot(self.pos(0, 5), radius=.09, fill_color=self.BLUE),
                      Circle(radius=.14, stroke_color=self.ORANGE, stroke_width=3,
                             fill_opacity=0).move_to(self.pos(0, 5)))
        trails, projections = Group(), Group()
        clock = self.clock()
        root = Group(self.heading(3, "同一时刻，两球仍在同一高度"), self.axes(False),
                     balls, trails, projections, clock["root"],
                     self.label("每隔0.25秒留下一个位置", -.8, 2.4, 28, self.MUTED, 7),
                     self.tex(r"v_x=4\,\mathrm{m/s}", 5.12, .6, 29, self.BLUE, 2.8),
                     self.tex(r"v_x=8\,\mathrm{m/s}", 5.12, -.1, 29, self.ORANGE, 2.8))
        self.page(root)
        self.mark("synchronous_motion_ready")
        self._read("synchronous_trails")
        self._at(start, 2)
        physical = {"time": 0.}
        stamps = []

        def draw(time):
            physical["time"] = time
            for ball, (x, y) in zip(balls, simultaneous_positions(time)):
                ball.move_to(self.pos(x, y))
            clock["number"].set_value(time)

        self._nonlinear_probe = lambda: {
            "chapter": "recombine", "physical_time": physical["time"],
            "ball_centers": [ball.get_center().tolist() for ball in balls],
            "stamp_count": len(stamps)}
        try:
            for i in range(4):
                lo, hi = i / 4, (i + 1) / 4
                self.play(UpdateFromAlphaFunc(balls, lambda _, a, lo=lo, hi=hi:
                    draw(lo + a * (hi - lo))), run_time=1.5, rate_func=linear)
                a, b = [self.pos(x, y) for x, y in simultaneous_positions(hi)]
                trails.add(balls.copy().set_opacity(.42))
                projections.add(Line(a, b, stroke_color=self.MINT, stroke_width=1).set_opacity(.35))
                stamps.append(hi)
                self.mark(("slice_025_ready", "slice_050_ready", "slice_075_ready", "slice_100_ready")[i])
            self.mark("shared_time_slices_ready")
            self._read("equal_time_spacing")
            self.reveal(root, self.label("水平间距相等，竖直间距越来越大", -.5, -2.55, 31, width=10), .6)
            self._at(start, 11.8)
            self._close_focus()
            self._at(start, 12)
        finally:
            self._nonlinear_probe = None

    def _horizontal(self):
        start = float(self.get_time())
        self._chapter_id = "horizontal"
        law = self._formula("{x}=v_x{t}", {"distance": "{x}", "eq": "=", "speed": "v_x", "time": "{t}"},
                            0, 1.9, size=44)
        root = Group(self.heading(5, "水平匀速：射程就是速度乘时间"), law)
        self.full_active["range"] = law
        self.page(root)
        self._read("horizontal_range_law")
        self._at(start, 2)
        landed = self._formula("{R}=v_x{T}", {"distance": "{R}", "eq": "=", "speed": "v_x", "time": "{T}"},
                               0, 1.9, size=44)
        FullFormulaLesson._morph(self, "range", landed, root, .8, "At landing x=R and t=T")
        self.mark("horizontal_range_law_ready")
        self._at(start, 5)
        self._read("horizontal_parallel_products")
        pairs = []
        for index, (digit, y, color) in enumerate((("4", .25, self.BLUE), ("8", -1.3, self.ORANGE)), 1):
            source = landed.copy()
            name = "range" + str(index)
            target = self._formula(r"R_" + str(index) + "={" + digit + r"}\,\frac{\mathrm{m}}{\mathrm{s}}\times{1}\,\mathrm{s}",
                {"distance": "R_" + str(index), "eq": "=", "speed": "{" + digit + "}", "time": "{1}",
                 "denominator_seconds": (r"\mathrm{s}", 0), "multiplier_seconds": (r"\mathrm{s}", 1)},
                0, y, size=38, color=color)
            self.add(source)
            pairs.append((name, source, target, digit, y, color))
        self.play(*(matching_transform(source, target, unmatched_in_place=True)
                    for _, source, target, *_ in pairs), run_time=.8)
        for name, _, target, *_ in pairs:
            self._adopt(name, target, root)
        self.mark("horizontal_products_ready")
        self._at(start, 8)
        self._read("horizontal_parallel_units")
        cancellations = Group()
        for _, _, target, *_ in pairs:
            # Explicit seconds in the denominator and multiplier, on both rows.
            for part in target.get_parts_by_tex(r"\mathrm{s}"):
                cancellations.add(Line(part.get_corner(DL), part.get_corner(UR),
                                       stroke_color=self.MINT, stroke_width=2))
        self.reveal(root, cancellations, .6)
        self._at(start, 9)
        results = [(name, self._formula("R_" + name[-1] + "={" + digit + r"}\,\mathrm{m}",
                    {"distance": "R_" + name[-1], "eq": "=", "speed": "{" + digit + "}"},
                    0, y, size=40, color=color)) for name, _, _, digit, y, color in pairs]
        self.play(*(matching_transform(self.full_active[name], target, unmatched_in_place=True)
                    for name, target in results), FadeOut(cancellations), run_time=1)
        root.remove(cancellations)
        for name, target in results:
            root.remove(self.full_active[name])
            self._adopt(name, target, root)
            self._event("parallel_units_end", name=name, actual=self._snapshot(target))
        self.mark("horizontal_units_ready")
        self._at(start, 13)

    def _height_steps(self):
        start = float(self.get_time())
        self._chapter_id = "height_steps"
        ground, top, lane = -1.1, 2.1, -5.1

        def fall_point(t):
            return self.p(lane, top - .16 * fall_state(t)["drop"])

        def graph(t, speed):
            return self.p(-1.4 + 3.1 * t, ground + .14 * speed)

        def region(points, color, opacity=.3):
            return Polygon(*(graph(t, speed) for t, speed in points),
                           fill_color=color, fill_opacity=opacity, stroke_width=0)

        ball = Dot(fall_point(0), radius=.11, fill_color=self.MINT)
        ghosts = Group()
        time_number = self.number(0, size=30).move_to(self.p(-3.6, -.65))
        trace = Line(graph(0, 0), graph(.001, .01), stroke_color=self.MINT, stroke_width=3)
        cursor = Dot(graph(0, 0), radius=.075, fill_color=self.MINT)
        guide = Line(graph(.001, 0), graph(.001, .01), stroke_color=self.MUTED, stroke_width=1)
        first_area = region([(0, 0), (.001, 0), (.001, .01)], self.BLUE)
        second_area = region([(1, 0), (1.001, 0), (1.001, 10.01), (1, 10)], self.ORANGE, 0)
        axis_labels = Group()
        for t in (0, 1, 2):
            axis_labels.add(self.tex(str(t), graph(t, 0)[0], ground - .25, 25))
        for v in (10, 20):
            axis_labels.add(self.tex(str(v), -1.75, graph(0, v)[1], 25, self.MUTED, .6),
                            Line(graph(0, v), graph(2, v), stroke_color=self.GRID, stroke_width=1))
        gravity_cue = Group(
            Arrow(self.p(-3.75, 2.05), self.p(-3.75, 1.25), buff=0,
                  fill_color=self.MINT, thickness=2.5),
            self.tex(r"g=10\,\mathrm{m/s^2}", -3.75, .85, 24, self.MINT, 2.2),
            self.tex(r"v_{y0}=0", -3.8, .25, 27, self.MINT, 2))
        root = Group(self.heading(6, "重力不变，下落却越来越快"),
                     Line(self.p(lane - .6, ground), self.p(lane + .65, ground), stroke_color=self.MUTED),
                     Arrow(self.p(lane - .55, ground), self.p(lane - .55, 2.5), buff=0,
                           fill_color=self.MUTED, thickness=1.5),
                     self.tex("y", lane - .95, 2.7, 27), self.label("向上为正", lane, 2.65, 23, width=1.8),
                     gravity_cue,
                     self.tex("t=", -4.35, -.65, 29), time_number,
                     self.tex(r"\mathrm{s}", -2.95, -.65, 25),
                     self.label("每隔0.5秒留影", -4.65, -1.65, 23, self.MUTED, 3.2),
                     Arrow(graph(0, 0), graph(2.3, 0), buff=0, fill_color=self.MUTED, thickness=1.5),
                     Arrow(graph(0, 0), graph(0, 23), buff=0, fill_color=self.MUTED, thickness=1.5),
                     self.label("下落速率", .1, 2.35, 28, self.MINT, 2.6),
                     self.tex(r"|v_y|\,/\,(\mathrm{m/s})", 2.5, 2.35, 27, self.MINT, 3),
                     self.tex(r"t/\mathrm{s}", 5.5, ground - .3, 26),
                     axis_labels, first_area, second_area, trace, guide, ghosts, ball, cursor)
        self.page(root)
        self.mark("fall_and_rate_ready")
        self._read("constant_gravity")
        relation = self.tex(r"v_y=-gt\qquad |v_y|=gt", .7, -2.65, 35, self.MINT, 9)
        self.reveal(root, relation, .6)
        self._at(start, 5)
        physical = {"time": 0., "phase": "fall"}
        proof_objects = {}
        ghosts.add(ball.copy().set_opacity(.3))

        def draw(t):
            physical["time"] = t
            state = fall_state(t)
            ball.move_to(fall_point(t))
            time_number.set_value(t)
            cursor.move_to(graph(t, state["speed"]))
            trace.put_start_and_end_on(graph(0, 0), graph(max(t, .001), max(state["speed"], .01)))
            guide.put_start_and_end_on(graph(max(t, .001), 0), graph(max(t, .001), max(state["speed"], .01)))
            end = max(.001, min(t, 1))
            first_area.become(region([(0, 0), (end, 0), (end, 10 * end)], self.BLUE))
            if t > 1:
                second_area.become(region([(1, 0), (t, 0), (t, 10 * t), (1, 10)], self.ORANGE))

        self._nonlinear_probe = lambda: {
            "chapter": "height_steps", "phase": physical["phase"],
            "physical_time": physical["time"], "ball_center": ball.get_center().tolist(),
            "cursor_center": cursor.get_center().tolist(),
            "ghost_centers": [obj.get_center().tolist() for obj in ghosts],
            "trace_ends": [trace.get_start().tolist(), trace.get_end().tolist()],
            "area_bounds": [self._geometry(first_area), self._geometry(second_area)],
            "proof_vertices": {name: [point.tolist() for point in obj.get_vertices()]
                               for name, obj in proof_objects.items()}}
        try:
            self._read("first_rate_growth")
            for lo in (0, .5):
                self.play(UpdateFromAlphaFunc(ball, lambda _, a, lo=lo: draw(lo + .5 * a)),
                          run_time=3, rate_func=linear)
                ghosts.add(ball.copy().set_opacity(.35))
            self.mark("first_rate_endpoint")
            self._read("equal_speed_increments")
            increment = self.label("每过1秒，下落速率增加10米每秒", .7, -2.05, 29, width=10)
            self.reveal(root, increment, .6)
            self._at(start, 14)
            self._read("second_rate_growth")
            for lo in (1, 1.5):
                self.play(UpdateFromAlphaFunc(ball, lambda _, a, lo=lo: draw(lo + .5 * a)),
                          run_time=3, rate_func=linear)
                ghosts.add(ball.copy().set_opacity(.35))
            self.mark("second_rate_endpoint")
            self._read("growing_gaps")
            self._at(start, 23.4)
            self.play(FadeOut(relation), FadeOut(increment), FadeOut(guide), FadeOut(gravity_cue), run_time=.6)
            root.remove(relation, increment, guide, gravity_cue)
            for lo, average, distance, color, end_at, identity in (
                    (0, 5, 5, self.BLUE, 36, "first_average_distance"),
                    (1, 15, 15, self.ORANGE, 48, "second_average_distance")):
                physical["phase"] = identity
                self._read(identity)
                hi = lo + 1
                lower = region([(lo, 0), (hi, 0), (hi, average), (lo + .5, average), (lo, 10 * lo)], color, .65)
                cap = region([(lo + .5, average), (hi, average), (hi, 10 * hi)], color, .65)
                working = Group(lower, cap)
                selected_area = first_area if lo == 0 else second_area
                selected_area.set_fill(opacity=0)
                average_line = Line(graph(lo, average), graph(hi, average), stroke_color=color, stroke_width=2)
                average_formula = self._formula(
                    r"\overline{|v_y|}=\frac{" + str(10 * lo) + "+" + str(10 * hi) + r"}{2}=" + str(average) + r"\,\mathrm{m/s}",
                    {"average": r"\overline{|v_y|}", "eq": ("=", 0)}, .7, -2.05, size=34, color=color)
                proof_objects.update(lower=lower, cap=cap)
                self.reveal(root, working, .6)
                turn = PI if lo == 0 else -PI
                self.play(Rotate(cap, turn, about_point=graph(lo + .5, average)),
                          FadeIn(average_line), FadeIn(average_formula), run_time=2)
                root.add(average_line, average_formula)
                self.mark(identity + "_rectangle_ready")
                self.wait(2.4)
                product = self._formula(str(average) + r"\,\mathrm{m/s}\times1\,\mathrm{s}=" + str(distance) + r"\,\mathrm{m}",
                    {"eq": "="}, .7, -2.8, size=34, color=color)
                brace = self.height_brace(-4.7, fall_point(hi)[1], fall_point(lo)[1],
                                          str(distance) + r"\,\mathrm{m}", color, -4.05, 27)
                self.reveal(root, Group(product, brace), .8)
                self.mark(identity + "_distance_ready")
                self._at(start, end_at - 2.6)
                self.play(Rotate(cap, -turn, about_point=graph(lo + .5, average)), run_time=1.4)
                self.play(FadeOut(working), FadeOut(average_line), FadeOut(average_formula),
                          FadeOut(product), run_time=.6)
                root.remove(working, average_line, average_formula)
                proof_objects.clear()
                selected_area.set_fill(opacity=.3)
                # product was nested with the brace; detach it before retirement.
                for group in root.submobjects:
                    if product in group.submobjects:
                        group.remove(product)
                self._at(start, end_at)
            physical["phase"] = "total_distance"
            self._read("total_distance")
            total = self.tex(r"5\,\mathrm m+15\,\mathrm m=20\,\mathrm m", .7, -2.2, 35, width=9)
            self.reveal(root, total, .6)
            self.mark("two_interval_distances_ready")
            self._at(start, 53.4)
            self.play(FadeOut(total), FadeOut(first_area), FadeOut(second_area), FadeOut(guide), run_time=.6)
            root.remove(total, first_area, second_area)
            self._read("triangle_distance_law")
            physical["phase"] = "triangle_law"
            triangle = region([(0, 0), (1, 0), (1, 10)], self.MINT, .4)
            base = Line(graph(0, 0) + .55 * DOWN, graph(1, 0) + .55 * DOWN, stroke_color=self.MINT, stroke_width=3)
            side = Line(graph(1, 0), graph(1, 10), stroke_color=self.MINT, stroke_width=3)
            base_label = self.tex("T", graph(.5, 0)[0], ground - .8, 30, self.MINT)
            side_label = self.tex("gT", graph(1, 5)[0] + .4, graph(1, 5)[1], 30, self.MINT)
            relation = self._formula(r"s=\frac{1}{2}({g}{T}){T}",
                {"distance": "s", "eq": "=", "half": r"\frac{1}{2}", "time": ("{T}", 0), "gravity": "{g}"},
                .7, -2.85, size=40, width=10)
            self.reveal(root, Group(triangle, base, side, base_label, side_label), .6)
            FullFormulaLesson._show(self, "distance_law", relation, root, .8)
            self.wait(2)
            squared = self._formula(r"s=\frac{1}{2}{g}{T}^{2}",
                {"distance": "s", "eq": "=", "half": r"\frac{1}{2}", "gravity": "{g}", "time": "{T}"},
                .7, -2.85, size=40, width=10)
            FullFormulaLesson._morph(self, "distance_law", squared, root, 1.6,
                                     "Triangle base T times height gT, divided by two")
            self.mark("triangle_distance_law_ready")
            self._at(start, 60)
            self._read("double_time_four_area")
            physical["phase"] = "time_scaling"
            stretch = {"factor": 1.}
            old_probe = self._nonlinear_probe
            self._nonlinear_probe = lambda: {**old_probe(), "scale_factor": stretch["factor"],
                "triangle_vertices": [point.tolist() for point in triangle.get_vertices()],
                "base_ends": [base.get_start().tolist(), base.get_end().tolist()],
                "side_ends": [side.get_start().tolist(), side.get_end().tolist()]}

            def double(_, alpha):
                factor = 1 + alpha
                stretch["factor"] = factor
                triangle.become(region([(0, 0), (factor, 0), (factor, 10 * factor)], self.MINT, .4))
                base.put_start_and_end_on(graph(0, 0) + .55 * DOWN, graph(factor, 0) + .55 * DOWN)
                side.put_start_and_end_on(graph(factor, 0), graph(factor, 10 * factor))
                base_label.move_to(self.p(graph(factor / 2, 0)[0], ground - .8))
                side_label.move_to(graph(factor, 5 * factor) + .4 * RIGHT)

            self.play(UpdateFromAlphaFunc(triangle, double), run_time=3, rate_func=linear)
            self.play(Transform(base_label, self.tex("2T", base_label.get_x(), base_label.get_y(), 30, self.MINT)),
                      Transform(side_label, self.tex("2gT", side_label.get_x(), side_label.get_y(), 30, self.MINT)), run_time=.6)
            tiles = Group(*(region(points, color, .55) for points, color in (
                ([(0, 0), (1, 0), (1, 10)], self.BLUE),
                ([(1, 0), (2, 0), (2, 10)], self.MINT),
                ([(1, 10), (2, 10), (2, 20)], self.ORANGE),
                ([(1, 0), (2, 10), (1, 10)], self.WHITE))))
            self.reveal(root, tiles, .8)
            self.mark("four_equal_areas_ready")
            scale_result = self._formula(r"s(2T)=4s(T)",
                {"distance": ("s", 0), "eq": "="}, .7, -2.85, size=37, color=self.MINT, width=9)
            FullFormulaLesson._morph(self, "distance_law", scale_result, root, .6,
                                     "Replace distance law with its doubled-time consequence")
            self._at(start, 69.8)
            self._close_focus()
            self._at(start, 70)
        finally:
            self._nonlinear_probe = None
            self._clear_formulas()

    def _direct_chapter(self, identity, method):
        self._chapter_id = identity
        self._event("chapter_begin", chapter=identity)
        method()
        self._close_focus()
        self._event("chapter_end", chapter=identity)

    def _landing(self):
        chapter = PacedLandingChapter(self, self.get_time())
        try:
            self.current_page = chapter.play(self.current_page)
        finally:
            chapter.driver.clear_updaters()
            self.remove(chapter.driver)
            chapter.write_report()

    def construct(self):
        self.current_page = None
        self.add(Rectangle(width=14.3, height=8.1, fill_color=self.BG, fill_opacity=1, stroke_width=0))
        self._legacy_chapter("opening", 0, self._opening)
        self._legacy_chapter("vertical", 18, self._vertical)
        self._clear_formulas()
        self._direct_chapter("recombine", self._recombine)
        self._direct_chapter("landing", self._landing)
        self._legacy_chapter("horizontal", 58, self._horizontal)
        self._clear_formulas()
        self._direct_chapter("height_steps", self._height_steps)
        self._legacy_chapter("height", 74, self._height)
        self._clear_formulas()
        self._direct_chapter("transfer", self._transfer)
        self._clear_formulas()
        self._legacy_chapter("conclusion", 102, self._conclusion)
        self._event("complete", duration=float(self.get_time()))

    def tear_down(self):
        self._close_focus()
        for filename, report in (
            ("full-formula-motion.json", {"events": self.full_formula_events,
                                           "samples": self.full_formula_frames}),
            ("nonlinear-motion.json", {"samples": self.nonlinear_samples})):
            with (self.out / filename).open("x", encoding="utf-8") as stream:
                json.dump({"schema_version": 1, "duration": float(self.get_time()),
                    "cue_boundaries": [0] + [row["time"] for row in self.full_formula_events
                                               if row["kind"] == "chapter_end"],
                    "source_cue_boundaries": LEGACY_CUE_BOUNDARIES, **report,
                    "writer": "NonlinearLesson live native frame sampler",
                    "consumers": ["independent pixel reviewer", "regression reviewer", "lead"],
                    "lifecycle": "This exact scene execution; no reconstructed timestamps",
                    "invalidation": "Source, dependencies, timing, fonts, plan, contract or media change",
                    "limitations": "Native geometry is not rendered pixels, speech approval or independent review"},
                    stream, ensure_ascii=False)
        UnderstandingScene.tear_down(self)
