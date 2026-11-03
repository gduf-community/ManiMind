"""Repair point scope and scalar collection over the immutable v009 lesson.

Writer: 01a19f6b-1725-7be3-a4d8-bf988a308b31. Consumers: native renderer,
tests and independent reviewers. Every construct owns its scope labels and
active formulas. Sources, geometry, timings or pixels changing invalidate the
observations. This scene grants no approval and never changes original audio.
"""

import hashlib

from derivative_ch04_traceable_v009 import DerivativeChainTraceableV009, AUTHOR_AGENT
from derivative_ch04_traceable_v008 import remainder
from derivative_ch04_chain import U_COLOR, Y_COLOR
from derivative_chapter_shared import MUTED
from manimlib import FadeIn, FadeOut, Group, VGroup
from manimind.components.formula_motion import matching_transform


PRODUCT = r"y'=4(3x-1)^3\cdot3"
FINAL = r"y'=12(3x-1)^3"


def align_native_glyphs(target, source):
    left = target.family_members_with_points()
    right = source.family_members_with_points()
    if len(left) != len(right):
        raise ValueError("The same mathematical part needs the same native glyph topology")
    for a, b in zip(left, right, strict=True):
        a.set_points(b.get_points().copy())


def geometry_signature(part):
    return hashlib.sha256(part.get_all_points().round(5).tobytes()).hexdigest()


class DerivativeChainTraceableV010(DerivativeChainTraceableV009):
    def semantic(self, latex, tokens, **kwargs):
        if latex != PRODUCT or "input" not in tokens:
            return super().semantic(latex, tokens, **kwargs)
        tokens = {**tokens, "prefix": "y'", "times": r"\cdot"}
        product = super().semantic(latex, tokens, **kwargs)
        factor = remainder(product, [product.tag(k) for k in
                           ("prefix", "relation", "coefficient", "rate", "times")])
        reserve = super().semantic("12", {"value": "12"}, size=kwargs.get("size", 44))
        center = product.tag("coefficient").get_center().copy()
        center[0] = factor.get_left()[0] - .10 - reserve.get_width()/2
        product.tag("coefficient").move_to(center)
        lhs = VGroup(*product.tag("prefix").submobjects, *product.tag("relation").submobjects)
        lhs.shift([center[0]-reserve.get_width()/2-.12-lhs.get_right()[0], 0, 0])
        return product

    def carry(self, source, target, start, end, role):
        if role != "collect_4_times_3":
            return super().carry(source, target, start, end, role)
        self.at(start)
        # Retag the identical active expression, not a retained visual copy.
        # Each glyph is placed at its actual source coordinate before replacing
        # the old selector wrapper; no target row is introduced here.
        active = super().semantic(PRODUCT, {"lhs": "y'=", "factor": r"(3x-1)^3",
            "four": "4", "three": ("3", 2), "times": r"\cdot"}, y=-.3, size=43)
        source_lhs = VGroup(*source.tag("prefix").submobjects, *source.tag("relation").submobjects)
        source_factor = remainder(source, [source.tag(k) for k in
                                  ("prefix", "relation", "coefficient", "rate", "times")])
        for key, part in (("lhs", source_lhs), ("factor", source_factor),
                          ("four", source.tag("coefficient")), ("three", source.tag("rate")),
                          ("times", source.tag("times"))):
            align_native_glyphs(active.tag(key), part)
        final = super().semantic(FINAL, {"lhs": "y'=", "factor": r"(3x-1)^3", "twelve": "12"},
                                 y=-.3, size=43)
        align_native_glyphs(final.tag("lhs"), active.tag("lhs"))
        align_native_glyphs(final.tag("factor"), active.tag("factor"))
        final.tag("twelve").move_to(active.tag("four").get_center())
        self.remove(source)
        self.add(active)
        driver = Group()
        frame = getattr(self.camera, "frame", None)
        camera_geometry = None if frame is None else dict(width=float(frame.get_width()),
            height=float(frame.get_height()), center=frame.get_center().tolist())
        self.sample("collection_fixed_regions", factor_box=active.tag("factor").get_bounding_box().tolist(),
                    lhs_box=active.tag("lhs").get_bounding_box().tolist(), camera=camera_geometry)

        def record(_):
            self.sample("collection_fixed_geometry", factor=geometry_signature(active.tag("factor")),
                        lhs=geometry_signature(active.tag("lhs")))

        record(driver)
        driver.add_updater(record)
        self.add(driver)
        self.sample("collection_constants_begin", operation="4 times 3 equals 12")
        animation = matching_transform(active, final,
            pairs=[("lhs", "lhs"), ("factor", "factor")], unmatched_in_place=True)
        self.at(end, animation)
        driver.clear_updaters()
        self.remove(driver)
        self.sample("collection_constants_finalize", factor=geometry_signature(final.tag("factor")),
                    lhs=geometry_signature(final.tag("lhs")))

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
        self.at(25)
        self.focus_end("chain_conditions")
        self.focus_end("chain_rule")
        self.at(25.2, *(FadeOut(m) for m in (general, condition, rule, outer, inner)))
        scope = self.label("本例：从 x=1 出发", 0, 2.55, size=30, color=MUTED)
        functions = self.put(r"u=x^2+1,\qquad y=u^3", 0, 1.8, size=38)
        point = self.put(r"x=1,\quad u=2,\quad \Delta x=h", 0, 1, size=34)
        point_context = Group(scope, functions, point)
        self.at(25.6, FadeIn(point_context))
        self.sample("example_point_scope", x=1, u=2, inner="x^2+1", outer="u^3")
        self.mark("example_point_scope_ready")
        self.focus_begin("small_change_reason")
        local = self.put(r"\Delta u=2h+h^2,\quad\Delta y=12\Delta u+6(\Delta u)^2+(\Delta u)^3", 0, -.65, size=30)
        self.show(26, FadeIn(local))
        self.mark("chain_remainders_ready")
        reason = self.label("输入越来越小，高次项除以 h 后也趋于零", 0, -1.65, size=28)
        self.beat(.69, FadeIn(reason))
        self.at(47)
        self.focus_end("small_change_reason")
        self.at(47.2, FadeOut(point_context), FadeOut(local), FadeOut(reason))
        rule.move_to([0, 2.1, 0]).set_opacity(1)
        variable_scope = self.label("本例：任意实数输入", 0, 1.4, size=26, color=MUTED)
        self.at(47.4, FadeIn(rule), FadeIn(variable_scope))
        rates = self.semantic(r"u=x^2+1,\quad f'(u)=3u^2,\quad g'(x)=2x",
            {"input": "x^2+1", "coefficient": "3", "power": ("2", 1), "rate": "2x"}, y=.7, size=31,
            colors={"input": U_COLOR, "rate": U_COLOR, "coefficient": Y_COLOR, "power": Y_COLOR})
        self.at(47.6, FadeIn(rates))
        self.sample("example_variable_scope", domain="all real x", point_binding_removed=True)
        self.mark("example_variable_scope_ready")
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


class DerivativeChainRepairProbeV010(DerivativeChainTraceableV010):
    def construct(self):
        self.motion_samples = []
        for cue in self.cues:
            self.begin_chapter(cue)
            getattr(self, cue["id"])()
            self.end_chapter()
