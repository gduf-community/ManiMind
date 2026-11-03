"""Lesson 04 author candidate. Native copies start at visible mathematical sources.

Writer: 01a19f6b-1725-7be3-a4d8-bf988a308b31. Consumers: renderer/tests and
independent reviewers. Lifetime: one bound plan/render; any input invalidates
its observations. This module grants no review or publication authority.
"""

from derivative_ch04_chain_v005 import DerivativeChainLessonV005, SCOPE_HEADINGS
from derivative_ch04_chain import X_COLOR, U_COLOR, Y_COLOR, chain_ratios
from derivative_chapter_shared import ACCENT, INK
from manimlib import Arrow, FadeIn, FadeOut, Group, Transform


AUTHOR_AGENT = "01a19f6b-1725-7be3-a4d8-bf988a308b31"
TRANSITIONS = [
    ("name_inner", "two-stages", 5.3, 6.3, 7.76, "name", "(x^2+1) in the original composite", "u=x^2+1", "Keep the landed whole inner expression while naming it"),
    ("split_ratio", "ratios", 5, 10, 15, "factor", "Delta y/Delta x and a new nonzero Delta u", "(Delta y/Delta u)(Delta u/Delta x)", "Insert the same intermediate increment in two distinct roles"),
    ("multiply_rates", "rule", 14.6, 17, 19.4, "multiply", "f'(u) and g'(x), at corresponding inputs", "y'=f'(u)g'(x)", "Assemble the two rates without inventing a general proof from nonzero increments"),
    ("example_substitution", "rule", 48, 51, 54, "substitute", "3u^2, u=x^2+1, and 2x", "3(x^2+1)^2 times 2x", "Substitute the whole inner expression then multiply the inner rate"),
    ("linear_increment", "linear-inner", 10, 11.5, 14, "subtract", "a(x+Delta x)+b-(ax+b)", "a Delta x", "Subtract the two affine states; the constant cancels"),
    ("linear_substitution", "linear-inner", 17, 19, 23, "substitute", "ax+b and the a in Delta u=a Delta x", "f'(ax+b) times a", "Separate whole-input substitution from the inner rate; a=0 handled independently"),
    ("practice_substitution", "practice", 23, 24.9, 27.4, "substitute", "4u^3, u=3x-1, u'=3", "4(3x-1)^3 times 3", "Keep 3x-1 intact and bring the rate from its different source"),
    ("practice_collect", "practice", 27.6, 28.4, 29.4, "collect", "4(3x-1)^3 times 3", "12(3x-1)^3", "Collect numerical factors without scattering the inner expression"),
]


