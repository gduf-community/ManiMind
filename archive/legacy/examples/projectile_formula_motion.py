"""Composable twenty-second landing derivation; frozen experiments are untouched.

Only current_page is returned to the caller. Chapter state and the invisible
sampler belong to a local adapter, removed on exit. motion-samples.json is
create-only render evidence; source, TeX, geometry or timing changes invalidate it.
"""

import json
import math
import sys

import numpy as np

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from manimlib import *
    from manimind.experiments.visual_first_support import VisualLessonScene
finally:
    sys.argv = _host_argv
del _host_argv

from manimind.components.formula_motion import SemanticFormula


TITLE_Y = 2.94
FORMULA_Y = .05
CORRIDOR_GAP = .12


def _bbox(mobject):
    return [float(mobject.get_left()[0]), float(mobject.get_right()[0]),
            float(mobject.get_bottom()[1]), float(mobject.get_top()[1])]


def _opacity(mobject):
    values = []
    for glyph in mobject.family_members_with_points():
        if isinstance(glyph, VMobject):
            fill = float(glyph.get_fill_opacity())
            stroke = float(glyph.get_stroke_opacity()) if glyph.get_stroke_width() > 0 else 0
            values.append(max(fill, stroke))
        else:
            try:
                values.append(float(glyph.get_opacity()))
            except (ValueError, KeyError):
                # GL 1.7.2 ImageMobject inherits the rgba getter but actually
                # stores per-vertex opacity, without an rgba data field.
                if "opacity" not in (glyph.data.dtype.names or ()):
                    raise
                values.extend(float(value) for value in glyph.data["opacity"].ravel())
    return {"min": min(values, default=0), "max": max(values, default=0)}


def _overlap(a, b):
    return min(a[1], b[1]) > max(a[0], b[0]) + 1e-6 and min(a[3], b[3]) > max(a[2], b[2]) + 1e-6


def _lane(source, target, obstacle_boxes, direction):
    half_height = max(source[3] - source[2], target[3] - target[2]) / 2
    if direction == "above":
        lane = max((source[2] + source[3]) / 2 + 1.2,
                   max(box[3] for box in obstacle_boxes) + CORRIDOR_GAP + half_height)
        if lane + half_height > TITLE_Y - .02:
            raise ValueError("Full-term route would cross the title line")
    else:
        lane = min(box[2] for box in obstacle_boxes) - CORRIDOR_GAP - half_height
    return lane


def _lane_path(source_center, target_center, lane, durations, set_phase):
    cuts = np.cumsum(durations) / sum(durations)
    lift = np.array([0., lane - source_center[1], 0.])
    settle = np.array([0., lane - target_center[1], 0.])

    def path(start_points, end_points, alpha):
        if alpha < cuts[0]:
            set_phase("lift")
            return start_points + smooth(alpha / cuts[0]) * lift
        if alpha < cuts[1]:
            set_phase("across")
            amount = smooth((alpha - cuts[0]) / (cuts[1] - cuts[0]))
            return (1 - amount) * (start_points + lift) + amount * (end_points + settle)
        set_phase("settle")
        amount = smooth((alpha - cuts[1]) / (1 - cuts[1]))
        return end_points + (1 - amount) * settle

    return path


