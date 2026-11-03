"""Author candidate: chapter 03 traceable operations and intact original graphs.

Formula state belongs to one cue and expires on cue exit. Actual transitions
are journaled for authors and independent reviewers, never as pixel approval.
"""

import numpy as np
from manimlib import Dot, FadeIn, FadeOut, Group, Line, ValueTracker, VMobject, linear
from manimind.components.formula_motion import SemanticFormula
from derivative_ch02_traceable import TraceableSteps
from derivative_ch03_rules_v004 import DerivativeRulesLessonV004
from derivative_ch03_rules import linear_state, product_quotient, average_cost_state
from derivative_chapter_shared import INK, MUTED, CURVE, RATE, ACCENT


AUTHOR = "01a19f5e-8733-71c0-ac2d-d507423acd13"


class DerivativeCh03Traceable(TraceableSteps, DerivativeRulesLessonV004):
    def linearity(self):
        first = self.tf(r"\Delta(u\pm v)=\Delta u\pm\Delta v",
                        {"du": r"\Delta u", "dv": r"\Delta v"}, 2.35)
        self.reveal(first, 1.94, 2.34)
        self.add(self.label("u、v 在同一点可微；c 为常数", 0, 2.93, size=24))
        self.ready("linear_increment")
        self.at(16.14)
        self.ready("linear_limit")
        divided = self.tf(r"\frac{\Delta(u\pm v)}h=\frac{\Delta u}h\pm\frac{\Delta v}h",
                          {"du": r"\Delta u", "dv": r"\Delta v"}, 1.1, size=35)
        self.transfer("linear_divide_h", first, divided, [("du", "du"), ("dv", "dv")],
                      16.4, 19.0, retain=True)
        rates = self.tf(divided.get_tex(), {"u_rate": r"\frac{\Delta u}h", "v_rate": r"\frac{\Delta v}h"}, 1.1, size=35)
        self.remove(divided)
        self.add(rates)
        rule = self.tf(r"(u\pm v)'=u'\pm v'", {"u_rate": "u'", "v_rate": "v'"}, 1.1)
        self.transfer("linear_take_limit", rates, rule,
                      [("u_rate", "u_rate"), ("v_rate", "v_rate")], 20.0, 23.0)
        scalar = self.tf(r"\Delta(cu)=c\Delta u", {"c": ("c", 1), "du": r"\Delta u"}, -.15, size=34)
        self.reveal(scalar, 26.34, 26.74)
        self.ready("linear_scalar")
        scalar_rate = self.tf(r"\frac{\Delta(cu)}h=c\frac{\Delta u}h",
                              {"c": ("c", 1), "du": r"\Delta u"}, -.15, size=34)
        self.transfer("scalar_divide_h", scalar, scalar_rate, [("c", "c"), ("du", "du")], 28.0, 30.5)
        scalar_source = self.tf(scalar_rate.get_tex(), {"c": ("c", 1), "rate": r"\frac{\Delta u}h"}, -.15, size=34)
        self.remove(scalar_rate)
        self.add(scalar_source)
        scalar_rule = self.tf(r"(cu)'=cu'", {"c": ("c", 1), "rate": "u'"}, -.15, size=36)
        self.transfer("scalar_take_limit", scalar_source, scalar_rule,
                      [("c", "c"), ("rate", "rate")], 31.5, 34.0)
        h = ValueTracker(.5)
        stems = [Line([x, -2.25, 0], [x, -1, 0], color=color, stroke_width=8)
                 for x, color in zip((-4.5, 0, 4.5), (CURVE, RATE, ACCENT))]
        labels = Group(*(self.sf(text, -2.72, x=x, size=29, width=3)
            for x, text in ((-4.5, r"\Delta u"), (0, r"\Delta v"), (4.5, r"\Delta u+\Delta v"))))
        context = self.label("同一输入增量 h：u=x²，v=x，取 x=1", 0, -.88, size=26)

        def update(_):
            state = linear_state(1, float(h.get_value()))
            for line, x, key in zip(stems, (-4.5, 0, 4.5), ("du", "dv", "sum_increment")):
                line.put_start_and_end_on(np.array([x, -2.25, 0]), np.array([x, -2.25+.55*state[key], 0]))
            self.sample("linear_increments", **state)

        self.driver(update)
        self.beat(.56, FadeIn(Group(*stems, labels, context)))
        self.ready("linear_motion")
        self.beat(.88, h.animate.set_value(.05), rate_func=linear)
        self.focus_end("linear_motion")
        self.beat(.95)

    def product_area(self):
        base, right, top, corner, h = self.area()
        self.beat(.12, FadeIn(base), FadeIn(self.sf(r"(u+\Delta u)(v+\Delta v)", 2.3, x=3.2, width=6.1, size=36)))
        self.ready("product_base")
        right_label = self.tf(r"v\Delta u", {"area": r"v\Delta u"}, 1.2, x=3.2,
                              width=6, colors={"area": RATE})
        top_label = self.tf(r"u\Delta v", {"area": r"u\Delta v"}, .15, x=3.2,
                            width=6, colors={"area": CURVE})
        corner_label = self.tf(r"\Delta u\Delta v", {"area": r"\Delta u\Delta v"}, -.9, x=3.2,
                               width=6, colors={"area": ACCENT})
        self.beat(.28, FadeIn(right), FadeIn(right_label))
        self.ready("product_right")
        self.beat(.44, FadeIn(top), FadeIn(top_label))
        self.ready("product_top")
        self.beat(.60, FadeIn(corner), FadeIn(corner_label))
        self.ready("product_corner")
        self.at(48.52)
        self.ready("product_exact_increment")
        exact = self.tf(r"\Delta(uv)=v\Delta u+u\Delta v+\Delta u\Delta v",
            {"right": r"v\Delta u", "top": (r"u\Delta v", 0), "corner": r"\Delta u\Delta v"},
            -2.1, x=2.6, size=31, width=7.8, colors={"right": RATE, "top": CURVE, "corner": ACCENT})
        self.gather("product_collect_areas", exact,
                    [(right_label, "area", "right"), (top_label, "area", "top"),
                     (corner_label, "area", "corner")], 48.9, 52.2)

    def product_limit(self):
        base, right, top, corner, h = self.area()
        graph = Group(base, right, top, corner)
        exact = self.tf(r"\Delta(uv)=v\Delta u+u\Delta v+\Delta u\Delta v",
            {"right": r"v\Delta u", "top": (r"u\Delta v", 0), "corner": r"\Delta u\Delta v"},
            1.9, x=3.25, size=31, width=6.2)
        self.beat(.13, FadeIn(graph), FadeIn(exact))
        self.ready("product_divided")
        divided = self.tf(r"\frac{\Delta(uv)}h=v\frac{\Delta u}h+u\frac{\Delta v}h+\frac{\Delta u}h\Delta v",
            {"right": r"v\frac{\Delta u}h", "top": r"u\frac{\Delta v}h", "corner": r"\frac{\Delta u}h\Delta v"},
            1.9, x=3.25, size=32, width=6.2)
        self.transfer("product_divide_h", exact, divided,
                      [(k, k) for k in ("right", "top", "corner")], 3.0, 6.2)
        standards = self.sf(r"\Delta u/h\to u',\quad\Delta v/h\to v',\quad\Delta v\to0", .7, x=3.25, width=6.2, size=31)
        self.beat(.27, FadeIn(standards))
        self.ready("product_limits")
        corner_rate = self.number(product_quotient(1, .6)["corner_rate"], decimals=3, size=28, color=ACCENT)
        rate_label = self.sf(r"\Delta u\Delta v/h\approx", -.45, x=2.5, size=28, width=3.9)
        self.driver(lambda _: corner_rate.set_value(product_quotient(1, h.get_value())["corner_rate"]).move_to([5.15, -.45, 0]))
        self.beat(.38, FadeIn(rate_label), FadeIn(corner_rate))
        self.ready("product_corner_shrink")
        self.beat(.69, h.animate.set_value(.025), rate_func=linear)
        self.focus_end("product_corner_shrink")
        self.at(46.48)
        self.ready("product_rule")
        self.drop(46.9, standards, rate_label, corner_rate)
        intermediate = self.tf(r"v u'+u v'+u'\cdot0",
            {"right": "v u'", "top": "u v'", "corner": r"u'\cdot0"}, -1.55, x=3.2, size=34, width=6.1)
        self.transfer("product_take_limits", divided, intermediate,
                      [(k, k) for k in ("right", "top", "corner")], 47.2, 50.0, retain=True)
        rule = self.tf(r"(uv)'=u'v+uv'", {"right": "u'v", "top": "uv'"},
                       -1.55, x=3.2, size=42, width=6.1)
        self.transfer("product_remove_corner", intermediate, rule,
                      [("right", "right"), ("top", "top")], 50.4, 53.2)
        self.beat(.91, FadeIn(self.label("同一点的 u、v；可微保证增量趋零", 2.5, -2.65, size=25, width=7.7)))

    def product_example(self):
        first = self.tf(r"f(x)=x^2\sin x\qquad(x\in\mathbb R,\ \mathrm{rad})",
                        {"u": "x^2", "v": r"\sin x"}, 2.0)
        info = self.tf(r"u=x^2,\quad u'=2x;\qquad v=\sin x,\quad v'=\cos x",
                       {"u": "x^2", "up": "2x", "v": r"\sin x", "vp": r"\cos x"}, .6, size=35)
        self.beat(.15, FadeIn(first))
        self.ready("product_example_factors")
        self.beat(.38, FadeIn(info))
        self.ready("product_example_derivatives")
        self.at(18.1)
        self.ready("product_example_result")
        first_term = self.tf(r"f'(x)=2x\sin x", {"up": "2x", "v": r"\sin x"},
                             -.85, x=-2.5, size=39, width=6)
        self.gather("product_example_first", first_term,
                    [(info, "up", "up"), (info, "v", "v")], 18.5, 21.4)
        second_term = self.tf(r"+x^2\cos x", {"u": "x^2", "vp": r"\cos x"},
                              -.85, x=3.0, size=39, width=5)
        self.gather("product_example_second", second_term,
                    [(info, "u", "u"), (info, "vp", "vp")], 22.0, 25.0)
        self.beat(.84, FadeIn(self.label("每一项：一个因子的变化率 × 另一个因子的当前值", 0, -2.25, size=28)))

    def quotient_increment(self):
        known = self.tf(r"q=\frac uv", {"u": "u", "v": "v"}, 2.2)
        condition = self.sf(r"v\ne0,\qquad v+\Delta v\ne0", -2.1, size=32)
        self.beat(.13, FadeIn(known), FadeIn(condition))
        self.ready("quotient_difference")
        difference = self.tf(r"\Delta(u/v)=\frac{u+\Delta u}{v+\Delta v}-\frac uv",
            {"new_u": r"u+\Delta u", "new_v": r"v+\Delta v", "old_u": ("u", 3), "old_v": ("v", 3)}, 2.2, size=36)
        self.transfer("quotient_build_difference", known, difference,
                      [("u", "old_u"), ("v", "old_v")], 3.0, 6.0)
        self.at(21.42)
        self.ready("quotient_common_denominator")
        common = self.tf(r"\frac{v(u+\Delta u)-u(v+\Delta v)}{v(v+\Delta v)}",
            {"new_u": r"u+\Delta u", "old_u": ("u", 2), "old_v_top": ("v", 0),
             "old_v_bottom": ("v", 3), "new_v_top": (r"v+\Delta v", 0), "new_v_bottom": (r"v+\Delta v", 1)},
            .8, size=37)
        self.gather("quotient_cross_multiply", common,
            [(difference, "new_u", "new_u"), (difference, "old_u", "old_u"),
             (difference, "old_v", "old_v_top"), (difference, "old_v", "old_v_bottom"),
             (difference, "new_v", "new_v_top"), (difference, "new_v", "new_v_bottom")], 22.2, 26.4)
        self.at(38.22)
        self.ready("quotient_cancel")
        expanded = self.tf(r"\frac{uv+v\Delta u-uv-u\Delta v}{v(v+\Delta v)}",
            {"left": r"uv+v\Delta u", "right": r"-uv-u\Delta v", "den": r"v(v+\Delta v)"}, -.65, size=36)
        grouped = self.tf(common.get_tex(), {"left": r"v(u+\Delta u)", "right": r"-u(v+\Delta v)", "den": r"v(v+\Delta v)"}, .8, size=37)
        self.remove(common)
        self.add(grouped)
        self.transfer("quotient_expand_products", grouped, expanded,
                      [(k, k) for k in ("left", "right", "den")], 38.7, 42.2, retain=True)
        reduced = self.tf(r"\frac{v\Delta u-u\Delta v}{v(v+\Delta v)}",
            {"left": r"v\Delta u", "right": r"u\Delta v", "den": r"v(v+\Delta v)"}, -.65, size=39)
        source = self.tf(expanded.get_tex(), {"left": r"v\Delta u", "right": r"u\Delta v", "den": r"v(v+\Delta v)"}, -.65, size=36)
        self.remove(expanded)
        self.add(source)
        self.transfer("quotient_cancel_uv", source, reduced,
                      [(k, k) for k in ("left", "right", "den")], 43.0, 46.3)
        self.beat(.82, FadeIn(self.label("分子：uv相消；分母：保留两次所在位置的分母", 0, -2.85, size=27)))

    def quotient_limit(self):
        exact = self.tf(r"\Delta(u/v)=\frac{v\Delta u-u\Delta v}{v(v+\Delta v)}",
            {"left": r"v\Delta u", "right": r"u\Delta v", "den": r"v(v+\Delta v)"}, 2.1, size=37)
        self.beat(.13, FadeIn(exact))
        self.ready("quotient_divide_h")
        divided = self.tf(r"\frac{\Delta(u/v)}h=\frac{v(\Delta u/h)-u(\Delta v/h)}{v(v+\Delta v)}",
            {"left": r"v(\Delta u/h)", "right": r"u(\Delta v/h)", "den": r"v(v+\Delta v)"}, 2.1, size=37)
        self.transfer("quotient_divide_h", exact, divided,
                      [(k, k) for k in ("left", "right", "den")], 3.0, 6.4)
        standards = self.sf(r"\Delta u/h\to u',\quad\Delta v/h\to v',\quad\Delta v\to0", .65, size=35)
        condition = self.label("u、v在同一点可微；v连续且非零，附近的分母也能保持非零", 0, -2.3, size=27)
        self.beat(.35, FadeIn(standards), FadeIn(condition))
        self.ready("quotient_take_limit")
        numerator_limit = self.tf(r"\frac{v u'-u v'}{v(v+\Delta v)}",
            {"left": "v u'", "right": "u v'", "den": r"v(v+\Delta v)"}, 2.1, size=39)
        self.transfer("quotient_numerator_limit", divided, numerator_limit,
                      [(k, k) for k in ("left", "right", "den")], 15.2, 18.5)
        zero_limit = self.tf(r"\frac{v u'-u v'}{v(v+0)}",
            {"left": "v u'", "right": "u v'", "den": "v(v+0)"}, 2.1, size=39)
        self.transfer("quotient_denominator_limit", numerator_limit, zero_limit,
                      [(k, k) for k in ("left", "right", "den")], 20.0, 23.2)
        self.at(30.22)
        self.ready("quotient_rule")
        self.drop(30.5, standards)
        square = self.tf(r"\left(\frac uv\right)'=\frac{v u'-u v'}{v^2}\quad(v\ne0)",
            {"left": "v u'", "right": "u v'", "den": "v^2"}, -.9, size=40)
        self.transfer("quotient_square_denominator", zero_limit, square,
                      [(k, k) for k in ("left", "right", "den")], 30.8, 33.8)
        rule = self.tf(r"\left(\frac uv\right)'=\frac{u'v-uv'}{v^2}\quad(v\ne0)",
            {"left": "u'v", "right": "uv'", "den": "v^2"}, -.9, size=42)
        self.transfer("quotient_rule_order", square, rule,
                      [(k, k) for k in ("left", "right", "den")], 34.4, 37.3)
        self.beat(.84)

    def cost_example(self):
        context = self.label("连续产量模型：x 百件，C(x) 百元，A(x) 元/件", 0, 2.6, size=27)
        model = self.tf(r"C=x^2+4,\quad A=\frac{x^2+4}{x}\quad(x>0)",
                        {"num": ("x^2+4", 1), "den": ("x", 2)}, 1.65, x=3.2, size=32, width=6.1)
        self.beat(.12, FadeIn(context), FadeIn(model))
        self.ready("cost_model")
        self.at(22.26)
        self.ready("cost_substitute")
        rates = self.tf(r"u'=2x,\quad v'=1", {"up": "2x", "vp": "1"}, .75, x=3.2, size=29, width=6.1)
        self.reveal(rates, 22.4, 23.0)
        substituted = self.tf(r"A'=\frac{2x\cdot x-(x^2+4)\cdot1}{x^2}",
            {"up": "2x", "top_den": ("x", 1), "num": "x^2+4", "vp": "1", "bottom_den": ("x", 3)},
            -.15, x=3.2, size=34, width=6.1)
        self.gather("cost_substitute", substituted,
            [(rates, "up", "up"), (model, "den", "top_den"), (model, "num", "num"),
             (rates, "vp", "vp"), (model, "den", "bottom_den")], 23.3, 28.5)
        self.at(33.26)
        self.ready("cost_derivative")
        source = self.tf(substituted.get_tex(),
            {"positive": r"2x\cdot x", "negative": r"-(x^2+4)\cdot1", "den": ("x^2", 1)},
            -.15, x=3.2, size=34, width=6.1)
        self.remove(substituted)
        self.add(source)
        expanded = self.tf(r"\frac{2x^2-x^2-4}{x^2}",
            {"positive": "2x^2", "negative": "-x^2-4", "den": ("x^2", 2)}, -.75, x=3.2, size=36, width=6.1)
        self.transfer("cost_expand_numerator", source, expanded,
                      [(k, k) for k in ("positive", "negative", "den")], 34.0, 36.0, retain=True)
        combined = self.tf(r"\frac{x^2-4}{x^2}", {"square": ("x^2", 0), "four": "4", "den": ("x^2", 1)},
                           -.75, x=3.2, size=36, width=6.1)
        expanded_source = self.tf(expanded.get_tex(), {"square": "2x^2-x^2", "four": "4", "den": ("x^2", 2)},
                                  -.75, x=3.2, size=36, width=6.1)
        self.remove(expanded)
        self.add(expanded_source)
        self.transfer("cost_combine_squares", expanded_source, combined,
                      [(k, k) for k in ("square", "four", "den")], 36.2, 38.2)
        split = self.tf(r"\frac{x^2}{x^2}-\frac4{x^2}",
                        {"square": ("x^2", 0), "four": "4", "den": ("x^2", 2)}, -.75, x=3.2, size=36, width=6.1)
        self.transfer("cost_split_fraction", combined, split,
                      [(k, k) for k in ("square", "four", "den")], 38.5, 40.5)
        split_source = self.tf(split.get_tex(), {"one": r"\frac{x^2}{x^2}", "four": "4", "den": ("x^2", 2)},
                               -.75, x=3.2, size=36, width=6.1)
        self.remove(split)
        self.add(split_source)
        result = self.tf(r"1-\frac4{x^2}", {"one": "1", "four": "4", "den": "x^2"},
                         -.75, x=3.2, size=41, width=6.1)
        self.transfer("cost_cancel_square", split_source, result,
                      [(k, k) for k in ("one", "four", "den")], 40.8, 43.0)
        self.remove(rates, source)
        p = lambda x, y: np.array([-6.0+1.33*(x-.5), -1.7+.60*(y-3.5), 0.])
        axes = Group(Line(p(.5, 3.5), p(4.45, 3.5), color=MUTED),
                     Line(p(.5, 3.5), p(.5, 8.5), color=MUTED),
                     self.sf("x", -2.05, x=-.55, size=25, width=.5),
                     self.sf("A", 1.55, x=-6.35, size=25, width=.5))
        for x in (1, 2, 3, 4):
            axes.add(self.sf(str(x), -2.05, x=p(x, 3.5)[0], size=25, width=.6))
        for y in (4, 6, 8):
            axes.add(self.sf(str(y), p(.5, y)[1], x=-6.35, size=25, width=.6))
        curve = VMobject().set_points_as_corners([p(x, average_cost_state(float(x))["average_cost"])
                                                for x in np.linspace(.55, 4.4, 150)]).set_stroke(CURVE, 3)
        a = ValueTracker(1)
        dot = Dot(color=ACCENT)
        tangent = Line([0, 0, 0], [1, 0, 0], color=ACCENT, stroke_width=3)
        read = self.number(-3, decimals=2, size=30, color=RATE)
        x_read = self.number(1, decimals=2, size=29, color=ACCENT)

        def update(_):
            s = average_cost_state(float(a.get_value()))
            x, y, slope = s["x"], s["average_cost"], s["derivative"]
            dot.move_to(p(x, y))
            tangent.put_start_and_end_on(p(x-.25, y-.25*slope), p(x+.25, y+.25*slope))
            read.set_value(slope).move_to([4.7, -1.9, 0])
            x_read.set_value(x).move_to([-3.1, -2.72, 0])
            self.sample("average_cost", **s, point=dot.get_center().tolist())

        self.driver(update)
        graph = Group(axes, curve, dot, tangent, read, x_read,
                      self.sf(r"A'(x)\approx", -1.9, x=2.5, size=30, width=2),
                      self.sf(r"x\approx", -2.72, x=-4.4, size=29, width=1.5))
        self.beat(.45, FadeIn(graph))
        self.ready("cost_decreasing")
        self.beat(.61, a.animate.set_value(2), rate_func=linear)
        self.focus_end("cost_decreasing")
        minimum = self.sf(r"x=2:\quad A=4,\quad A'=0", -2.75, x=3.1, size=29, width=6)
        self.beat(.68, FadeIn(minimum))
        self.ready("cost_stationary")
        self.beat(.75)
        self.focus_end("cost_stationary")
        self.beat(.78, FadeOut(minimum))
        self.ready("cost_increasing")
        self.beat(.95, a.animate.set_value(4), rate_func=linear)
        self.focus_end("cost_increasing")
