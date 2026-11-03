"""Author candidate: chapter 02 source-to-target algebra over the intact clock.

The scene owns formula identities and transition traces for one render. Authors
and independent reviewers consume them; source, timing or geometry changes
invalidate them. Traces are not pixel approval or narration authorization.
"""

import math

from manimlib import FadeIn, FadeOut, Group, Transform, ValueTracker, linear
from manimind.components.formula_motion import SemanticFormula
from derivative_ch02_basics_v005 import DerivativeBasicsLessonV005
from derivative_chapter_shared import INK, MUTED, CURVE, RATE, ACCENT


AUTHOR = "01a19f5e-8733-71c0-ac2d-d507423acd13"


class TraceableSteps:
    def at(self, local, *animations, **kwargs):
        self.until(self._cue["start"] + local, *animations, **kwargs)

    def tf(self, latex, tokens, y, x=0, size=37, width=12.0, colors=None):
        obj = SemanticFormula(latex, tokens=tokens, font_size=size, colors=colors)
        obj.set_color(INK)
        for key, color in (colors or {}).items():
            obj.tag(key).set_color(color)
        if obj.get_width() > width:
            obj.set_width(width)
        return obj.move_to([x, y, 0])

    def reveal(self, obj, start, end):
        self.at(start)
        self.at(end, FadeIn(obj))
        return obj

    def transfer(self, identity, source, target, pairs, start, end, *, retain=False, arc=0, serial=False):
        self.at(start)
        pairs = list(pairs)
        moving = {a: source.tag(a).copy() for a, _ in pairs}
        destinations = {a: target.tag(b) for a, b in pairs}
        used = {id(g) for part in destinations.values() for g in part.family_members_with_points()}
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        phase = "source"
        driver = Group()

        def sample(_):
            self.sample("traceable_formula", transition=identity, cue=self._cue["id"],
                        retained=retain, phase=phase, source_tex=source.get_tex(),
                        target_tex=target.get_tex(),
                        moving={a: part.get_center().tolist() for a, part in moving.items()},
                        target={b: target.tag(b).get_center().tolist() for _, b in pairs},
                        glyph_counts={a: len(part.family_members_with_points()) for a, part in moving.items()})

        sample(driver)
        self.add(driver, *moving.values())
        driver.add_updater(sample)
        if not retain:
            phase = "clear_old_syntax"
            self.at(start + .2, FadeOut(source))
        phase = "travel_unchanged"
        # Move readable source shapes first. Algebra changes only after arrival.
        arrivals = []
        for key, part in moving.items():
            destination = destinations[key]
            placed = part.copy()
            scale = min(1., destination.get_width() / max(placed.get_width(), 1e-8))
            placed.scale(scale).move_to(destination.get_center())
            arrivals.append(Transform(part, placed, path_arc=arc))
        if serial:
            first = self.time - self._cue["start"]
            span = (end - .6 - first) / len(arrivals)
            for index, animation in enumerate(arrivals):
                self.at(first + (index + 1) * span, animation, rate_func=linear)
        else:
            self.at(end - .6, *arrivals, rate_func=linear)
        phase = "resolve_operation"
        self.at(end - .25, *(Transform(part, destinations[key].copy()) for key, part in moving.items()))
        phase = "new_syntax"
        self.at(end, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *moving.values())
        self.add(target)
        self.sample("traceable_complete", transition=identity, cue=self._cue["id"],
                    source_tex=source.get_tex(), target_tex=target.get_tex())
        return target

    def gather(self, identity, target, tracks, start, end, *, arc=0, retire=()):
        """Explicit multi-source slots; each copy starts at its visible source."""
        self.at(start)
        moving, destinations, used = [], [], set()
        for source, source_id, target_id in tracks:
            part = source.tag(source_id).copy()
            destination = target.tag(target_id)
            moving.append(part)
            destinations.append(destination)
            used.update(id(g) for g in destination.family_members_with_points())
        syntax = Group(*(g for g in target.family_members_with_points() if id(g) not in used))
        driver = Group()
        phase, active = "source", None

        def sample(_):
            self.sample("traceable_gather", transition=identity, cue=self._cue["id"],
                        phase=phase, active_role=active,
                        moving=[part.get_center().tolist() for part in moving],
                        target=[target.tag(t[2]).get_center().tolist() for t in tracks],
                        roles=[(t[1], t[2]) for t in tracks])

        sample(driver)
        driver.add_updater(sample)
        self.add(driver)
        if retire:
            self.at(start + .25, *(FadeOut(obj) for obj in retire))
        # One role travels at a time, so copies cannot cross each other in flight.
        first = self.time - self._cue["start"]
        span = (end - .25 - first) / len(moving)
        for index, (part, destination) in enumerate(zip(moving, destinations)):
            active, phase = tracks[index][2], "travel_unchanged"
            self.add(part)
            placed = part.copy()
            scale = min(1., destination.get_width() / max(placed.get_width(), 1e-8))
            placed.scale(scale).move_to(destination.get_center())
            arrival = first + (index + 1) * span
            self.at(arrival - .15, Transform(part, placed, path_arc=arc), rate_func=linear)
            phase = "resolve_operation"
            self.at(arrival, Transform(part, destination.copy()))
        phase, active = "new_syntax", None
        self.at(end, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *moving)
        self.add(target)
        self.sample("traceable_complete", transition=identity, cue=self._cue["id"],
                    target_tex=target.get_tex())
        return target

    def drop(self, local, *objects):
        self.at(local, *(FadeOut(obj) for obj in objects))