class DerivativeChainTraceable(DerivativeChainLessonV005):
    def at(self, offset, *animations):
        self.until(self._cue["start"] + offset, *animations)

    def show(self, offset, *animations):
        self.at(offset-.4)
        self.at(offset, *animations)

    def carry(self, source, target, start, end, role):
        self.at(start)
        moving = source.copy()
        self.add(moving)
        self.sample("source_copy", role=role, origin=source.get_center().tolist(),
                    destination=target.get_center().tolist(), end=self._cue["start"]+end)
        self.at(end, Transform(moving, target))
        self.remove(moving)
        self.add(target)

    def syntax(self, formula, start, end):
        selected = {id(g) for key in formula.semantic_ids
                    for g in formula.tag(key).family_members_with_points()}
        syntax = Group(*(g for g in formula.family_members_with_points() if id(g) not in selected))
        self.at(start)
        self.at(end, FadeIn(syntax))
        return syntax

    def install(self, formula, syntax):
        self.remove(syntax, *(formula.tag(key) for key in formula.semantic_ids))
        self.add(formula)

    def two_stages(self):
        original = self.semantic(r"y=(x^2+1)^3", {"inside": "x^2+1"}, y=2.1,
                                 colors={"inside": U_COLOR})
        self.beat(.12, FadeIn(original))
        self.focus_begin("compound_expression")
        first = self.semantic(r"u=x^2+1", {"inside": "x^2+1"}, x=-3.4, y=.9,
                              colors={"inside": U_COLOR})
        self.carry(original.tag("inside"), first.tag("inside"), 5.3, 7.2, "whole_inner")
        syntax = self.syntax(first, 7.2, 7.76)
        self.install(first, syntax)
        self.mark("chain_inner_named")
        self.focus_begin("inner_named")
        second = self.semantic(r"y=u^3", {"u": "u", "y": "y"}, x=3.4, y=.9,
                               colors={"u": U_COLOR, "y": Y_COLOR})
        self.beat(.48, FadeIn(Arrow([-1.5, .9, 0], [1.6, .9, 0], buff=.1,
                                   stroke_color=U_COLOR)), FadeIn(second))
        self.mark("chain_two_levels_ready")
        self.focus_begin("two_levels")
        values = Group(self.put("x=1", -4.2, -.7, color=X_COLOR),
                       self.put("u=2", 0, -.7, color=U_COLOR),
                       self.put("y=8", 4.2, -.7, color=Y_COLOR),
                       Arrow([-3.1, -.7, 0], [-1, -.7, 0], buff=.1),
                       Arrow([1, -.7, 0], [3.1, -.7, 0], buff=.1))
        self.beat(.66, FadeIn(values))
        self.mark("chain_base_values_ready")
        self.focus_begin("base_values")
        self.beat(.9, FadeIn(self.label("u：前一步的输出，后一步的输入", 0, -2.1, color=U_COLOR)))

    def ratios(self):
        result = self.semantic(r"\frac{\Delta y}{\Delta x}=\frac{\Delta y}{\Delta u}\cdot\frac{\Delta u}{\Delta x}",
            {"total": r"\frac{\Delta y}{\Delta x}", "dy": (r"\Delta y", 1),
             "du_outer": (r"\Delta u", 0), "du_inner": (r"\Delta u", 1), "dx": (r"\Delta x", 1), "relation": "="},
            y=1.9, size=42, colors={"du_outer": U_COLOR, "du_inner": U_COLOR, "dy": Y_COLOR})
        total = self.semantic(r"\frac{\Delta y}{\Delta x}", {"dy": r"\Delta y", "dx": r"\Delta x"}, y=1.9, size=42)
        total.move_to(result.tag("total"))
        self.beat(.14, FadeIn(total), FadeIn(self.put(r"x=1,\quad 0<|h|<1,\quad \Delta x=h", 0, 2.7, size=30)))
        self.focus_begin("ratio_identity")
        intermediate = self.put(r"\Delta u\ne0", 0, .7, size=33, color=U_COLOR)
        self.show(4.8, FadeIn(intermediate))
        syntax = self.syntax(result, 5, 5.4)
        self.carry(total.tag("dy"), result.tag("dy"), 6.7, 8.4, "outer_numerator")
        du = self.semantic(r"\Delta u\ne0", {"du": r"\Delta u"}, y=.7, size=33,
                           colors={"du": U_COLOR})
        self.remove(intermediate)
        self.add(du)
        self.carry(du.tag("du"), result.tag("du_outer"), 8.5, 10.2, "intermediate_denominator")
        self.carry(du.tag("du"), result.tag("du_inner"), 10.4, 12.1, "intermediate_numerator")
        self.carry(total.tag("dx"), result.tag("dx"), 12.3, 14.6, "original_denominator")
        self.at(15)
        self.remove(total, du)
        self.install(result, syntax)
        self.mark("ratio_identity_ready")
        self.beat(.30, FadeIn(self.put(r"\Delta u=(1+h)^2-1=h(2+h)\ne0", 0, .75, size=37, color=U_COLOR)))
        self.mark("ratio_nonzero_ready")
        self.focus_begin("nonzero_increment")
        labels = Group(self.label("输入增量 h", -4.8, -.15, size=24),
                       self.label("内层比值", -1.6, -.15, size=24, color=U_COLOR),
                       self.label("外层比值", 1.6, -.15, size=24, color=Y_COLOR),
                       self.label("总比值", 4.8, -.15, size=24))
        self.beat(.38, FadeIn(labels))
        self.focus_begin("ratio_limit")
        for index, h in enumerate((.1, .01, .001)):
            rates = chain_ratios(1, h)
            row = Group(*(self.number(v, size=29, decimals=5).move_to([p, -.75-index*.58, 0])
                          for p, v in zip((-4.8, -1.6, 1.6, 4.8),
                              (h, rates["inner_ratio"], rates["outer_ratio"], rates["total_ratio"]))))
            self.beat(.48+index*.15, FadeIn(row))
            self.mark(f"ratio_row_{index+1}_ready")
            self.sample("ratio_row", h=h, **rates)
        self.beat(.9, FadeIn(self.put(r"2\times12=24", 0, -2.65, color=ACCENT)))
        self.mark("ratio_limit_ready")

    def rule(self):
        general = self.semantic(r"u=g(x),\qquad y=f(u)", {"inner": "g(x)", "outer": "f(u)"}, y=2.35,
                                colors={"inner": U_COLOR, "outer": Y_COLOR})
        self.beat(.14, FadeIn(general))
        condition = self.label("内层在 x 处可导，外层在 u=g(x) 处可导", 0, 1.55, size=30)
        self.beat(.25, FadeIn(condition))
        self.mark("chain_conditions_ready")
        self.focus_begin("chain_conditions")
        outer = self.put(r"f'(u)", -3, .7, color=Y_COLOR)
        inner = self.put(r"g'(x)", 3, .7, color=U_COLOR)
        self.show(14.3, FadeIn(outer), FadeIn(inner))
        self.focus_begin("chain_rule")
        rule = self.semantic(r"y'=f'(u)\,g'(x)", {"outer": "f'(u)", "inner": "g'(x)", "relation": "="}, y=-.05,
                             colors={"outer": Y_COLOR, "inner": U_COLOR})
        syntax = self.syntax(rule, 14.6, 15)
        self.carry(outer, rule.tag("outer"), 15, 17, "outer_rate")
        self.carry(inner, rule.tag("inner"), 17.2, 19.4, "inner_rate")
        self.install(rule, syntax)
        self.mark("chain_rule_ready")
        self.show(24.9, FadeOut(outer), FadeOut(inner))
        local = self.put(r"\Delta u=2h+h^2,\quad\Delta y=12\Delta u+6(\Delta u)^2+(\Delta u)^3", 0, -.95, size=29)
        self.beat(.56, FadeIn(local))
        self.mark("chain_remainders_ready")
        self.focus_begin("small_change_reason")
        reason = self.label("输入越来越小，高次项除以 h 后也趋于零", 0, -1.65, size=28)
        self.beat(.69, FadeIn(reason))
        self.at(47)
        self.at(47.2, FadeOut(local), FadeOut(reason), FadeOut(general), FadeOut(condition),
                rule.animate.move_to([0, 2.1, 0]))
        rates = self.semantic(r"u=x^2+1,\quad f'(u)=3u^2,\quad g'(x)=2x",
            {"input": "x^2+1", "coefficient": "3", "power": ("2", 1), "rate": "2x"}, y=.7, size=31,
            colors={"input": U_COLOR, "rate": U_COLOR, "coefficient": Y_COLOR, "power": Y_COLOR})
        self.at(47.6, FadeIn(rates))
        self.focus_begin("chain_example_result")
        example = self.semantic(r"y'=3(x^2+1)^2\cdot2x",
            {"input": "x^2+1", "coefficient": "3", "power": ("2", 1), "rate": "2x", "relation": "="}, y=-.6, size=36)
        syntax = self.syntax(example, 48, 48.4)
        self.carry(Group(rates.tag("coefficient"), rates.tag("power")),
                   Group(example.tag("coefficient"), example.tag("power")), 48.4, 50, "outer_power_rule")
        self.carry(rates.tag("input"), example.tag("input"), 50, 52, "example_whole_input")
        self.carry(rates.tag("rate"), example.tag("rate"), 52, 54, "example_inner_rate")
        self.install(example, syntax)
        self.show(56, FadeIn(self.put(r"x=1:\quad3\cdot2^2\cdot2=24", 0, -1.6, size=34)))
        self.mark("chain_example_derivative_ready")

    def linear_inner(self):
        general = self.semantic(r"y=f(ax+b),\qquad u=ax+b", {"input": ("ax+b", 0), "inner": ("ax+b", 1)},
                                y=2.05, colors={"input": U_COLOR, "inner": U_COLOR})
        self.beat(.16, FadeIn(general))
        self.mark("linear_inner_ready")
        self.focus_begin("linear_input")
        difference = self.put(r"\Delta u=[a(x+\Delta x)+b]-(ax+b)", 0, .95, size=36)
        self.beat(.31, FadeIn(difference))
        self.focus_begin("linear_increment")
        increment = self.semantic(r"\Delta u=a\,\Delta x", {"factor": "a"}, y=.95, size=43,
                                  colors={"factor": U_COLOR})
        self.carry(difference, increment, 10, 14, "subtract_affine_states")
        self.remove(difference)
        self.mark("linear_increment_ready")
        self.at(16.3)
        self.focus_begin("linear_chain")
        result = self.semantic(r"y'=f'(ax+b)\cdot a", {"input": "ax+b", "factor": ("a", 1), "relation": "="},
                               y=-.2, size=47, colors={"input": U_COLOR, "factor": U_COLOR})
        syntax = self.syntax(result, 17, 17.4)
        self.carry(general.tag("inner"), result.tag("input"), 17.4, 20, "affine_whole_input")
        self.carry(increment.tag("factor"), result.tag("factor"), 20.3, 23, "affine_rate")
        self.install(result, syntax)
        self.mark("linear_chain_ready")
        self.beat(.7, FadeIn(self.put(r"a=0:\quad u=b,\quad y=f(b)", 0, -1.35, size=39)))
        self.beat(.83, FadeIn(self.label("f(b) 有定义时，这是常数函数，导数为 0", 0, -2.35, size=29)))
        self.mark("zero_linear_constant_ready")
        self.focus_begin("zero_linear_constant")

    def practice(self):
        original = self.semantic(r"y=(3x-1)^4", {"inside": "3x-1"}, y=2.2,
                                 colors={"inside": U_COLOR})
        self.beat(.13, FadeIn(original))
        self.mark("affine_composite_ready")
        self.focus_begin("affine_question")
        first = self.semantic(r"u=3x-1,\quad u'=3", {"input": "3x-1", "rate": ("3", 1)},
                              x=-2.9, y=.95, size=39, width=5.4,
                              colors={"input": U_COLOR, "rate": U_COLOR})
        second = self.semantic(r"y=u^4,\quad f'(u)=4u^3", {"coefficient": ("4", 1), "power": "3"},
                               x=3, y=.95, size=39, width=5.4, colors={"coefficient": Y_COLOR, "power": Y_COLOR})
        self.beat(.36, FadeIn(first))
        self.mark("affine_inner_ready")
        self.focus_begin("affine_inner")
        self.beat(.51, FadeIn(second))
        self.mark("affine_outer_ready")
        self.focus_begin("affine_outer")
        self.at(22.8)
        self.focus_begin("affine_product")
        product = self.semantic(r"y'=4(3x-1)^3\cdot3", {"coefficient": "4", "input": "3x-1",
            "power": ("3", 1), "rate": ("3", 2), "relation": "="}, y=-.3, size=43)
        syntax = self.syntax(product, 23, 23.3)
        self.carry(Group(second.tag("coefficient"), second.tag("power")),
                   Group(product.tag("coefficient"), product.tag("power")), 23.3, 24.3, "practice_outer_power")
        self.carry(first.tag("input"), product.tag("input"), 24.3, 25.8, "practice_whole_inner")
        self.carry(first.tag("rate"), product.tag("rate"), 25.8, 27.4, "practice_inner_rate")
        self.install(product, syntax)
        final = self.semantic(r"y'=12(3x-1)^3", {"input": "3x-1", "power": ("3", 1), "coefficient": "12"},
                              y=-.3, size=43)
        self.carry(product, final, 27.6, 29.4, "collect_4_times_3")
        self.remove(product)
        self.mark("affine_product_ready")
        self.beat(.82, FadeIn(self.label("这两个多项式复合，对所有实数 x 都可导", 0, -1.45, size=30)))
        self.beat(.9, FadeIn(self.label("外层的输入是整个 3x-1，内层变化率是 3", 0, -2.2, size=29)))
        bottom = [obj for obj in self.mobjects if obj.get_center()[1] < -1]
        self.beat(.92, *(FadeOut(obj) for obj in bottom))
        self.beat(.94, FadeIn(self.put(r"\sqrt{2x+1}:\quad x\ge-\frac12;\quad y'=\frac1{\sqrt{2x+1}},\ x>-\frac12",
                                       0, -1.45, size=29, width=11.8)))
        self.mark("chain_root_domain_ready")
        self.focus_begin("chain_domain_examples")
        self.beat(.96, FadeIn(self.put(r"\ln(2x+1):\quad y'=\frac2{2x+1},\quad x>-\frac12",
                                       0, -2.35, size=30, width=11.8)))
        self.mark("chain_log_domain_ready")
