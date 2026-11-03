"""Narrow CH07 candidate/substitution bridges over complete v004 content.

Writer: 01a19f6b-174f-7431-a0fd-2adf59301a9e. Glyph roles and their native
journal live for this construct; renderer/tests/reviewers consume them. Source,
clock or geometry changes invalidate the journal. This scene cannot approve.
"""
from derivative_ch07_extremes_v004 import DerivativeCh07ExtremesV004
from derivative_ch07_extremes import candidates, graph_point, value
from derivative_chapter_shared import ACCENT, CURVE, RATE
from manimind.components.formula_motion import SemanticFormula
from manimlib import Circle, Dot, FadeIn, FadeOut, Group, Transform, VGroup

AUTHOR_AGENT = "01a19f6b-174f-7431-a0fd-2adf59301a9e"


class DerivativeCh07Traceable(DerivativeCh07ExtremesV004):
    def role_formula(self, latex, tokens, x, y, size=32, width=6):
        result = SemanticFormula(latex, tokens=tokens, font_size=size)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def scaffold(self, formula, keys):
        for key in keys:
            formula.tag(key).set_opacity(0)
        self.add(formula)
        return formula

    def transfer_roles(self, origins, target, end, stage):
        self.until(self._cue["start"] + self._cue["animation_starts"][f"{end:.2f}"])
        if any(float(g.get_opacity()) < .95 for part, _ in origins for g in part.family_members_with_points()):
            raise ValueError("Role transfer needs a currently visible source")
        moving = [part.copy() for part, _ in origins]
        destinations = [target.tag(key).copy().set_opacity(1) for _, key in origins]
        driver = Group()

        def sample(_):
            self.sample("traceable_roles", stage=stage,
                moving=[m.get_center().tolist() for m in moving],
                targets=[m.get_center().tolist() for m in destinations])

        sample(driver)
        driver.add_updater(sample)
        self.add(driver, *moving)
        self.beat(end, *(Transform(m, t, path_arc=0) for m, t in zip(moving, destinations)))
        driver.clear_updaters()
        self.remove(driver, *moving)
        for _, key in origins:
            target.tag(key).set_opacity(1)
        self.mark(stage + "_ready")

    def reveal_role(self, formula, key, end):
        self.until(self._cue["start"] + self._cue["animation_starts"][f"{end:.2f}"])
        self.beat(end, FadeIn(formula.tag(key).set_opacity(1)))

    def candidates(self, cue):
        self.begin_chapter(cue)
        domain = self.role_formula(r"x\in[0,3]", {"left": "0", "right": "3"}, -3, 2.6)
        derivative = self.role_formula(r"f'(x)=2(x-1)", {"factor": "x-1"}, 3.5, 2.05, size=39)
        root = self.role_formula(r"f'(x)=0\ \Longrightarrow\ x=1", {"position": "1"}, 3.5, 1.1, size=34)
        self.beat(.12, FadeIn(self.graph()), FadeIn(domain), FadeIn(derivative), FadeIn(root))
        self.mark("interior_candidate_ready")
        self.focus_begin("interior_candidate")
        self.beat(.31)
        self.focus_end("interior_candidate")
        ends = self.role_formula(r"0,\ 3", {"left": "0", "right": "3"}, 4.5, -.1, size=39)
        internal = self.role_formula("1", {"position": "1"}, 4.5, -1.05, size=39)
        self.scaffold(ends, ends.semantic_ids)
        self.scaffold(internal, internal.semantic_ids)
        self.beat(.40, FadeIn(self.label("端点", 2.15, -.1, size=28, color=ACCENT)),
            FadeIn(self.label("内部驻点", 2.15, -1.05, size=28)))
        self.focus_begin("all_candidates")
        self.transfer_roles([(root.tag("position"), "position")], internal, .45, "stationary_to_candidate")
        self.transfer_roles([(domain.tag("left"), "left"), (domain.tag("right"), "right")],
            ends, .41, "domain_to_endpoints")
        points = VGroup(*(Circle(radius=.15).move_to(graph_point(x, value(x))).set_stroke(ACCENT, 3)
            for x in (0, 1, 3)))
        self.beat(.48, FadeIn(points))
        self.mark("all_candidates_ready")
        self.beat(.72)
        self.focus_end("all_candidates")
        self.beat(.81, FadeIn(self.label("本例处处可导，内部极值必在驻点", 3.5, -2.15, size=26, width=5.5)))
        self.mark("candidate_reason_ready")
        self.focus_begin("candidate_reason")
        self.end_chapter()

    def compare(self, cue):
        self.begin_chapter(cue)
        original = self.role_formula(r"f(x)=(x-1)^2", {"rule": "(x-1)^2"}, -3, 2.6, size=32)
        rows = candidates(0, 3)
        positions = [self.role_formula(str(x), {"position": str(x)}, 1.55, 1.2-.9*i, size=36)
            for i, (x, _) in enumerate(rows)]
        calculation_heading = self.label("代回原函数", 3.85, 2.05, size=25, width=3.2)
        self.beat(.13, FadeIn(self.graph()), FadeIn(original),
            FadeIn(self.put("x", 1.55, 2.05, size=32)),
            FadeIn(calculation_heading),
            FadeIn(self.put("f(x)", 6.2, 2.05, size=32)),
            *(FadeIn(p) for p in positions))
        self.focus_begin("candidate_values")
        values = []
        calculations = []
        for i, ((x, y), position) in enumerate(zip(rows, positions)):
            row_y = 1.2-.9*i
            # A stable original rule and three retained calculations avoid
            # confusing a candidate coordinate with its evaluated value.
            calc = self.role_formula(f"({x}-1)^2={y}",
                {"input": (str(x), 0), "result": (str(y), 1 if y == 1 else 0)},
                3.85, row_y, size=32, width=3.4)
            output = self.role_formula(str(y), {"value": str(y)}, 6.2, row_y, size=36)
            self.scaffold(calc, calc.semantic_ids)
            self.scaffold(output, output.semantic_ids)
            self.transfer_roles([(position.tag("position"), "input")], calc, .21+i*.11, f"substitute_{x}")
            self.reveal_role(calc, "result", .23+i*.11)
            self.transfer_roles([(calc.tag("result"), "value")], output, .25+i*.11, f"value_{x}_to_column")
            self.add(Dot(graph_point(x, y), radius=.09, color=ACCENT))
            values.append(output)
            calculations.append(calc)
        self.mark("candidate_values_ready")
        self.beat(.62)
        self.focus_end("candidate_values")
        self.beat(.64, FadeOut(calculation_heading), *(FadeOut(calc) for calc in calculations))
        minimum = self.role_formula(r"\min f=0\quad(x=1)", {"value": "0", "position": "1"}, 3.85, -1.65, size=33)
        maximum = self.role_formula(r"\max f=4\quad(x=3)", {"value": "4", "position": "3"}, 3.85, -2.5, size=33)
        self.scaffold(minimum, minimum.semantic_ids)
        self.scaffold(maximum, maximum.semantic_ids)
        self.focus_begin("closed_extremes")
        self.transfer_roles([(values[1].tag("value"), "value")], minimum, .72, "select_minimum_value")
        self.transfer_roles([(positions[1].tag("position"), "position")], minimum, .74, "minimum_position")
        self.transfer_roles([(values[2].tag("value"), "value")], maximum, .79, "select_maximum_value")
        self.transfer_roles([(positions[2].tag("position"), "position")], maximum, .81, "maximum_position")
        self.mark("closed_extremes_ready")
        self.end_chapter()
