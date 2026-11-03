"""Supervised 114-second formula refinement; not a frozen-model submission.

Main supplies examples + src on PYTHONPATH and a fresh visual-first output.
The frozen candidate is loaded read-only for drawing/physics utilities. This
scene owns full-formula-motion.json; the portable landing owns its own log.
Both logs live with this render and expire on any source/timing/media change.
"""

import importlib.util
import json
import math

import numpy as np

from manimind.components.formula_motion import SemanticFormula, matching_transform
from manimind.postproduce import pilot
from manimlib import *

from projectile_formula_motion import _lane_path, play_landing_derivation


FROZEN_SOURCE = pilot.ROOT / "outputs/sol61-visual-first-20261024-v1/candidate.py"
_spec = importlib.util.spec_from_file_location("_frozen_projectile_utilities", FROZEN_SOURCE)
_frozen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_frozen)

CUE_BOUNDARIES = (0, 18, 38, 58, 74, 102, 114)


def vertical_steps():
    """Braced selectors distinguish the argument t, moving t and each 2."""
    initial = (r"\begin{aligned}y_1(t)&=y_{10}+v_{y10}{t}+\frac{{a_y}{t}^{2}}{{2}}\\"
               r"y_2(t)&=y_{20}+v_{y20}{t}+\frac{{a_y}{t}^{2}}{{2}}\end{aligned}")
    substituted = (r"\begin{aligned}y_1(t)&={h}+{0}{t}-\frac{{g}{t}^{2}}{{2}}\\"
                   r"y_2(t)&={h}+{0}{t}-\frac{{g}{t}^{2}}{{2}}\end{aligned}")
    laws = (r"\begin{aligned}y_1(t)&={h}-\frac{{g}{t}^{2}}{{2}}\\"
            r"y_2(t)&={h}-\frac{{g}{t}^{2}}{{2}}\end{aligned}")
    common = {"position1": "y_1(t)", "position2": "y_2(t)",
              "eq1": ("=", 0), "eq2": ("=", 1),
              "power1": ("^{2}", 0), "power2": ("^{2}", 1),
              "denominator1": ("{2}", 1), "denominator2": ("{2}", 3)}
    first = {**common, "height1": "y_{10}", "height2": "y_{20}",
             "velocity1": "v_{y10}", "velocity2": "v_{y20}",
             "linear_time1": ("{t}", 0), "linear_time2": ("{t}", 2),
             "time1": ("{t}", 1), "time2": ("{t}", 3),
             "gravity1": ("{a_y}", 0), "gravity2": ("{a_y}", 1)}
    second = {**first, "height1": ("{h}", 0), "height2": ("{h}", 1),
              "velocity1": ("{0}", 0), "velocity2": ("{0}", 1),
              "gravity1": ("{g}", 0), "gravity2": ("{g}", 1)}
    third = {key: value for key, value in second.items()
             if key not in {"velocity1", "velocity2", "linear_time1", "linear_time2"}}
    third.update(time1=("{t}", 0), time2=("{t}", 1))
    return [(initial, first), (substituted, second), (laws, third),
            (r"y_1(t)=y_2(t)", {"position1": "y_1(t)", "eq1": "=", "position2": "y_2(t)"})]