class DerivativeCh02Traceable(TraceableSteps, DerivativeBasicsLessonV005):
    def general(self):
        first = self.tf(r"\frac{(a+h)^2-a^2}{h}",
                        {"square": "(a+h)^2", "old": "a^2", "den": ("h", 1)}, 2.2)
        expanded = self.tf(r"\frac{a^2+2ah+h^2-a^2}{h}",
            {"square": "a^2+2ah+h^2", "old": ("a^2", 1), "den": ("h", 2)}, .8)
        reduced = self.tf(r"\frac{2ah+h^2}{h}",
                         {"body": "2ah+h^2", "den": ("h", 2)}, .8)
        self.reveal(first, 1.94, 2.34)
        condition = self.put(r"h\ne0", 4.6, 2.2, size=29)
        self.add(condition)
        self.ready("general_quotient")
        self.transfer("square_expand", first, expanded,
                      [("square", "square"), ("old", "old"), ("den", "den")], 7.0, 9.8, retain=True)
        cancellation = self.tf(r"\frac{a^2+2ah+h^2-a^2}{h}",
            {"keep": "2ah+h^2", "den": ("h", 2)}, .8)
        self.remove(expanded)
        self.add(cancellation)
        self.transfer("square_cancel_squares", cancellation, reduced,
                      [("keep", "body"), ("den", "den")], 10.0, 12.5)
        self.at(13.96)
        self.ready("general_limit")
        factored = self.tf(r"\frac{h(2a+h)}{h}",
                           {"body": "2a+h", "top_h": ("h", 0), "den": ("h", 2)}, -.55)
        self.transfer("square_factor_h", reduced, factored, [("body", "body"), ("den", "den")],
                      14.5, 16.5, retain=True)
        quotient = self.tf(r"2a+h", {"body": "2a+h"}, -.55)
        self.transfer("square_divide_h", factored, quotient, [("body", "body")], 16.8, 18.8)
        limit_source = self.tf(quotient.get_tex(), {"main": "2a", "small": "h"}, -.55)
        self.remove(quotient)
        self.add(limit_source)
        limit = self.tf(r"2a\quad(h\to0)", {"main": "2a"}, -.55)
        self.transfer("square_limit", limit_source, limit, [("main", "main")], 20.0, 22.4)
        deriv_a = self.tf(r"f'(a)=2a", {"value": "2a"}, -1.85)
        self.transfer("square_name_derivative", limit, deriv_a, [("main", "value")],
                      22.65, 24.36, retain=True)
        self.ready("general_function")
        rename_source = self.tf(deriv_a.get_tex(), {"arg": ("a", 0), "value": ("a", 1)}, -1.85)
        self.remove(deriv_a)
        self.add(rename_source)
        deriv_x = self.tf(r"f'(x)=2x", {"arg": ("x", 0), "value": ("x", 1)}, -1.85, x=3.2)
        self.transfer("rename_input", rename_source, deriv_x, [("arg", "arg"), ("value", "value")],
                      27.2, 30.0, retain=True)
        self.beat(.52)
        for key in ("general_quotient", "general_limit", "general_function"):
            self.focus_end(key)
        old = [m for m in self.mobjects if m is not self._subtitle_driver]
        self.beat(.57, *(FadeOut(m) for m in old))
        group, a = self.pair("square", (-2.4, 2.4), (-.5, 6), (-5, 5), -2)
        self.beat(.62, FadeIn(group), FadeIn(self.sf(r"x^2\quad\longmapsto\quad 2x", 2.8)))
        self.ready("general_map")
        self.beat(.76, a.animate.set_value(0), rate_func=linear)
        self.beat(.91, a.animate.set_value(2), rate_func=linear)
        self.focus_end("general_map")
        self.beat(.96, FadeIn(self.label("切线斜率成为右图的高度", 0, -2.72, size=28)))
        self.ready("general_map_result")

    def identity(self):
        initial = self.tf(r"\frac{(x+h)-x}{h}\quad(h\ne0)",
                          {"positive": ("x", 0), "negative": ("x", 1), "inc": ("h", 0)}, 2.15)
        self.reveal(initial, 2.1, 2.5)
        self.ready("identity_quotient")
        reduced = self.tf(r"\frac hh=1\quad(h\ne0)", {"inc": ("h", 0)}, 2.15)
        self.transfer("identity_cancel", initial, reduced, [("inc", "inc")], 5.0, 8.0)
        self.beat(.27)
        self.focus_end("identity_quotient")
        self.beat(.31, FadeOut(reduced))
        graph, a = self.pair("identity", (-2.4, 2.4), (-2.5, 2.5), (0, 2), -2)
        self.beat(.39, FadeIn(graph), FadeIn(self.sf(r"(x)'=1\qquad x\in\mathbb R", 2.65)))
        self.ready("identity_map")
        self.beat(.88, a.animate.set_value(2), rate_func=linear)
        self.focus_end("identity_map")

    def power(self):
        first = self.tf(r"\frac{(x+h)^3-x^3}{h}\quad(h\ne0)",
                        {"cube": "(x+h)^3", "old": "x^3", "den": ("h", 1)}, 2.25, size=34)
        expanded = self.tf(r"\frac{x^3+3x^2h+3xh^2+h^3-x^3}{h}",
            {"cube": "x^3+3x^2h+3xh^2+h^3", "old": ("x^3", 1), "den": ("h", 3)}, 1.05, size=33)
        self.reveal(first, 2.1, 2.5)
        self.ready("power_cubic_expansion")
        self.transfer("cubic_expand", first, expanded,
                      [("cube", "cube"), ("old", "old"), ("den", "den")], 5.0, 8.0, retain=True)
        source = self.tf(r"\frac{x^3+3x^2h+3xh^2+h^3-x^3}{h}",
                        {"a": "3x^2h", "b": "3xh^2", "c": "h^3", "den": ("h", 3)}, 1.05, size=33)
        reduced = self.tf(r"\frac{3x^2h+3xh^2+h^3}{h}",
                         {"a": "3x^2h", "b": "3xh^2", "c": "h^3", "den": ("h", 3)}, 1.05, size=35)
        self.remove(expanded)
        self.add(source)
        self.transfer("cubic_cancel_cubes", source, reduced,
                      [(k, k) for k in ("a", "b", "c", "den")], 8.8, 11.5)
        self.at(17.18)
        self.ready("power_cubic_limit")
        divided = self.tf(r"3x^2+3xh+h^2", {"a": "3x^2", "b": "3xh", "c": "h^2"}, -.25)
        self.transfer("cubic_divide_h", reduced, divided,
                      [(k, k) for k in ("a", "b", "c")], 18.0, 21.2, retain=True)
        limit = self.tf(r"3x^2\quad(h\to0)", {"a": "3x^2"}, -.25)
        self.transfer("cubic_limit", divided, limit, [("a", "a")], 23.4, 26.4)
        rule = self.sf(r"(x^n)'=nx^{n-1}\quad(n=1,2,3,\ldots;\ x\in\mathbb R)", -1.35, size=31)
        self.beat(.46, FadeIn(rule))
        domains = Group(self.sf(r"n=0:\ (1)'=0;\quad n<0,\ n\in\mathbb Z:\ x\ne0", -2.15, size=28),
                        self.label("实数幂先在 x > 0 使用；端点另查", 0, -2.85, size=27))
        self.beat(.54, FadeIn(domains))
        self.ready("power_rule_domain")
        self.beat(.58)
        for key in ("power_cubic_expansion", "power_cubic_limit", "power_rule_domain"):
            self.focus_end(key)
        self.beat(.62, *(FadeOut(m) for m in (first, reduced, limit, rule, domains)))
        graph, a = self.pair("cube", (-1.5, 1.5), (-3.5, 3.5), (-.5, 7), -1.35)
        self.beat(.67, FadeIn(graph), FadeIn(self.sf(r"x^3\quad\longmapsto\quad3x^2", 2.7)))
        self.ready("power_cubic_map")
        self.beat(.80, a.animate.set_value(0), rate_func=linear)
        self.beat(.95, a.animate.set_value(1.35), rate_func=linear)
        self.focus_end("power_cubic_map")

    def reciprocal(self):
        first = self.tf(r"\frac{1/(x+h)-1/x}{h}",
                        {"changed": "x+h", "old": ("x", 1), "den": ("h", 1)}, 2.2)
        conditions = self.sf(r"x\ne0,\quad h\ne0,\quad x+h\ne0", -2.6, size=30)
        self.reveal(first, 1.96, 2.36)
        self.add(conditions)
        self.ready("reciprocal_quotient")
        self.at(12.42)
        self.ready("reciprocal_common_denominator")
        common = self.tf(r"\frac{x-(x+h)}{h\,x(x+h)}",
            {"top_old": ("x", 0), "top_changed": ("x+h", 0),
             "den": ("h", 1), "bottom_old": ("x", 2), "bottom_changed": ("x+h", 1)}, .8)
        self.gather("reciprocal_common", common,
            [(first, "old", "top_old"), (first, "changed", "top_changed"),
             (first, "den", "den"), (first, "old", "bottom_old"), (first, "changed", "bottom_changed")],
            13.0, 20.0)
        reduced = self.tf(r"\frac{-h}{h\,x(x+h)}",
                         {"num": "-h", "den": ("h", 1), "product": "x(x+h)"}, .8)
        source = self.tf(common.get_tex(), {"num": "x-(x+h)", "den": ("h", 1), "product": "x(x+h)"}, .8)
        self.remove(common)
        self.add(source)
        self.transfer("reciprocal_cancel_x", source, reduced,
                      [(k, k) for k in ("num", "den", "product")], 20.2, 23.5)
        self.at(27.44)
        self.ready("reciprocal_limit")
        cancelled = self.tf(r"-\frac1{x(x+h)}", {"product": "x(x+h)"}, -.55)
        self.transfer("reciprocal_divide_h", reduced, cancelled, [("product", "product")],
                      28.0, 31.0, retain=True)
        limit = self.tf(r"-\frac1{x^2}", {"product": "x^2"}, -.55)
        self.transfer("reciprocal_limit", cancelled, limit, [("product", "product")], 34.0, 37.0)
        self.beat(.48)
        for key in ("reciprocal_quotient", "reciprocal_common_denominator", "reciprocal_limit"):
            self.focus_end(key)
        self.beat(.53, *(FadeOut(m) for m in (first, reduced, limit, conditions)))
        graph, a = self.pair("reciprocal", (-3, 3), (-2.5, 2.5), (-6, .5), -2.5,
                             segments=[(-3, -.45), (.45, 3)])
        self.beat(.58, FadeIn(graph), FadeIn(self.sf(r"1/x\quad\longmapsto\quad-1/x^2", 2.7)))
        self.ready("reciprocal_negative_branch")
        self.beat(.70, a.animate.set_value(-.65), rate_func=linear)
        self.focus_end("reciprocal_negative_branch")
        self.stop_drivers()
        self.beat(.74, FadeOut(graph))
        graph, a = self.pair("reciprocal", (-3, 3), (-2.5, 2.5), (-6, .5), .65,
                             segments=[(-3, -.45), (.45, 3)])
        self.beat(.78, FadeIn(graph))
        self.ready("reciprocal_positive_branch")
        self.beat(.94, a.animate.set_value(2.5), rate_func=linear)
        self.focus_end("reciprocal_positive_branch")

    def root(self):
        first = self.tf(r"\frac{\sqrt{x+h}-\sqrt x}{h}",
                        {"top": r"\sqrt{x+h}-\sqrt x", "den": ("h", 1)}, 2.25, size=34)
        condition = self.sf(r"x>0,\quad h\ne0,\quad x+h\ge0", -2.2, size=29)
        self.reveal(first, 1.94, 2.34)
        self.add(condition)
        self.ready("root_rationalize")
        self.at(12.26)
        self.ready("root_conjugate")
        conjugate = self.tf(r"\frac{(\sqrt{x+h}-\sqrt x)(\sqrt{x+h}+\sqrt x)}{h(\sqrt{x+h}+\sqrt x)}",
            {"top": r"\sqrt{x+h}-\sqrt x", "den": ("h", 2)}, .85, size=32)
        self.transfer("root_multiply_conjugate", first, conjugate,
                      [("top", "top"), ("den", "den")], 12.6, 15.2, retain=True)
        squared = self.tf(r"\frac{(x+h)-x}{h(\sqrt{x+h}+\sqrt x)}",
                         {"top": "(x+h)-x", "bottom": r"h(\sqrt{x+h}+\sqrt x)"}, .85, size=34)
        source = self.tf(conjugate.get_tex(),
            {"top": r"(\sqrt{x+h}-\sqrt x)(\sqrt{x+h}+\sqrt x)",
             "bottom": r"h(\sqrt{x+h}+\sqrt x)"}, .85, size=32)
        self.remove(conjugate)
        self.add(source)
        self.transfer("root_difference_squares", source, squared,
                      [("top", "top"), ("bottom", "bottom")], 15.6, 18.2)
        hrow = self.tf(r"\frac{h}{h(\sqrt{x+h}+\sqrt x)}",
                       {"top": ("h", 0), "bottom": r"h(\sqrt{x+h}+\sqrt x)"}, .85, size=34)
        self.transfer("root_cancel_x", squared, hrow,
                      [("top", "top"), ("bottom", "bottom")], 18.5, 20.2)
        result = self.tf(r"\frac1{\sqrt{x+h}+\sqrt x}", {"sum": r"\sqrt{x+h}+\sqrt x"}, -.5)
        hsource = self.tf(hrow.get_tex(), {"sum": r"\sqrt{x+h}+\sqrt x"}, .85, size=34)
        self.remove(hrow)
        self.add(hsource)
        self.transfer("root_divide_h", hsource, result, [("sum", "sum")], 20.5, 23.8, retain=True)
        self.at(24.1)
        self.ready("root_domain")
        limit = self.tf(r"\frac1{2\sqrt x}", {"sum": r"2\sqrt x"}, -.5)
        self.transfer("root_limit", result, limit, [("sum", "sum")], 27.2, 29.7)
        note = self.label("原函数 x ≥ 0；x = 0 没有有限的右侧斜率极限", 0, -2.85, size=26)
        self.reveal(note, 30.0, 30.5)
        self.beat(.49)
        for key in ("root_rationalize", "root_conjugate", "root_domain"):
            self.focus_end(key)
        self.beat(.54, *(FadeOut(m) for m in (first, hsource, limit, condition, note)))
        graph, a = self.pair("root", (.04, 4), (0, 2.2), (0, 3), .09)
        self.beat(.59, FadeIn(graph), FadeIn(self.sf(r"\sqrt x\quad\longmapsto\quad1/(2\sqrt x)", 2.7)))
        self.ready("root_map")
        self.beat(.94, a.animate.set_value(3.7), rate_func=linear)
        self.focus_end("root_map")

    def exponential(self):
        first = self.tf(r"\frac{a^{x+h}-a^x}{h}",
                        {"shifted": "a^{x+h}", "old": "a^x", "den": ("h", 1)}, 2.0)
        self.reveal(first, 2.14, 2.54)
        self.ready("exp_factor")
        expanded = self.tf(r"\frac{a^x a^h-a^x}{h}",
            {"shifted": "a^x a^h", "old": ("a^x", 1), "den": ("h", 1)}, .9)
        self.transfer("exp_split_power", first, expanded,
                      [(k, k) for k in ("shifted", "old", "den")], 3.0, 5.5, retain=True)
        factored = self.tf(r"a^x\frac{a^h-1}{h}",
                          {"factor": "a^x", "remainder": "a^h-1", "den": ("h", 1)}, .9)
        source = self.tf(expanded.get_tex(),
                         {"factor": ("a^x", 0), "remainder": "a^h-a^x", "den": ("h", 1)}, .9)
        self.remove(expanded)
        self.add(source)
        self.transfer("exp_factor", source, factored,
                      [(k, k) for k in ("factor", "remainder", "den")], 6.0, 8.8)
        factor_source = self.tf(factored.get_tex(),
                                {"factor": "a^x", "rate": r"\frac{a^h-1}{h}"}, .9)
        self.remove(factored)
        self.add(factor_source)
        standard = self.tf(r"\frac{a^h-1}{h}\longrightarrow\ln a\quad(a>0)",
                           {"rate": r"\frac{a^h-1}{h}", "limit": r"\ln a"}, -.3, size=35)
        self.at(13.72)
        self.ready("exp_standard_limit")
        self.transfer("exp_standard_limit", factor_source, standard, [("rate", "rate")],
                      14.0, 16.5, retain=True)
        self.at(24.28)
        self.ready("exp_rule")
        result = self.tf(r"(a^x)'=a^x\ln a", {"factor": ("a^x", 1), "limit": r"\ln a"}, -1.45)
        self.gather("exp_apply_limit", result,
                    [(factor_source, "factor", "factor"), (standard, "limit", "limit")], 24.8, 27.5)
        special = self.sf(r"(e^x)'=e^x,\quad\ln e=1;\qquad x\in\mathbb R", -2.4, size=32)
        self.reveal(special, 30.0, 31.0)
        self.beat(.50)
        for key in ("exp_factor", "exp_standard_limit", "exp_rule"):
            self.focus_end(key)
        self.beat(.55, *(FadeOut(m) for m in (first, factor_source, standard, result, special)))
        graph, a = self.pair("exp", (-1.5, 1.5), (0, 5), (0, 5), -1.3)
        self.beat(.60, FadeIn(graph), FadeIn(self.sf(r"e^x\quad\longmapsto\quad e^x", 2.7)))
        self.ready("exp_map")
        self.beat(.90, a.animate.set_value(1.3), rate_func=linear)
        self.focus_end("exp_map")
        self.beat(.95, FadeIn(self.label("e为底：函数值与斜率数值相同；0<a<1 时斜率为负", 0, -2.72, size=26)))
        self.ready("exp_compare")

    def logarithm(self):
        relation = self.tf(r"y=\ln x\quad\Longleftrightarrow\quad x=e^y",
                           {"old_x": ("x", 1), "old_exp": "e^y"}, 2.65, size=34)
        condition = self.sf(r"x>0,\quad\Delta x\ne0,\quad x+\Delta x>0", -2.85, size=27)
        self.reveal(relation, 2.08, 2.48)
        self.add(condition)
        self.ready("log_variables")
        graph, dx = self.increment_diagram()
        dy = self.tf(r"\Delta y=\ln(x+\Delta x)-y", {"dy": r"\Delta y"}, 1.8, x=3.3, size=30, width=6)
        endpoint = self.tf(r"x+\Delta x=e^{y+\Delta y}",
                           {"new_x": r"x+\Delta x", "new_exp": r"e^{y+\Delta y}"}, .8, x=3.3, size=33, width=6)
        self.reveal(Group(graph, dy, endpoint), 15.86, 16.26)
        self.ready("log_increments")
        self.at(34.22)
        self.ready("log_exp_increment")
        exact = self.tf(r"(x+\Delta x)-x=e^{y+\Delta y}-e^y",
            {"new_x": r"x+\Delta x", "old_x": ("x", 2),
             "new_exp": r"e^{y+\Delta y}", "old_exp": "e^y"}, -.28, x=3.3, size=27, width=6)
        self.gather("log_subtract_relations", exact,
            [(endpoint, "new_x", "new_x"), (relation, "old_x", "old_x"),
             (endpoint, "new_exp", "new_exp"), (relation, "old_exp", "old_exp")], 34.5, 37.0)
        factored = self.tf(r"\Delta x=e^y(e^{\Delta y}-1)",
                          {"dx": r"\Delta x", "factor": "e^y", "increment": r"e^{\Delta y}-1"},
                          -.28, x=3.3, size=30, width=6)
        exact_source = self.tf(exact.get_tex(),
            {"dx": r"(x+\Delta x)-x", "factor": "e^y", "increment": r"e^{y+\Delta y}"},
            -.28, x=3.3, size=27, width=6)
        self.remove(exact)
        self.add(exact_source)
        self.transfer("log_factor_exponential", exact_source, factored,
                      [(k, k) for k in ("dx", "factor", "increment")], 37.2, 40.0, serial=True)
        increment = self.tf(r"\Delta x=x(e^{\Delta y}-1)",
                           {"factor": ("x", 1), "increment": r"e^{\Delta y}-1"}, -.28, x=3.3, size=31, width=6)
        self.transfer("log_replace_exp_y", factored, increment,
                      [("factor", "factor"), ("increment", "increment")], 40.2, 42.8)
        nonzero = self.sf(r"\Delta x\ne0\Rightarrow\Delta y\ne0", -.8, x=-3.4, size=27, width=5.5)
        self.reveal(nonzero, 43.2, 44.0)
        self.beat(.27)
        self.ready("log_increment_motion")
        self.beat(.36, dx.animate.set_value(.08), rate_func=linear)
        self.focus_end("log_increment_motion")
        self.beat(.38, FadeOut(nonzero))
        continuity = self.sf(r"\Delta x\to0\Rightarrow\Delta y\to0", -.8, x=-3.4, size=27, width=5.5)
        self.reveal(continuity, 57.9, 58.2)
        self.ready("log_exp_rate")
        exp_rate = self.tf(r"\frac{\Delta x}{\Delta y}=x\frac{e^{\Delta y}-1}{\Delta y}",
            {"factor": ("x", 1), "increment": r"e^{\Delta y}-1"}, -1.45, x=3.3, size=31, width=6)
        self.transfer("log_divide_dy", increment, exp_rate,
                      [("factor", "factor"), ("increment", "increment")], 61.2, 64.0, retain=True)
        inverse_source = self.tf(r"\frac{\Delta x}{\Delta y}\longrightarrow x",
            {"dx": r"\Delta x", "dy": r"\Delta y", "limit": ("x", 1)}, -1.45, x=3.3, size=33, width=6)
        rate_source = self.tf(exp_rate.get_tex(), {"dx": r"\Delta x", "dy": (r"\Delta y", 0), "limit": ("x", 1)},
                              -1.45, x=3.3, size=31, width=6)
        self.remove(exp_rate)
        self.add(rate_source)
        self.transfer("log_exp_limit", rate_source, inverse_source,
                      [(k, k) for k in ("dx", "dy", "limit")], 68.0, 71.0)
        self.beat(.43)
        self.focus_end("log_increments")
        self.focus_end("log_exp_increment")
        self.beat(.45, FadeOut(dy), FadeOut(endpoint), FadeOut(increment))
        self.at(75.42)
        self.ready("log_inverse_limit")
        inverse = self.tf(r"\frac{\Delta y}{\Delta x}\longrightarrow\frac1x",
            {"dx": r"\Delta x", "dy": r"\Delta y", "limit": ("x", 1)}, 1.15, x=3.3, size=35, width=6)
        self.transfer("log_reciprocal_limit", inverse_source, inverse,
                      [(k, k) for k in ("dx", "dy", "limit")], 76.0, 79.0, retain=True, arc=.6, serial=True)
        derivative = self.sf(r"(\ln x)'=\frac1x\quad(x>0)", .25, x=3.3, size=34, width=6)
        self.reveal(derivative, 80.2, 81.5)
        self.beat(.51)
        for key in ("log_variables", "log_exp_rate", "log_inverse_limit"):
            self.focus_end(key)
        self.clear_log_phase(.53)
        pair, a = self.pair("log", (.2, 4), (-2, 2), (0, 5.5), .25)
        self.beat(.56, FadeIn(pair), FadeIn(self.sf(r"\ln x\quad\longmapsto\quad1/x\quad(x>0)", 2.7)))
        self.ready("log_map")
        self.beat(.67, a.animate.set_value(3.7), rate_func=linear)
        self.focus_end("log_map")
        self.clear_log_phase(.70)
        base = self.tf(r"k=\frac1{\ln a}\quad\text{(constant)},\quad x>0,\ a>0,\ a\ne1",
                       {"k": "k", "one": ("1", 0), "base_log": r"\ln a"}, 2.65, size=30)
        z = self.tf(r"z=\log_a x=\frac{\ln x}{\ln a}=k\ln x", {"k": "k", "log": (r"\ln x", 1)}, 1.55, size=35)
        self.reveal(Group(base, z), 98.64, 99.04)
        self.ready("log_base_definition")
        self.at(117.84)
        self.ready("log_base_increment")
        dz = self.tf(r"\Delta z=k\ln(x+\Delta x)-k\ln x",
            {"left_k": ("k", 0), "right_k": ("k", 1), "old": r"\ln x"}, .4, size=34)
        self.gather("log_base_difference", dz,
                    [(z, "k", "left_k"), (z, "k", "right_k"), (z, "log", "old")], 118.2, 121.2)
        combined = self.tf(r"\Delta z=k[\ln(x+\Delta x)-\ln x]",
                           {"dz": r"\Delta z", "k": "k", "difference": r"\ln(x+\Delta x)-\ln x"}, .4, size=34)
        dz_source = self.tf(dz.get_tex(),
            {"dz": r"\Delta z", "k": ("k", 0), "difference": r"\ln(x+\Delta x)-k\ln x"}, .4, size=34)
        self.remove(dz)
        self.add(dz_source)
        self.transfer("log_base_factor_k", dz_source, combined,
                      [(k, k) for k in ("dz", "k", "difference")], 122.0, 124.5)
        dyk = self.tf(r"\Delta z=k\Delta y", {"dz": r"\Delta z", "k": "k", "difference": r"\Delta y"}, .4)
        self.transfer("log_base_name_dy", combined, dyk,
                      [(k, k) for k in ("dz", "k", "difference")], 125.0, 127.5)
        self.at(131.72)
        self.ready("log_base_quotient")
        quotient = self.tf(r"\frac{\Delta z}{\Delta x}=k\frac{\Delta y}{\Delta x}",
                           {"dz": r"\Delta z", "k": "k", "difference": r"\Delta y"}, -.8)
        self.transfer("log_base_divide_dx", dyk, quotient,
                      [(k, k) for k in ("dz", "k", "difference")], 132.2, 135.0, retain=True)
        quotient_source = self.tf(quotient.get_tex(),
            {"left": r"\frac{\Delta z}{\Delta x}", "right": r"k\frac{\Delta y}{\Delta x}"}, -.8)
        self.remove(quotient)
        self.add(quotient_source)
        limit = self.tf(r"\frac{\Delta z}{\Delta x}\longrightarrow\frac{k}{x}",
                        {"left": r"\frac{\Delta z}{\Delta x}", "right": r"\frac{k}{x}"}, -.8)
        self.transfer("log_base_limit", quotient_source, limit,
                      [("left", "left"), ("right", "right")], 137.0, 140.0)
        coefficient_source = self.tf(limit.get_tex(), {"input": ("x", 1)}, -.8)
        self.remove(limit)
        self.add(coefficient_source)
        self.at(144.32)
        for key in ("log_base_definition", "log_base_increment", "log_base_quotient"):
            self.focus_end(key)
        self.ready("log_base_derivative")
        self.drop(144.8, z, dyk)
        result = self.tf(r"(\log_a x)'=\frac1{x\ln a}",
                         {"one": "1", "input": ("x", 1), "coefficient": r"\ln a"},
                         -1.9, x=-3.2, size=36, width=6.1)
        self.gather("log_base_restore_k", result,
            [(base, "one", "one"), (coefficient_source, "input", "input"),
             (base, "base_log", "coefficient")], 145.0, 148.0, retire=(coefficient_source,))
        values = self.tf(r"a=2,\quad x=2", {"base": ("2", 0), "input": ("2", 1)},
                         -1.0, x=3.3, size=30, width=6.1)
        self.reveal(values, 150.0, 151.0)
        example = self.tf(r"z'=\frac1{2\ln2}", {"input": ("2", 0), "base": ("2", 1)},
                          -1.95, x=3.3, size=34, width=6.1)
        self.gather("log_base_example", example,
                    [(values, "input", "input"), (values, "base", "base")], 151.3, 154.0)
        self.beat(.96, FadeIn(self.label("a>1 时斜率为正；0<a<1 时斜率为负", 0, -2.85, size=27)))
        self.ready("log_base_sign")

    def sine(self):
        first = self.tf(r"\frac{\sin(x+h)-\sin x}{h}",
                        {"shift": r"\sin(x+h)", "old": r"\sin x", "den": ("h", 1)}, 2.0, size=35)
        self.reveal(first, 1.3, 1.7)
        standards = self.tf(r"\frac{\sin h}{h}\to1,\quad\frac{\cos h-1}{h}\to0\quad(\mathrm{radians})",
                            {"one": ("1", 0), "zero": "0"}, -.1, size=31)
        self.reveal(standards, 2.12, 2.52)
        self.ready("sine_limits")
        angle = self.tf(r"\frac{\sin x\cos h+\cos x\sin h-\sin x}{h}",
            {"shift": r"\sin x\cos h+\cos x\sin h", "old": (r"\sin x", 1), "den": ("h", 2)},
            1.05, size=33)
        self.transfer("sine_angle_substitution", first, angle,
                      [(k, k) for k in ("shift", "old", "den")], 3.0, 5.6, retain=True)
        expanded = self.tf(r"\sin x\frac{\cos h-1}{h}+\cos x\frac{\sin h}{h}",
            {"sin": r"\sin x", "cos": r"\cos x", "left_ratio": r"\frac{\cos h-1}{h}",
             "right_ratio": r"\frac{\sin h}{h}"}, 1.05, size=33)
        angle_source = self.tf(angle.get_tex(),
            {"sin": (r"\sin x", 0), "cos": r"\cos x", "left_ratio": r"\cos h",
             "right_ratio": r"\sin h"}, 1.05, size=33)
        self.remove(angle)
        self.add(angle_source)
        self.transfer("sine_collect_ratios", angle_source, expanded,
                      [(k, k) for k in ("sin", "cos", "left_ratio", "right_ratio")], 5.8, 8.6)
        substituted = self.tf(r"\sin x\cdot0+\cos x\cdot1", {"sin": r"\sin x", "cos": r"\cos x", "zero": "0", "one": "1"}, -1.3)
        self.gather("sine_apply_limits", substituted,
                    [(expanded, "sin", "sin"), (expanded, "cos", "cos"),
                     (standards, "zero", "zero"), (standards, "one", "one")], 10.0, 13.0,
                    retire=(standards,))
        result = self.tf(r"(\sin x)'=\cos x", {"cos": r"\cos x"}, -1.3)
        self.transfer("sine_remove_zero", substituted, result, [("cos", "cos")], 14.0, 16.5)
        self.beat(.42)
        self.focus_end("sine_limits")
        self.beat(.48, *(FadeOut(m) for m in (first, expanded, result)))
        graph, a = self.pair("sin", (0, 2*math.pi), (-1.25, 1.25), (-1.25, 1.25), 0)
        self.beat(.54, FadeIn(graph), FadeIn(self.sf(r"(\sin x)'=\cos x\qquad x\in\mathbb R\ (\mathrm{rad})", 2.7, size=36)))
        self.ready("sine_map")
        self.beat(.68, a.animate.set_value(math.pi/2), rate_func=linear)
        self.beat(.79, a.animate.set_value(math.pi), rate_func=linear)
        self.beat(.94, a.animate.set_value(2*math.pi), rate_func=linear)
        self.focus_end("sine_map")