class _LandingChapter:
    WHITE, MUTED, MINT = "#EDF3F7", "#8FA4A7", "#8AE0C8"
    BLUE, ORANGE = "#67BEFF", "#FFB36B"

    def __init__(self, scene, start):
        self.scene, self.start = scene, float(start)
        self.samples, self.routes = [], []
        self.token_views, self.context_obstacles = {}, {}
        self.active_formula, self.stage, self.phase, self.watch = None, "position", "hold", None
        self.driver = VectorizedPoint().set_opacity(0)
        self.driver.add_updater(lambda _: self.sample(), call=False)

    def label(self, text, x, y, size=28, color=None):
        return self.scene.cn(text, size=size, color=color or self.WHITE).move_to([x, y, 0])

    def equation(self, latex, tokens):
        groups = [r"\frac{gt^2}{2}", r"\frac{gT^2}{2}", "gT^2", "T^2", "2h", r"\frac{2h}{g}"]
        result = SemanticFormula(latex, tokens=tokens, font_size=90, isolate=groups,
                                 colors={key: self.MINT for key in ("height", "time") if key in tokens})
        result.shift(np.array([1.6, FORMULA_Y, 0]) - result.tag("eq").get_center())
        return result

    def until(self, local):
        self.scene.until(self.start + local)

    def activate(self, formula):
        self.active_formula = formula
        self.token_views = {key: formula.tag(key) for key in formula.semantic_ids}

    @staticmethod
    def part(formula, selector):
        text, index = selector if isinstance(selector, tuple) else (selector, 0)
        parts = formula.get_parts_by_tex(text)
        if index >= len(parts) or not parts[index].family_members_with_points():
            raise ValueError(f"Missing native coarse formula part: {selector}")
        return parts[index]

    def sample(self):
        if self.active_formula is None:
            return
        record = {"time": round(float(self.scene.get_time()), 6),
                  "local_time": round(float(self.scene.get_time()) - self.start, 6),
                  "stage": self.stage, "phase": self.phase, "tokens": {}, "pairs": []}
        for key, part in self.token_views.items():
            record["tokens"][key] = {"center": part.get_center().tolist(), "bbox": _bbox(part),
                                      "width": float(part.get_width()), "height": float(part.get_height()),
                                      "opacity": _opacity(part)}
        if self.watch:
            moving, obstacles, direction, name = self.watch
            box, opacity = _bbox(moving), _opacity(moving)
            record["moving"] = {"name": name, "bbox": box, "opacity": opacity,
                                 "title_clearance": TITLE_Y - box[3]}
            for identity, obstacle in obstacles.items():
                other = _bbox(obstacle)
                clearance = box[2] - other[3] if direction == "above" else other[2] - box[3]
                record["pairs"].append({"name": f"{name}-vs-{identity}", "moving_bbox": box,
                    "obstacle_bbox": other, "moving_opacity": opacity, "obstacle_opacity": _opacity(obstacle),
                    "overlap": _overlap(box, other), "corridor_clearance": clearance,
                    "corridor_required": CORRIDOR_GAP if self.phase == "across" and direction != "straight"
                                         and identity not in self.context_obstacles else None})
        self.samples.append(record)

    def transition(self, target, stage, groups, *, mover=None, durations=None, direction="straight", extras=()):
        """Move disjoint live native coarse views, retaining fine glyph colors.

        Full fractions include their rule. No Tex rebuild, recoloring, shape
        fallback or shared atom arc is used.
        """
        source = self.active_formula
        if stage == "relocated_term":
            for identity in ("height", "eq"):
                target.tag(identity).move_to(source.tag(identity).get_center())
        pairs = [(name, self.part(source, left), self.part(target, right)) for name, left, right in groups]
        self.stage, self.phase = stage, "straight"
        occupied_source, occupied_target = set(), set()
        for _, left, right in pairs:
            a = {id(glyph) for glyph in left.family_members_with_points()}
            b = {id(glyph) for glyph in right.family_members_with_points()}
            if a & occupied_source or b & occupied_target:
                raise ValueError("Coarse motion groups must not overlap")
            occupied_source |= a
            occupied_target |= b
        obstacles = {name: left for name, left, _ in pairs if name != mover}
        animations = []
        for name, left, right in pairs:
            options = {}
            if name == mover:
                if direction != "straight":
                    boxes = [_bbox(part) for identity, a, b in pairs if identity != mover for part in (a, b)]
                    lane = _lane(_bbox(left), _bbox(right), boxes, direction)
                    options["path_func"] = _lane_path(left.get_center(), right.get_center(), lane, durations,
                                                      lambda phase: setattr(self, "phase", phase))
                    self.routes.append({"stage": stage, "mover": name, "direction": direction,
                                        "lane_y": lane, "durations": list(durations), "gap": CORRIDOR_GAP})
                self.watch = (left, {**obstacles, **self.context_obstacles}, direction, name)
            if stage != "relocated_term" or name not in {"height", "eq"}:
                animations.append(Transform(left, right, rate_func=linear, **options))
        # Zero/minus, the old fraction rule and old exponent fade in place.
        duration = sum(durations)
        fade_early = lambda alpha: smooth(min(1., alpha * duration / min(.2, duration)))
        animations += [FadeOut(glyph, rate_func=fade_early) for glyph in source.family_members_with_points() if id(glyph) not in occupied_source]
        animations += [FadeIn(glyph) for glyph in target.family_members_with_points() if id(glyph) not in occupied_target]
        animations += list(extras)
        self.sample()
        self.scene.play(*animations, run_time=duration)
        # Animation wrappers can be top-level scene objects. Remove their native
        # families before restoring the exact target's fine semantic structure.
        self.scene.remove(source, *(animation.mobject for animation in animations))
        self.scene.add(target)
        self.activate(target)
        self.watch, self.phase = None, "hold"
        self.sample()

    def write_report(self):
        pairs = [pair for sample in self.samples for pair in sample["pairs"]]
        violations = [pair for pair in pairs if pair["overlap"]
                      or (pair["corridor_required"] is not None and pair["corridor_clearance"] < CORRIDOR_GAP - 1e-5)]
        moving = [sample["moving"] for sample in self.samples if "moving" in sample]
        report = {"samples": self.samples, "routes": self.routes, "start": self.start, "duration": 20,
                  "summary": {"pair_violations": len(violations),
                              "opacity_violations": sum(entry["opacity"]["min"] < .98 for entry in moving),
                              "title_violations": sum(entry["title_clearance"] < .02 for entry in moving),
                              "moving_opacity_min": min((entry["opacity"]["min"] for entry in moving), default=None),
                              "title_clearance_min": min((entry["title_clearance"] for entry in moving), default=None)},
                  "writer": "Actual ManimGL landing chapter sampler", "consumers": ["reviewer", "refinement packager"],
                  "lifecycle": "This chapter render and semantic native glyph identities",
                  "invalidation": "Chapter, component, TeX, geometry, time or render change"}
        with (self.scene.out / "motion-samples.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)

    def play(self, previous_page):
        scene = self.scene
        scene.add(self.driver)
        header = Group(self.label("03", -6.42, 3.35, 28, self.MINT),
                       self.label("落地时间从哪里来？", -1.55, 3.35, 44),
                       self.label("03 / 06", 6.02, 3.35, 24, self.MUTED),
                       Line([-6.65, TITLE_Y, 0], [6.65, TITLE_Y, 0], stroke_color="#304458", stroke_width=1.2))
        x, bottom, top = -4.3, -1.35, 1.85
        ground = Line([-6.1, bottom, 0], [-2.35, bottom, 0], stroke_color=self.MUTED, stroke_width=1.5)
        axis = Arrow([x, bottom - .12, 0], [x, 2.08, 0], buff=0, stroke_width=1.4, fill_color=self.MUTED, thickness=1.4)
        height_lines = VGroup(Line([-5.65, bottom, 0], [-5.65, top, 0]),
                              Line([-5.77, bottom, 0], [-5.53, bottom, 0]), Line([-5.77, top, 0], [-5.53, top, 0])).set_stroke(self.MINT, 2)
        height_brace = Group(height_lines, scene.formula("h", size=46, color=self.MINT).move_to([-5.98, .25, 0]))
        blue = Dot([x, top, 0], radius=.105, fill_color=self.BLUE)
        orange = Circle(radius=.155, stroke_color=self.ORANGE, stroke_width=3, fill_opacity=0).move_to([x, top, 0])
        trace = Line([x, top, 0], [x, top - .001, 0], stroke_color=self.MINT, stroke_width=3, stroke_opacity=.32)
        clock = scene.number(0, size=38, decimals=2).move_to([-4.45, -2.35, 0])
        clock_label = scene.formula(r"t=", size=36).move_to([-5.18, -2.35, 0])
        units = scene.formula(r"\mathrm{s}", size=32).move_to([-3.85, -2.35, 0])
        model_label = self.label("共同竖直投影", -4.3, 2.35, 27, self.MINT)
        condition = scene.formula(r"h>0,\quad g>0", size=28, color=self.MUTED).move_to([2.9, -2.85, 0])
        position_label = self.label("竖直位置", 2.9, 1.86, 28, self.MUTED)
        y_label = scene.formula("y", size=33).move_to([x + .28, 2.0, 0])
        permanent = [header, ground, axis, height_brace, blue, orange, trace, clock, clock_label, units, model_label, condition, y_label]
        base = Group(*permanent, position_label)
        opening = [FadeIn(base)] + ([FadeOut(previous_page)] if previous_page is not None else [])
        scene.play(*opening, run_time=.6)

        tokens0 = {"position": "y", "eq": "=", "height": "h", "gravity": "g", "time": "t",
                   "power": ("2", 0), "factor": ("2", 1), "minus": "-"}
        tokens1 = {**tokens0, "position": "0", "time": "T"}
        tokens2 = {key: value for key, value in tokens1.items() if key not in {"position", "minus"}}
        tokens4 = {key: value for key, value in tokens2.items() if key != "power"}
        tokens4["factor"] = ("2", 0)
        formulas = [self.equation(latex, tokens) for latex, tokens in [
            (r"y=h-\frac{gt^2}{2}", tokens0), (r"0=h-\frac{gT^2}{2}", tokens1),
            (r"\frac{gT^2}{2}=h", tokens2), (r"gT^2=2h", tokens2),
            (r"T^2=\frac{2h}{g}", tokens2), (r"T=\sqrt{\frac{2h}{g}}", tokens4)]]
        self.until(1)
        self.activate(formulas[0])
        scene.play(FadeIn(formulas[0]), run_time=.8)
        scene.play(Indicate(height_brace, color=self.MINT, scale_factor=1.04),
                   Indicate(formulas[0].tag("height"), color=self.MINT, scale_factor=1.12), run_time=.6)
        scene.mark("vertical_equation_linked")
        self.until(3)

        def fall(_, alpha):
            y = top - (top - bottom) * alpha * alpha
            blue.move_to([x, y, 0])
            orange.move_to([x, y, 0])
            trace.put_start_and_end_on(np.array([x, top, 0]), np.array([x, min(y, top - .001), 0]))
            clock.set_value(alpha)

        scene.play(UpdateFromAlphaFunc(blue, fall), run_time=4, rate_func=linear)
        landed = scene.formula("y=0", size=40, color=self.MINT).move_to([-3.3, bottom + .27, 0])
        ring = Circle(radius=.23, stroke_color=self.MINT, stroke_width=2.5).move_to([x, bottom, 0])
        scene.play(ShowCreation(ring), FadeIn(landed), run_time=.4)
        self.transition(formulas[1], "ground_condition", [("fraction", r"\frac{gt^2}{2}", r"\frac{gT^2}{2}"),
                        ("height", "h", "h"), ("eq", "=", "="), ("minus", "-", "-")],
                        durations=(.6,), extras=(FadeOut(ring),))
        scene.mark("ground_condition_applied")

        badge1 = Group(self.label("两边同加", 1.72, -1.75, 24, self.MUTED),
                       scene.formula(r"\frac{gT^2}{2}", size=35, color=self.MUTED).move_to([3.42, -1.75, 0]))
        self.until(8.3)
        scene.play(FadeOut(position_label), FadeIn(badge1), run_time=.15)
        self.context_obstacles = {"badge": badge1, "title": header}
        self.transition(formulas[2], "relocated_term", [("fullterm", r"\frac{gT^2}{2}", r"\frac{gT^2}{2}"),
                        ("height", "h", "h"), ("eq", "=", "=")],
                        mover="fullterm", durations=(.2, .45, .25), direction="above")
        scene.mark("term_relocated")

        badge2 = Group(self.label("两边同乘", 1.72, -1.75, 24, self.MUTED),
                       scene.formula("2", size=35, color=self.MUTED).move_to([3.42, -1.75, 0]))
        scene.play(FadeOut(badge1), run_time=.1)
        scene.play(FadeIn(badge2), run_time=.1)
        self.context_obstacles = {"badge": badge2, "title": header}
        self.transition(formulas[3], "twice_height", [("numerator", "gT^2", "gT^2"),
                        ("factor", ("2", 1), ("2", 1)), ("height", "h", "h"), ("eq", "=", "=")],
                        mover="factor", durations=(.18, .34, .18), direction="below")
        scene.mark("height_doubled")

        badge_divide = Group(self.label("两边同除", 1.72, -1.75, 24, self.MUTED),
                             scene.formula("g", size=35, color=self.MUTED).move_to([3.42, -1.75, 0]))
        scene.play(FadeOut(badge2), run_time=.1)
        scene.play(FadeIn(badge_divide), run_time=.1)
        self.context_obstacles = {"badge": badge_divide, "title": header}
        self.transition(formulas[4], "isolated_square", [("square", "T^2", "T^2"),
                        ("gravity", "g", "g"), ("numerator", "2h", "2h"), ("eq", "=", "=")],
                        mover="gravity", durations=(.2, .35, .25), direction="below")
        scene.mark("square_time_isolated")

        positive = scene.formula(r"T>0", size=33, color=self.MINT).move_to([4.9, -.85, 0])
        badge3 = self.label("取正根", 2.6, -1.75, 25, self.MUTED)
        scene.play(FadeOut(badge_divide), run_time=.15)
        scene.play(FadeIn(badge3), FadeIn(positive), run_time=.15)
        self.until(11.7)
        self.context_obstacles = {"badge": badge3, "positive": positive, "title": header}
        self.transition(formulas[5], "positive_root", [("radicand", r"\frac{2h}{g}", r"\frac{2h}{g}"),
                        ("time", "T", "T"), ("eq", "=", "=")], mover="radicand", durations=(1.3,))
        scene.mark("landing_time_derived")

        params = scene.formula(r"h=5\,\mathrm{m},\qquad g=10\,\mathrm{m/s^2}", size=30,
                               color=self.MUTED).move_to([2.65, -1.55, 0])
        check = scene.formula(r"T=1.00\,\mathrm{s}", size=49, color=self.MINT).move_to([2.65, -2.25, 0])
        self.until(13.6)
        scene.play(FadeOut(badge3), run_time=.3)
        self.until(14.4)
        scene.play(FadeIn(params), run_time=.4)
        scene.play(FadeIn(check), run_time=.6)
        self.until(20)
        self.sample()
        page = Group(*permanent, landed, formulas[5], positive, params, check)
        scene.add(page)
        scene.current_page = page
        return page


def play_landing_derivation(scene, *, start=0, previous_page=None):
    """Play exactly 20 local seconds and return this chapter's visible page Group.

    All until targets and samples use start; mark stays the caller's global API.
    No caller label/equation/update_mobjects or other chapter fields are changed.
    """
    if not math.isfinite(start) or start < 0 or abs(scene.get_time() - start) > 1e-5:
        raise ValueError("Call the landing chapter at its declared absolute start")
    chapter = _LandingChapter(scene, start)
    try:
        return chapter.play(previous_page)
    finally:
        chapter.driver.clear_updaters()
        scene.remove(chapter.driver)
        chapter.write_report()


class FormulaDerivation(VisualLessonScene):
    default_camera_config = {"background_color": "#101416"}

    def construct(self):
        play_landing_derivation(self)