class FullFormulaLesson(_frozen.GeneratedLesson):
    def setup(self):
        super().setup()
        self.full_formula_frames = []
        self.full_formula_events = []
        self.full_active = {}
        self.full_flights = {}

    @staticmethod
    def _geometry(part):
        glyphs = part if isinstance(part, tuple) else part.family_members_with_points()
        arrays = [glyph.get_points() for glyph in glyphs if glyph.get_num_points()]
        if not arrays:
            return {"valid": False, "position": None, "bounds": None, "width": None, "height": None}
        points = np.vstack(arrays)
        low, high = points.min(axis=0), points.max(axis=0)
        bounds = (low, (low + high) / 2, high)
        return {"valid": True, "position": bounds[1].tolist(),
                "bounds": {"min": bounds[0].tolist(), "max": bounds[2].tolist()},
                "width": float(high[0] - low[0]), "height": float(high[1] - low[1])}

    def _snapshot(self, formula):
        return {"latex": formula.get_tex(), **self._geometry(formula),
                "tokens": {identity: self._geometry(formula.tag(identity))
                           for identity in formula.semantic_ids}}

    def update_mobjects(self, dt):
        super().update_mobjects(dt)
        if getattr(self, "full_active", None) or getattr(self, "full_flights", None):
            self.full_formula_frames.append({
                "time": float(self.get_time()),
                "formulas": {key: self._snapshot(value) for key, value in self.full_active.items()},
                "flights": {key: {**self._geometry(value["part"]), "source": value["source"],
                                  "target": value["target"]} for key, value in self.full_flights.items()}})

    def _event(self, kind, **data):
        self.full_formula_events.append({"time": float(self.get_time()), "kind": kind, **data})

    def _formula(self, latex, tokens, x, y, *, size=38, width=10.8, color=None):
        formula = SemanticFormula(latex, tokens=tokens, font_size=size)
        formula.set_color(color or self.WHITE)
        for identity in formula.semantic_ids:
            if any(word in identity for word in ("height", "time", "gravity", "root")):
                formula.tag(identity).set_color(self.MINT)
        if formula.get_width() > width:
            formula.scale(width / formula.get_width())
        return formula.move_to(self.p(x, y))

    def _adopt(self, name, formula, root):
        self.remove(formula)
        root.add(formula)
        self.add(root)
        self.full_active[name] = formula

    def _show(self, name, formula, root, duration=.4, *extra):
        self.full_active[name] = formula
        self._event("introduce", name=name, target=self._snapshot(formula))
        self.play(FadeIn(formula), *extra, run_time=duration)
        self._adopt(name, formula, root)

    def _morph(self, name, target, root, duration, operation, *, arc=0, extra=()):
        source = self.full_active[name]
        pairs = [(key, key) for key in source.semantic_ids if key in target.semantic_ids]
        self._event("matching_begin", name=name, operation=operation, pairs=pairs,
                    source=self._snapshot(source), target=self._snapshot(target))
        root.remove(source)
        self.add(source)
        animation = matching_transform(source, target, pairs=pairs, run_time=duration, path_arc=arc,
                                       unmatched_in_place=True)
        self.play(animation, *extra, run_time=duration)
        self._adopt(name, target, root)
        self._event("matching_end", name=name, operation=operation, actual=self._snapshot(target))

    def _merge(self, name, target, root, sources, duration, operation, *, consume=(), arc=0, paths=None):
        """Transport authored token groups, never guess glyph shapes or algebra.

        sources maps each target ID to (active formula, source ID or ID tuple).
        A tuple explicitly joins a known product, e.g. v_x and T into R. Kept
        equations donate copies; consumed equations donate their actual parts.
        """
        consume = set(consume)
        source_formulas = dict(self.full_active)
        animations, visible_targets, occupied = [], [], set()
        used = set()
        for key in consume:
            root.remove(source_formulas[key])
            self.add(source_formulas[key])
        for identity, (source_name, ids) in sources.items():
            ids = (ids,) if isinstance(ids, str) else ids
            formula = source_formulas[source_name]
            parts = [formula.tag(key) for key in ids]
            source = parts[0] if len(parts) == 1 else VGroup(*parts)
            glyph_ids = {id(glyph) for glyph in source.family_members_with_points()}
            if source_name in consume and used & glyph_ids:
                raise ValueError("A consumed semantic glyph cannot have two destinations")
            used.update(glyph_ids)
            destination = target.tag(identity)
            occupied.update(id(glyph) for glyph in destination.family_members_with_points())
            animation_type = ReplacementTransform if source_name in consume else TransformFromCopy
            route = {"path_func": paths[identity]} if paths and identity in paths else {"path_arc": arc}
            animation = animation_type(source, destination, **route)
            animations.append(animation)
            visible_targets.append(destination)
            self.full_flights[f"{name}.{identity}"] = {
                "part": tuple(animation.mobject.family_members_with_points()),
                "source": [source_name, *ids], "target": [name, identity]}
        for key in consume:
            leftover = VGroup(*(glyph for glyph in source_formulas[key].family_members_with_points()
                               if id(glyph) not in used))
            if len(leftover):
                animations.append(FadeOut(leftover))
        syntax = VGroup(*(glyph for glyph in target.family_members_with_points() if id(glyph) not in occupied))
        if len(syntax):
            animations.append(FadeIn(syntax))
            visible_targets.append(syntax)
        self._event("transport_begin", name=name, operation=operation, sources=sources,
                    consume=sorted(consume), target=self._snapshot(target))
        self.play(*animations, run_time=duration)
        for animation in animations:
            self.remove(animation.mobject)
        self.remove(*visible_targets)
        for key in consume:
            self.remove(source_formulas[key])
            self.full_active.pop(key)
        self.full_flights.clear()
        self._adopt(name, target, root)
        self._event("transport_end", name=name, operation=operation, actual=self._snapshot(target))

    def _expand_time_here(self, target, root):
        source = self.full_active["final_range"]
        for identity in ("range", "eq", "speed"):
            if np.linalg.norm(source.tag(identity).get_center() - target.tag(identity).get_center()) > 1e-4:
                raise ValueError("Reserve the radical slot without moving fixed range symbols")
        old_time, radical = source.tag("time"), target.tag("root")
        point = old_time.get_center().copy()
        self._event("local_expansion_begin", operation="Expand the substituted T in its reserved slot",
                    source=self._snapshot(source), target=self._snapshot(target))
        root.remove(source)
        self.add(source)
        self.play(FadeOut(old_time), run_time=.2)
        growth = GrowFromPoint(radical, point)
        self.full_flights["final_range.root"] = {
            "part": tuple(radical.family_members_with_points()),
            "source": ["final_range", "time"], "target": ["final_range", "root"]}
        self.play(growth, run_time=.4)
        self.remove(source, radical)
        self.full_flights.clear()
        self._adopt("final_range", target, root)
        self._event("local_expansion_end", actual=self._snapshot(target))

    def _clear_formulas(self):
        self.full_active.clear()
        self.full_flights.clear()

    def _opening(self):
        d = self.standard(1, "横速改变了什么？")
        gravity_reference = Group(
            Arrow(self.p(2.25, 1.55), self.p(2.25, .68), buff=0, fill_color=self.MINT, thickness=2.6),
            self.tex(r"g=10\,\mathrm{m/s^2}", 2.25, .29, 28, self.MINT, 2.2))
        d["root"].add(gravity_reference)
        self.page(d["root"], .9)
        self.mark("launch_conditions_visible")
        self.until(4.7)
        self.play(FadeOut(d["arrows"]), FadeOut(gravity_reference), run_time=.3)
        d["root"].remove(gravity_reference)
        self.state(d["clock"], "4倍慢放", self.MINT)
        self.run_standard(d, 0, .5, 2)
        self.mark("first_equal_height_visible")
        self.run_standard(d, .5, 1, 2)
        self.state(d["clock"], "暂停 · 已落地")
        self.flash(d["root"], [(self.pos(4, 0), self.BLUE), (self.pos(8, 0), self.ORANGE)], .5)
        self.mark("first_simultaneous_landing")
        common = Group(self.label("共同落地时间", 5.12, -.83, 25, self.MUTED),
                       self.tex(r"T=1.00\,\mathrm{s}", 5.12, -1.38, 38, self.MINT, 2.65))
        self.reveal(d["root"], common, .6)
        ranges = Group(self.range_bar(self.X0, self.X0 + 4, -2.10, self.BLUE, r"4\,\mathrm{m}", 33),
                       self.range_bar(self.X0, self.X0 + 8, -2.75, self.ORANGE, r"8\,\mathrm{m}", 33))
        self.reveal(d["root"], ranges, .9)
        self.mark("first_ranges_visible")
        self.until(14.2)
        self.play(Indicate(common, color=self.MINT, scale_factor=1.04), run_time=.8)
        self.until(18)

    def _vertical(self):
        d = self.standard(2, "竖直方向发生了什么？", with_height=False)
        root = d["root"]
        self.page(root, .6)
        self.until(19)
        self.play(FadeOut(d["arrows"]), run_time=.3)
        self.state(d["clock"], "4倍慢放", self.MINT)
        self.run_standard(d, 0, .5, 2)
        self.state(d["clock"], "暂停", self.MINT)
        grav = Group(
            Arrow(self.pos(2, 3.75) + .16 * DOWN, self.pos(2, 3.75) + 1.02 * DOWN,
                  buff=0, fill_color=self.MINT, thickness=3),
            Arrow(self.pos(4, 3.75) + .16 * DOWN, self.pos(4, 3.75) + 1.02 * DOWN,
                  buff=0, fill_color=self.MINT, thickness=3),
            self.tex("g", self.pos(2, 3.75)[0] + .3, -.04, 31, self.MINT),
            self.tex("g", self.pos(4, 3.75)[0] + .3, -.04, 31, self.MINT),
            self.tex("a_x=0", 5.12, -.88, 35), self.tex("a_y=-g", 5.12, -1.47, 35, self.MINT),
            self.tex("v_{y0}=0", 5.12, -2.06, 35))
        self.reveal(root, grav, .65)
        self.mark("equal_gravity_visible")
        projection = self.vertical_projection(d, .5)
        self.reveal(root, projection, .65)
        coords = Group(self.tex(r"x=2\,\mathrm{m}", -3.1, 1.17, 29, self.BLUE, 1.85),
                       self.tex(r"x=4\,\mathrm{m}", -1.1, 1.17, 29, self.ORANGE, 1.85),
                       self.tex(r"3.75\,\mathrm{m}", -6.08, .7, 28, self.MINT, 1.55))
        self.reveal(root, coords, .4)
        self.mark("vertical_projections_coincide")
        steps = vertical_steps()
        self.until(23.1)
        first = self._formula(*steps[0], 0, -2.44, size=31, width=10.2)
        # The right-hand initial-condition labels retire before the formula band.
        self.play(FadeOut(grav), run_time=.2)
        root.remove(grav)
        self._show("vertical", first, root, .4)
        self._morph("vertical", self._formula(*steps[1], 0, -2.44, size=31), root, .7,
                    "Both initial heights are h; both vertical speeds are zero; a_y=-g")
        self._morph("vertical", self._formula(*steps[2], 0, -2.44, size=34), root, .6,
                    "Remove the two zero initial-velocity terms")
        self.until(25.1)
        self.play(FadeOut(coords), run_time=.4)
        root.remove(coords)
        self.state(d["clock"], "重置 · t = 0")
        d["draw"](0)
        d["equal"].set_opacity(.23)
        self.until(26)
        root.add(self.time_tick("0", 5))
        self.state(d["clock"], "4倍慢放", self.MINT)
        self.run_standard(d, 0, .5, 2)
        root.add(self.time_tick("0.50", 3.75))
        self.run_standard(d, .5, 1, 2)
        root.add(self.time_tick("1.00", 0))
        self.state(d["clock"], "暂停 · 已落地")
        self._morph("vertical", self._formula(*steps[3], 1, -2.44, size=45), root, .7,
                    "The two explicitly identical right-hand sides give equal heights")
        self.mark("shared_vertical_motion_complete")
        self.until(33)
        self.play(Indicate(self.full_active["vertical"], color=self.MINT, scale_factor=1.04), run_time=.8)
        self.until(38)

    def _horizontal(self):
        d = self.standard(4, "同一段时间，横向走多远？")
        root = d["root"]
        common_t = self.tex(r"T=1.00\,\mathrm{s}", 5.12, -.69, 36, self.MINT, 2.65)
        root.add(common_t, self.horizontal_projection(d, 0))
        half_height = Group(
            Dot(self.pos(2, 3.75), radius=.045, fill_color=self.BLUE).set_opacity(.35),
            Circle(radius=.07, stroke_color=self.ORANGE, stroke_width=1.5,
                   fill_opacity=0).move_to(self.pos(4, 3.75)).set_opacity(.35),
            Line(self.pos(2, 3.75), self.pos(4, 3.75), stroke_color=self.MINT,
                 stroke_width=1).set_opacity(.22))
        root.add(half_height)
        # Bare x would also select the subscript in v_x; select a braced distance.
        x_law = self._formula("{x}=v_x{t}", {"distance": "{x}", "eq": "=", "speed": "v_x", "time": "{t}"},
                              5.12, -1.36, size=39, width=2.65)
        root.add(x_law)
        self.full_active["range"] = x_law
        self.page(root, .6)
        self.until(59)
        self.play(FadeOut(d["arrows"]), run_time=.2)
        self.state(d["clock"], "4倍慢放", self.MINT)
        self.run_standard(d, 0, 1, 4)
        self.state(d["clock"], "暂停 · 已落地")
        self.flash(root, [(self.pos(4, 0), self.BLUE), (self.pos(8, 0), self.ORANGE)], .4)
        self.mark("horizontal_projections_landed")
        range_law = self._formula("{R}=v_x{T}", {"distance": "{R}", "eq": "=", "speed": "v_x", "time": "{T}"},
                                  5.12, -1.36, size=39, width=2.65)
        self._morph("range", range_law, root, .6, "At landing x becomes R and t becomes T; v_x is unchanged")
        bars = VGroup()
        for length, y, color in ((4, -1.98, self.BLUE), (8, -2.80, self.ORANGE)):
            bars.add(Line(self.p(self.X0, y), self.p(self.X0 + length, y), stroke_color=color, stroke_width=2.4),
                     Line(self.p(self.X0, y - .08), self.p(self.X0, y + .08), stroke_color=color, stroke_width=2.4),
                     Line(self.p(self.X0 + length, y - .08), self.p(self.X0 + length, y + .08),
                          stroke_color=color, stroke_width=2.4))
        copies = []
        for name, digit, center, y, color, width in (("range1", "4", -3.1, -2.23, self.BLUE, 4.1),
                                                   ("range2", "8", -1.1, -3.05, self.ORANGE, 6.0)):
            source = range_law.copy()
            self.full_active[name] = source
            target = self._formula(r"R_" + name[-1] + "={" + digit + r"}\,\mathrm{m/s}\times{1}\,\mathrm{s}",
                                   {"distance": "R_" + name[-1], "eq": "=", "speed": "{" + digit + "}", "time": "{1}"},
                                   center, y, size=30, width=width, color=color)
            self.add(source)
            copies.append((name, source, target))
        self._event("substitute_products_begin", operation="T=1 s and the two measured speeds 4/8 m/s")
        for index, (name, source, target) in enumerate(copies):
            extra = [FadeIn(bars)] if index == 0 else []
            self.play(matching_transform(source, target, unmatched_in_place=True), *extra, run_time=.4)
            self._adopt(name, target, root)
        self.remove(bars)
        root.add(bars)
        self._event("substitute_products_end", formulas={name: self._snapshot(target) for name, _, target in copies})
        self.mark("range_products_visible")
        for name, digit, center, y, color, width in (("range1", "4", -3.1, -2.23, self.BLUE, 4.1),
                                                   ("range2", "8", -1.1, -3.05, self.ORANGE, 6.0)):
            target = self._formula("R_" + name[-1] + "={" + digit + r"}\,\mathrm{m}",
                                   {"distance": "R_" + name[-1], "eq": "=", "speed": "{" + digit + "}"},
                                   center, y, size=32, width=width, color=color)
            self._morph(name, target, root, .3, "Multiply by one second; cancel the seconds")
        ruler_y = -2.62
        ruler = VGroup(Line(self.p(self.X0, ruler_y), self.p(self.X0 + 4, ruler_y),
                            stroke_color=self.MINT, stroke_width=6),
                       *[Line(self.p(self.X0 + k, ruler_y - .09), self.p(self.X0 + k, ruler_y + .09),
                              stroke_color=self.MINT, stroke_width=2.4) for k in range(5)])
        ruler_label = self.label("4 m 标尺", 5.12, -2.03, 27, self.MINT, 2.6)
        ratio = self._formula(r"v_{x2}={2}v_{x1}", {"second": "v_{x2}", "eq": "=", "factor": "{2}", "first": "v_{x1}"},
                              5.12, -2.82, size=29, width=2.8)
        self.until(66)
        self._show("range_ratio", ratio, root, .6, FadeIn(ruler), FadeIn(ruler_label))
        root.add(ruler, ruler_label)
        self.until(67.3)
        root.add(ruler.copy().set_opacity(.3))
        self.play(ruler.animate.shift(4 * RIGHT), run_time=1.1)
        double = self._formula(r"R_2={2}R_1", {"second": "R_2", "eq": "=", "factor": "{2}", "first": "R_1"},
                               5.12, -2.82, size=32, width=2.8)
        self._morph("range_ratio", double, root, .6, "The common T preserves the speed ratio in the ranges")
        self.mark("double_range_measured")
        self.until(74)

    def _height(self):
        # The original experiment runs unchanged through its 90.4-second result.
        low_x, high_x = -5.50, .80
        scale_x, scale_y, ground_y = .50, .17, -1.55

        def low_pos(x, y):
            return self.p(low_x + scale_x * x, ground_y + scale_y * y)

        def high_pos(x, y):
            return self.p(high_x + scale_x * x, ground_y + scale_y * y)

        panels = Group(self.plate(6.2, 5.7, -3.25, -.42), self.plate(6.2, 5.7, 3.25, -.42))
        chart_axes = Group()
        for mapper, origin in ((low_pos, low_x), (high_pos, high_x)):
            chart_axes.add(Line(self.p(origin - .3, ground_y), self.p(origin + 4.75, ground_y),
                                stroke_color=self.MUTED, stroke_width=2),
                           Arrow(mapper(0, 0), mapper(0, 21), buff=0, fill_color=self.MUTED, thickness=1.6),
                           Arrow(mapper(0, 0), mapper(9.25, 0), buff=0, fill_color=self.MUTED, thickness=1.6),
                           self.tex(r"x/\mathrm{m}", origin + 4.52, -1.87, 23, self.MUTED))
            for yy in (0, 5, 10, 15, 20):
                q = mapper(0, yy)
                chart_axes.add(Line(q + .055 * LEFT, q + .055 * RIGHT, stroke_color=self.MUTED, stroke_width=1.2),
                               self.tex(str(yy), origin - .32, q[1], 22, self.MUTED, .28))
                if yy > 0:
                    chart_axes.add(Line(mapper(0, yy), mapper(8.7, yy), stroke_color=self.GRID,
                                        stroke_width=.8).set_opacity(.35))
            for xx in (4, 8):
                q = mapper(xx, 0)
                chart_axes.add(Line(q + .06 * DOWN, q + .06 * UP, stroke_color=self.MUTED, stroke_width=1.2),
                               self.tex(str(xx), q[0], ground_y - .25, 23, self.MUTED))
        low_h = self.height_brace(low_x - .57, ground_y, low_pos(0, 5)[1], r"5\,\mathrm{m}", self.BLUE, low_x - .84, 25)
        high_h = self.height_brace(high_x - .57, ground_y, high_pos(0, 20)[1], r"20\,\mathrm{m}", self.ORANGE, high_x - .91, 25)
        lpath = self.curve(low_pos, 4, 5, 0, self.BLUE, 2.5, .75)
        hpath = self.curve(high_pos, 4, 20, 0, self.ORANGE, 2.5, .75)
        lb = Dot(low_pos(0, 5), radius=.1, fill_color=self.BLUE)
        hb = Circle(radius=.14, stroke_color=self.ORANGE, stroke_width=3, fill_opacity=0).move_to(high_pos(0, 20))
        clock = self.clock(5.16, 1.49, "预测 · 待释放")
        prediction = self.tex(r"h\times4\qquad T\,?\qquad R\,?", 0, -2.94, 40, self.MINT, 8.7)
        evidence = Group(chart_axes, low_h, high_h, lpath, hpath, lb, hb,
                         self.label("蓝组 · h = 5 m", -3.35, 2.13, 31, self.BLUE, 3.8),
                         self.label("橙组 · h = 20 m", 2.36, 2.13, 31, self.ORANGE, 3.3))
        fixed_speed = self.tex(r"v_x=4\,\mathrm{m/s}", -3.62, 2.65, 33, width=3)
        same_scales = self.label("两组相同 · 坐标同尺度", .15, 2.65, 26, self.MUTED, 3.75)
        root = Group(self.heading(5, "高度变为四倍，会怎样？"), panels, evidence,
                     fixed_speed, same_scales, clock["root"], prediction)

        def height_draw(t):
            lt, ht = min(float(t), 1), min(float(t), 2)
            lb.move_to(low_pos(4 * lt, max(0., 5 - 5 * lt * lt)))
            hb.move_to(high_pos(4 * ht, max(0., 20 - 5 * ht * ht)))
            self.update_curve(lpath, low_pos, 4, 5, lt)
            self.update_curve(hpath, high_pos, 4, 20, ht)
            clock["number"].set_value(t)

        def height_run(a, b, duration):
            self.play(UpdateFromAlphaFunc(root, lambda m, u: height_draw(a + (b - a) * u)),
                      run_time=duration, rate_func=linear)

        self.page(root, .7)
        self.wait(.3)
        self.mark("height_prediction_ready")
        self.until(78.2)
        self.play(FadeOut(prediction), run_time=.3)
        root.remove(prediction)
        self.state(clock, "4倍慢放", self.MINT)
        height_run(0, 1, 4)
        self.state(clock, "暂停", self.MINT)
        high_dash = self.dash_group(self.ORANGE, 17)
        self.update_dashes(high_dash, high_pos(4, 0), high_pos(4, 15))
        coord_pack = Group(high_dash,
                           self.tex(r"x=4\,\mathrm{m}", low_pos(4, 0)[0], -1.99, 29, self.BLUE, 2),
                           self.tex(r"x=4\,\mathrm{m}", high_pos(4, 0)[0], -1.99, 29, self.ORANGE, 2),
                           self.tex(r"y=15\,\mathrm{m}", 3.85, .46, 29, self.ORANGE, 2),
                           Line(high_pos(4, 15) + self.p(.12, -.1), self.p(3.12, .65),
                                stroke_color=self.ORANGE, stroke_width=1.3))
        low_time = self.tex(r"T=1.00\,\mathrm{s}", -3.22, -2.72, 34, self.BLUE, 3.1)
        root.add(coord_pack, low_time)
        self.play(FadeIn(coord_pack), FadeIn(low_time), run_time=.5)
        self.mark("low_ball_landed_high_ball_flying")
        self.until(85)
        self.play(FadeOut(coord_pack), run_time=.3)
        root.remove(coord_pack)
        self.state(clock, "4倍慢放", self.MINT)
        height_run(1, 2, 4)
        self.state(clock, "暂停 · 两组已落地")
        self.flash(root, [(high_pos(8, 0), self.ORANGE)], .4)
        high_time = self.tex(r"T=2.00\,\mathrm{s}", 3.20, -2.72, 34, self.ORANGE, 3.1)
        low_range = self.range_bar(low_x, low_x + 2, -2.07, self.BLUE, r"R=4\,\mathrm{m}", 28)
        high_range = self.range_bar(high_x, high_x + 4, -2.07, self.ORANGE, r"R=8\,\mathrm{m}", 28)
        result = Group(high_time, low_range, high_range)
        self.reveal(root, result, .7)
        self.mark("high_ball_landed")
        root.remove(low_time, result)
        evidence.add(low_time, high_time, low_range, high_range)
        self.play(evidence.animate.scale(.52).move_to(self.p(-3.4, .15)),
                  FadeOut(panels), FadeOut(clock["root"]), FadeOut(fixed_speed), FadeOut(same_scales), run_time=.6)
        root.remove(panels, clock["root"], fixed_speed, same_scales)
        self._height_algebra(root)
        self.until(102)

    def _height_algebra(self, root):
        if self.get_time() < 90.4 - 1e-6:
            raise ValueError("Do not reveal height scaling before both experimental results")
        change = self._formula("h'={4}{h}", {"new_height": "h'", "eq": "=", "scale": "{4}", "height": "{h}"},
                               3.1, 1.85, size=38, width=5.8)
        t0 = self._formula(r"T'=\sqrt{\frac{{2}{h}'}{{g}}}",
                           {"new_time": "T'", "eq": "=", "base2": "{2}", "new_height": "{h}'", "gravity": "{g}"},
                           3.1, .45, size=40, width=5.8)
        r0 = self._formula("R'=v_xT'", {"new_range": "R'", "eq": "=", "speed": "v_x", "new_time": "T'"},
                           3.1, -1.3, size=40, width=5.8)
        self.full_active.update(height_change=change, height_time=t0, height_range=r0)
        self.play(FadeIn(change), FadeIn(t0), FadeIn(r0), run_time=.4)
        for name, formula in (("height_change", change), ("height_time", t0), ("height_range", r0)):
            self._adopt(name, formula, root)
        t1 = self._formula(r"T'=\sqrt{\frac{{2}\cdot{4}{h}}{{g}}}",
                           {"new_time": "T'", "eq": "=", "base2": "{2}", "scale": "{4}", "height": "{h}", "gravity": "{g}"},
                           3.1, .45, size=40, width=5.8)
        self._merge("height_time", t1, root,
                    {"new_time": ("height_time", "new_time"), "eq": ("height_time", "eq"),
                     "base2": ("height_time", "base2"), "scale": ("height_change", "scale"),
                     "height": ("height_change", "height"), "gravity": ("height_time", "gravity")},
                    .7, "Substitute the observed h'=4h into the landing-time law", consume=("height_time",))
        t2 = self._formula(r"T'=\sqrt{{4}}\sqrt{\frac{{2}{h}}{{g}}}",
                           {"new_time": "T'", "eq": "=", "scale": "{4}", "base2": "{2}", "height": "{h}", "gravity": "{g}"},
                           3.1, .45, size=40, width=5.8)
        self._morph("height_time", t2, root, .7, "For positive h and g, split off sqrt(4)", arc=-math.pi / 3)
        t3 = self._formula(r"T'={2}\sqrt{\frac{{2}{h}}{{g}}}",
                           {"new_time": "T'", "eq": "=", "scale": ("{2}", 0), "base2": ("{2}", 1),
                            "height": "{h}", "gravity": "{g}"}, 3.1, .45, size=40, width=5.8)
        self._morph("height_time", t3, root, .6, "sqrt(4)=2; do not confuse it with the original numerator 2")
        t4 = self._formula("T'={2}{T}", {"new_time": "T'", "eq": "=", "scale": "{2}", "time": "{T}"},
                           3.1, .45, size=43, width=5.8)
        self._merge("height_time", t4, root,
                    {"new_time": ("height_time", "new_time"), "eq": ("height_time", "eq"),
                     "scale": ("height_time", "scale"), "time": ("height_time", ("base2", "height", "gravity"))},
                    .6, "The original sqrt(2h/g) is T", consume=("height_time",))
        r1 = self._formula("R'=v_x({2}{T})", {"new_range": "R'", "eq": "=", "speed": "v_x", "scale": "{2}", "time": "{T}"},
                           3.1, -1.3, size=40, width=5.8)
        self._merge("height_range", r1, root,
                    {"new_range": ("height_range", "new_range"), "eq": ("height_range", "eq"),
                     "speed": ("height_range", "speed"), "scale": ("height_time", "scale"), "time": ("height_time", "time")},
                    .6, "Substitute the derived T'=2T while retaining the same v_x", consume=("height_range",))
        r2 = self._formula("R'={2}v_x{T}", {"new_range": "R'", "eq": "=", "scale": "{2}", "speed": "v_x", "time": "{T}"},
                           3.1, -1.3, size=40, width=5.8)
        self._morph("height_range", r2, root, .6, "Move the scalar 2 outside the unchanged speed-time product", arc=-math.pi / 3)
        r3 = self._formula("R'={2}{R}", {"new_range": "R'", "eq": "=", "scale": "{2}", "range": "{R}"},
                           3.1, -1.3, size=43, width=5.8)
        self._merge("height_range", r3, root,
                    {"new_range": ("height_range", "new_range"), "eq": ("height_range", "eq"),
                     "scale": ("height_range", "scale"), "range": ("height_range", ("speed", "time"))},
                    .6, "The unchanged product v_x T is the original R", consume=("height_range",))
        self.until(96)
        self.mark("height_scaling_verified")

    def _conclusion(self):
        def thumb1(x, y):
            return self.p(-6.06 + .42 * x, .30 + .235 * y)

        thumb_fixed = Group(
            self.plate(4.88, 2.73, -4.18, 1.21),
            self.label("同高度 · 横速 ×2", -4.18, 2.19, 28, width=4.3),
            self.tex(r"T=1\,\mathrm{s}", -3.18, 1.72, 28, self.MINT, 1.7),
            Line(self.p(-6.18, .3), self.p(-2.28, .3), stroke_color=self.MUTED, stroke_width=1.6),
            self.curve(thumb1, 4, 5, 1, self.BLUE, 2.2, 1), self.curve(thumb1, 8, 5, 1, self.ORANGE, 2.2, 1),
            Dot(thumb1(4, 0), radius=.065, fill_color=self.BLUE),
            Circle(radius=.095, stroke_color=self.ORANGE, stroke_width=2.1, fill_opacity=0).move_to(thumb1(8, 0)),
            self.tex(r"4\,\mathrm{m}", thumb1(4, 0)[0], .03, 26, self.BLUE),
            self.tex(r"8\,\mathrm{m}", thumb1(8, 0)[0], .03, 26, self.ORANGE),
            Line(thumb1(2, 3.75), thumb1(4, 3.75), stroke_color=self.MINT, stroke_width=1.1).set_opacity(.65))

        def thumb2(x, y):
            return self.p(-5.96 + .32 * x, -2.76 + .081 * y)

        thumb_height = Group(
            self.plate(4.88, 2.85, -4.18, -1.82), self.label("同横速 · 高度 ×4", -4.18, -.71, 28, width=4.3),
            Line(self.p(-6.08, -2.76), self.p(-2.37, -2.76), stroke_color=self.MUTED, stroke_width=1.6),
            self.curve(thumb2, 4, 5, 1, self.BLUE, 2.2, 1), self.curve(thumb2, 4, 20, 2, self.ORANGE, 2.2, 1),
            Dot(thumb2(4, 0), radius=.065, fill_color=self.BLUE),
            Circle(radius=.095, stroke_color=self.ORANGE, stroke_width=2.1, fill_opacity=0).move_to(thumb2(8, 0)),
            self.tex(r"5\,\mathrm{m}", -6.23, thumb2(0, 5)[1], 22, self.BLUE, .65),
            self.tex(r"20\,\mathrm{m}", -6.20, thumb2(0, 20)[1], 22, self.ORANGE, .75),
            self.tex(r"T\times2", -2.8, -1.55, 29, self.MINT, 1.35),
            self.tex(r"R\times2", -2.8, -2.18, 29, self.MINT, 1.35),
            self.tex(r"4\,\mathrm{m}", thumb2(4, 0)[0], -3.04, 25, self.BLUE),
            self.tex(r"8\,\mathrm{m}", thumb2(8, 0)[0], -3.04, 25, self.ORANGE))

        def node(symbol, caption, x, y, color):
            return Group(self.plate(1.19, .89, x, y, border=color), self.tex(symbol, x, y + .01, 43, color),
                         self.label(caption, x, y - .79, 27, self.MUTED, 2.3))

        hn, tn = node("h", "高度", -.53, .93, self.MINT), node("T", "飞行时间", 2.13, .93, self.MINT)
        rn, vn = node("R", "射程", 5.32, .93, self.WHITE), node("v_x", "横向初速度", 2.13, -1.43, self.BLUE)
        ht = Arrow(self.p(.14, .93), self.p(1.47, .93), buff=0, fill_color=self.MINT, thickness=2.8)
        tr = Arrow(self.p(2.8, .93), self.p(4.64, .93), buff=0, fill_color=self.MINT, thickness=2.8)
        vr = Arrow(self.p(2.8, -1.43), self.p(4.91, .36), buff=0, fill_color=self.BLUE, thickness=2.8)
        root_term = r"\sqrt{\frac{{2}{h}}{{g}}}"
        tf = self._formula("T=" + root_term, {"time": "T", "eq": "=", "root": root_term},
                           .65, 1.99, size=34, width=2.8)
        substituted = self._formula("R=v_x" + root_term,
                                    {"range": "R", "eq": "=", "speed": "v_x", "root": root_term},
                                    4.35, 1.99, size=35, width=4.05)
        rf = self._formula("R=v_xT", {"range": "R", "eq": "=", "speed": "v_x", "time": "T"},
                           4.2, 1.99, size=35, width=2.8)
        # Reserve the final root's space now, so R, = and v_x never move later.
        rf.scale(substituted.tag("speed").get_width() / rf.tag("speed").get_width())
        rf.shift(substituted.tag("speed").get_center() - rf.tag("speed").get_center())
        root = Group(self.heading(6, "把关系连起来"), self.label("g 固定", -.51, 2.59, 28, self.MUTED, 2))
        self.page(root, .6)
        self.reveal(root, thumb_fixed, .6)
        self.reveal(root, Group(tn, tf), .6)
        self.full_active["final_time"] = tf
        self.reveal(root, Group(vn, rn, tr, vr, rf), .7)
        self.full_active["final_range"] = rf
        # Keep the formula directly owned by the page for semantic replacements.
        for group in list(root.submobjects):
            if group is not tf and tf in group.submobjects:
                group.remove(tf)
            if group is not rf and rf in group.submobjects:
                group.remove(rf)
        root.add(tf, rf)
        self.mark("fixed_height_relation_highlighted")
        self.until(105.2)
        self.reveal(root, thumb_height, .5)
        self.reveal(root, Group(hn, ht), .6)
        self.play(Indicate(hn[1], color=self.MINT, scale_factor=1.1), run_time=.6)
        self.play(Indicate(tn[1], color=self.MINT, scale_factor=1.1), run_time=.5)
        self.play(Indicate(rn[1], color=self.MINT, scale_factor=1.1), run_time=.5)
        self.mark("height_relation_highlighted")
        self.until(108.5)
        self.play(Indicate(tf.tag("time"), color=self.MINT, scale_factor=1.15),
                  Indicate(rf.tag("time"), color=self.MINT, scale_factor=1.15), run_time=.2)
        self._event("time_correspondence", source=["final_time", "time"], target=["final_range", "time"])
        carry_path = _lane_path(tf.tag("time").get_center(), rf.tag("time").get_center(), 2.78,
                                (.1, .2, .1), lambda _: None)
        self._merge("final_range", rf.copy(), root,
                    {"range": ("final_range", "range"), "eq": ("final_range", "eq"),
                     "speed": ("final_range", "speed"), "time": ("final_time", "time")},
                    .4, "Lift the small T, cross above the equations, then settle in the reserved time slot",
                    consume=("final_range",), paths={"time": carry_path})
        self._expand_time_here(substituted, root)
        self.until(110)
        self.mark("final_relations_visible")
        self.until(114)

    def construct(self):
        self.current_page = None
        background = Rectangle(width=14.3, height=8.1, fill_color=self.BG, fill_opacity=1, stroke_width=0)
        footer = Group(Line(self.p(-6.65, -3.42), self.p(6.65, -3.42), stroke_color=self.GRID, stroke_width=1),
                       self.label("质点 · 均匀重力场 · 无空气阻力", -3.35, -3.7, 25, self.MUTED, 6.5),
                       self.tex(r"v_{y0}=0,\quad g=10\,\mathrm{m/s^2}", 3.35, -3.7, 28, self.MUTED, 5.5))
        self.add(background, footer)
        self._opening()
        self._vertical()
        self._clear_formulas()
        landing_page = play_landing_derivation(self, start=38, previous_page=self.current_page)
        if landing_page is not None:
            self.current_page = landing_page
        self.until(58)
        self._horizontal()
        self._clear_formulas()
        self._height()
        self._clear_formulas()
        self._conclusion()
        self._event("complete", duration=float(self.get_time()))

    def tear_down(self):
        (self.out / "full-formula-motion.json").write_text(json.dumps({
            "schema_version": 1, "duration": float(self.get_time()), "cue_boundaries": CUE_BOUNDARIES,
            "events": self.full_formula_events, "samples": self.full_formula_frames,
            "writer": "FullFormulaLesson actual render, supervised derivative",
            "consumers": ["independent formula/pixel reviewer", "full-film release gate"],
            "lifecycle": "This full render only; portable landing has a separate motion-samples.json",
            "invalidation": "Any change to scene, helper, frozen utilities, timeline, TeX or render",
            "limitations": "Native semantic geometry is not pixel review, listening review or final approval"
        }), encoding="utf-8")
        super().tear_down()
