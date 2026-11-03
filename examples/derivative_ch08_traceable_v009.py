"""CH08 v009 independent-module formula continuity over frozen v004 geometry.

Writer: 01a19f93-c389-7732-b292-5b8fc1d74f50. Consumers: native tests,
render runtime and independent reviewers. Roles/actors live for one construct;
source, clock, geometry or wording changes invalidate their journal/evidence.
Frozen once rendered; later revisions require new modules.
No review, sound, publication or remote authority.
"""

import math

from manimlib import FadeIn, FadeOut, Group, RIGHT, Transform, UpdateFromAlphaFunc, VGroup, ValueTracker, linear

from derivative_ch08_optimization_v004 import DerivativeCh08OptimizationV004
from derivative_ch08_optimization import dimensions, feasible, volume
from derivative_chapter_shared import ACCENT, CURVE, INK, MUTED, RATE


AUTHOR_AGENT = "01a19f93-c389-7732-b292-5b8fc1d74f50"

REWRITTEN_ROLES = {
    "dimensions_into_volume": {"length_value", "width_value"},
    "equal_bases_to_square": {"second_equal_base_counts_twice"},
    "positive_domain": {"positive_lower_bound", "base_positive_solves_upper_bound"},
    "product_rule_sources": {"differentiate_height", "differentiate_square"},
    "outer_square_derivative": {"differentiate_x_to_one", "inner_function_derivative"},
    "inner_derivative": {"inner_derivative_is_negative_two"},
    "chain_coefficients_collect": {"positive_outer_two_times_negative_inner_two", "two_times_two_and_retained_x"},
    "extract_common_factor": {"square_leaves_one_base"},
    "combine_remainder": {"twelve_minus_two_x_minus_four_x"},
    "factor_signed_constants": {"minus_two_from_first_linear_factor", "first_linear_factor_root_six", "minus_six_from_second_linear_factor", "second_linear_factor_root_two"},
    "two_negatives_and_factor_order": {"negative_times_negative_positive_twelve"},
    "factors_to_candidates": {"zero_of_x_minus_two", "zero_of_x_minus_six"},
    "feasible_candidate": set(),
    "optimum_substitution": {"objective_base_before_input_replacement"},
    "optimum_evaluation": {"base_eight_squared"},
}


class RoleGroup(VGroup):
    """Authored mathematical roles, never inferred from equal glyph strings."""

    def __init__(self, parts):
        self.parts = dict(parts)
        if len(self.parts) != len(parts):
            raise ValueError("Roles must be unique within their expression")
        super().__init__(*self.parts.values())

    def role(self, name):
        return self.parts[name]


class DerivativeCh08TraceableV009(DerivativeCh08OptimizationV004):
    def atom(self, tex, role, size=36, color=INK):
        obj = self.put(tex, size=size, color=color)
        obj.math_role = role
        return obj

    def square(self, role, size=36):
        base = self.atom(r"(12-2x)", role + ".base", size, CURVE)
        count = self.atom("2", role + ".multiplicity", size * .62, CURVE)
        count.move_to(base.get_right() + [.10, .22, 0])
        return RoleGroup([("base", base), ("count", count)])

    def substituted_square(self, size=36):
        body = self.row([("fixed_base", r"(12-2\cdot", CURVE), ("input", "2", ACCENT),
                         ("close", ")", CURVE)], 0, 0, size)
        count = self.atom("2", "substitution.square_multiplicity", size * .62, CURVE)
        count.move_to(body.get_right() + [.10, .22, 0])
        return RoleGroup([("body", body), ("count", count)])

    def row(self, values, x, y, size=36, width=12.4):
        parts = []
        for role, tex, *color in values:
            obj = tex if isinstance(tex, VGroup) else self.atom(tex, role, size, color[0] if color else INK)
            parts.append((role, obj))
        result = RoleGroup(parts)
        result.arrange(RIGHT, buff=.10)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def at(self, offset, *animations, **kwargs):
        self.until(self._cue["start"] + offset, *animations, **kwargs)

    def retire(self, *objects):
        self.remove(*objects)
        for obj in objects:
            obj.clear_updaters()
            obj.set_opacity(0)

    def transfer(self, stage, target, pairs, start, end, *, consume=(), syntax=(), discard=()):
        """Move exact source-role copies, then install one target, without ghosts.

        Repeated destinations are explicit many-to-one algebra, not matching.
        Consumed parents are removed BEFORE adding their moving role copies.
        """
        self.at(start)
        source_centers = [source.get_center().tolist() for _, source, _ in pairs]
        actors = [source.copy() for _, source, _ in pairs]
        retired = [obj.copy() for obj in discard]
        self.retire(*consume)
        if consume:
            self.add(*actors)
        self.add(*retired)
        driver = Group()

        def record(_):
            self.sample("ch08_role_transfer", stage=stage,
                        roles=[role for role, _, _ in pairs],
                        moving=[obj.get_center().tolist() for obj in actors],
                        sources=source_centers,
                        targets=[dest.get_center().tolist() for _, _, dest in pairs],
                        retained_source=not bool(consume),
                        active_parent_retired_before_motion=bool(consume))

        record(driver)
        driver.add_updater(record)
        self.add(driver)
        span = end-start
        rewritten = REWRITTEN_ROLES[stage]
        parallel = stage in {"inner_derivative","combine_remainder","two_negatives_and_factor_order","feasible_candidate","optimum_evaluation"}
        opening = [*(FadeOut(obj) for obj in retired), *(FadeIn(obj) for obj in syntax if not parallel)]
        self.at(start+.08*span,*opening) if opening else self.at(start+.08*span)
        installed = []
        def affine(actor,role,dest):
            original = actor.copy()
            a,b = original.get_center(),dest.get_center()
            scale = min(dest.get_width()/max(original.get_width(),.001),dest.get_height()/max(original.get_height(),.001))
            lift = .65 if stage=="equal_bases_to_square" and role=="height_factor" else 0
            if stage=="two_negatives_and_factor_order":
                lift = {"negative_times_negative_positive_twelve":1.3,"candidate_two_factor":-.65,"candidate_six_factor":.65}[role]
            def move(mob,alpha):
                point=(1-alpha)*a+alpha*b
                point[1]+=lift*math.sin(math.pi*alpha)
                mob.become(original.copy().scale(1+alpha*(scale-1)).move_to(point))
            return UpdateFromAlphaFunc(actor,move)
        if parallel:
            self.at(end-.24,*(affine(actor,role,dest) for actor,(role,_,dest) in zip(actors,pairs,strict=True)),rate_func=linear)
            changed=[actor for actor,(role,_,_) in zip(actors,pairs,strict=True) if role in rewritten]
            self.at(end-.12,*(FadeOut(obj) for obj in changed)) if changed else self.at(end-.12)
            self.retire(*changed)
            new=[dest for role,_,dest in pairs if role in rewritten]
            self.at(end,*(FadeIn(obj) for obj in [*new,*syntax])) if new or syntax else self.at(end)
            installed.extend(new)
        else:
            for index,(actor,(role,_,dest)) in enumerate(zip(actors,pairs,strict=True)):
                self.add(actor)
                finish = start + span*(.08+.92*(index+1)/len(actors))
                self.at(finish-2/self.camera.fps,affine(actor,role,dest),rate_func=linear)
                if role in rewritten or any(obj is dest for obj in installed):
                    self.at(finish-1/self.camera.fps,FadeOut(actor))
                    self.retire(actor)
                    if not any(obj is dest for obj in installed):
                        self.at(finish,FadeIn(dest))
                    else:
                        self.at(finish)
                else:
                    self.at(finish)
                    self.remove(actor)
                    self.add(dest)
                actor.move_to(dest.get_center())
                self.remove(actor)
                if not any(obj is dest for obj in installed):
                    installed.append(dest)
        record(driver)
        driver.clear_updaters()
        self.remove(driver, *actors, *retired, *syntax, *installed)
        self.add(target)
        self.sample("ch08_role_complete", stage=stage, roles=[r for r, _, _ in pairs])
        self.mark(stage + "_complete")

    def objective(self, cue):
        self.begin_chapter(cue)
        box = self.panels(2, math.pi / 2)
        length = self.row([("name", r"\ell="), ("value", r"12-2x", CURVE)], 2.0, 2.25, 33, 2.7)
        width = self.row([("name", "w="), ("value", r"12-2x", CURVE)], 4.8, 2.25, 33, 2.7)
        height = self.row([("name", "h="), ("value", "x", ACCENT)], 3.5, 1.55, 33, 2.8)
        note = self.label("长度用 cm；h 是盒高", -3.3, 1.8, size=24, color=MUTED, width=5.7)
        scope = self.label("形状取 x = 2 示意；尺寸式适用于任意可行 x", -3.3, -2.6, size=23, color=MUTED, width=5.7)
        self.at(2.34, FadeIn(box), FadeIn(length), FadeIn(width), FadeIn(height), FadeIn(note), FadeIn(scope))
        self.mark("dimensions_to_volume_ready")
        self.focus_begin("dimensions_to_volume")
        self.at(15.55)
        self.focus_end("dimensions_to_volume")
        general = self.row([("lhs", "V="), ("length", r"\ell", CURVE), ("dot1", r"\cdot"),
                            ("width", "w", CURVE), ("dot2", r"\cdot"), ("height", "h", ACCENT)], -3.3, 2.4, 36, 5.7)
        self.at(16.0, FadeIn(general))
        self.focus_begin("volume_objective")
        expanded = self.row([("lhs", "V="), ("length", r"(12-2x)", CURVE), ("dot1", r"\cdot"),
                             ("width", r"(12-2x)", CURVE), ("dot2", r"\cdot"), ("height", "x", ACCENT)], 3.5, -.70, 32, 5.7)
        self.transfer("dimensions_into_volume", expanded,
                      [("length_value", length.role("value"), expanded.role("length")),
                       ("width_value", width.role("value"), expanded.role("width")),
                       ("box_height", height.role("value"), expanded.role("height"))], 17.0, 19.0,
                      syntax=[expanded.role(k) for k in ("lhs", "dot1", "dot2")])
        objective = self.row([("lhs", "V="), ("height", "x", ACCENT), ("square", self.square("base_square", 38))], 3.5, -.70, 38, 5.7)
        self.transfer("equal_bases_to_square", objective,
                      [("second_equal_base_counts_twice", expanded.role("width"), objective.role("square").role("count")),
                       ("one_base", expanded.role("length"), objective.role("square").role("base")),
                       ("height_factor", expanded.role("height"), objective.role("height")),
                       ("volume_identity", expanded.role("lhs"), objective.role("lhs"))],
                      20.0, 23.0, consume=[expanded], discard=[expanded.role("dot1"), expanded.role("dot2")])
        self.mark("volume_objective_ready")
        units = self.put(r"\mathrm{cm}\cdot\mathrm{cm}\cdot\mathrm{cm}=\mathrm{cm}^3", 3.5, -1.4, size=30, color=CURVE, width=5.6)
        self.at(27.0, FadeIn(units))
        self.at(36.5)
        self.focus_end("volume_objective")
        self.focus_begin("physical_domain")
        positive = self.row([("height", "x", ACCENT), ("height_positive", ">0,"),
                             ("base", "12-2x", CURVE), ("base_positive", ">0")], 3.5, -2.15, 31, 5.6)
        self.at(39.0,FadeIn(positive))
        self.mark("positive_dimensions_complete")
        domain = self.row([("lower", "0<"), ("input", "x", ACCENT), ("upper", "<6"),
                           ("unit", r"(\mathrm{cm})")], 3.5, -2.95, 34, 5.6)
        self.transfer("positive_domain", domain,
                      [("positive_cut", positive.role("height"), domain.role("input")),
                       ("positive_lower_bound", positive.role("height_positive"), domain.role("lower")),
                       ("base_positive_solves_upper_bound", VGroup(positive.role("base"), positive.role("base_positive")), domain.role("upper"))],
                      41.3, 43.8, syntax=[domain.role("unit")])
        self.mark("physical_domain_ready")
        self.end_chapter()

    def optimize(self, cue):
        self.begin_chapter(cue)
        source = self.row([("lhs", "V="), ("height", "x", ACCENT), ("square", self.square("objective_square"))], 0, 2.5, 38)
        domain = self.put(r"0<x<6\quad(x:\mathrm{cm},\ V:\mathrm{cm}^3)", 4.8, 2.5, size=25, color=MUTED, width=3.9)
        source.shift([-1.0, 0, 0])
        self.at(1.8, FadeIn(source), FadeIn(domain))
        self.at(2.42)
        self.focus_begin("product_derivative")
        rule = self.row([("lhs", "V'="), ("dx", "(x)'", ACCENT), ("times1", r"\cdot"),
                         ("square", self.square("undifferentiated_square", 32)), ("plus", "+"),
                         ("height", "x", ACCENT), ("times2", r"\cdot"), ("differentiate_square", r"[(12-2x)^2]'", CURVE)], 0, 1.25, 32)
        self.transfer("product_rule_sources", rule,
                      [("differentiate_height", source.role("height"), rule.role("dx")),
                       ("retain_square", source.role("square"), rule.role("square")),
                       ("retain_height", source.role("height"), rule.role("height")),
                       ("differentiate_square", source.role("square"), rule.role("differentiate_square"))], 5.3, 10.4,
                      syntax=[rule.role(k) for k in ("lhs", "times1", "plus", "times2")])
        chain = self.row([("lhs", "V'="), ("one", "1", ACCENT), ("times1", r"\cdot"),
                          ("square", self.square("first_product_square", 32)), ("plus", "+"),
                          ("height", "x", ACCENT), ("times2", r"\cdot"), ("outer", "2", CURVE),
                          ("base", "(12-2x)", CURVE), ("times3", r"\cdot"), ("inner", "(12-2x)'", RATE)], 0, .05, 32)
        self.transfer("outer_square_derivative", chain,
                      [("differentiate_x_to_one", rule.role("dx"), chain.role("one")),
                       ("first_square_stays", rule.role("square"), chain.role("square")),
                       ("second_height_stays", rule.role("height"), chain.role("height")),
                       ("outer_power_rule", source.role("square").role("count"), chain.role("outer")),
                       ("outer_remaining_base", source.role("square").role("base"), chain.role("base")),
                       ("inner_function_derivative", source.role("square").role("base"), chain.role("inner"))], 13.0, 17.1,
                      consume=[rule], syntax=[chain.role(k) for k in ("lhs", "times1", "plus", "times2", "times3")],
                      discard=[rule.role(k) for k in ("lhs","times1","plus","times2","differentiate_square")])
        negative = self.row([("lhs", "V'="), ("one", "1", ACCENT), ("times1", r"\cdot"),
                             ("square", self.square("chain_first_square", 32)), ("plus", "+"),
                             ("height", "x", ACCENT), ("times2", r"\cdot"), ("outer", "2", CURVE),
                             ("base", "(12-2x)", CURVE), ("times3", r"\cdot"), ("inner", "(-2)", RATE)], 0, .05, 32)
        self.transfer("inner_derivative", negative,
                      [("inner_derivative_is_negative_two" if k == "inner" else "stable_" + k, obj, negative.role(k)) for k, obj in chain.parts.items()],
                      18.2, 21.0, consume=[chain])
        compact = self.row([("lhs", "V'="), ("square", self.square("compact_square", 38)), ("minus", "-", RATE),
                            ("coefficient", "4x", ACCENT), ("base", "(12-2x)", CURVE)], 0, -.95, 38)
        self.transfer("chain_coefficients_collect", compact,
                      [("first_square", negative.role("square"), compact.role("square")),
                       ("positive_outer_two_times_negative_inner_two", VGroup(negative.role("outer"), negative.role("inner")), compact.role("minus")),
                       ("two_times_two_and_retained_x", VGroup(negative.role("height"), negative.role("outer"), negative.role("inner")), compact.role("coefficient")),
                       ("retained_second_base", negative.role("base"), compact.role("base"))], 23.0, 26.8,
                      syntax=[compact.role("lhs")])
        self.mark("product_derivative_ready")
        self.at(27.3)
        self.focus_end("product_derivative")
        self.focus_begin("factor_derivative")
        self.at(27.45, FadeOut(negative))
        self.retire(rule, negative)
        common = self.row([("lhs", "V'="), ("common", "(12-2x)", CURVE), ("open", "["),
                           ("remaining_base", "12-2x", CURVE), ("minus", "-", RATE),
                           ("remaining_coefficient", "4x", ACCENT), ("close", "]")], 0, .35, 36)
        self.transfer("extract_common_factor", common,
                      [("common_from_square", compact.role("square").role("base"), common.role("common")),
                       ("same_common_from_second_product", compact.role("base"), common.role("common")),
                       ("square_leaves_one_base", compact.role("square").role("base"), common.role("remaining_base")),
                       ("remaining_negative_sign", compact.role("minus"), common.role("minus")),
                       ("remaining_four_x", compact.role("coefficient"), common.role("remaining_coefficient"))], 27.5, 30.5,
                      syntax=[common.role(k) for k in ("lhs", "open", "close")])
        reduced = self.row([("lhs", "V'="), ("base", "(12-2x)", CURVE), ("remainder", "(12-6x)", ACCENT)], 0, .35, 38)
        self.transfer("combine_remainder", reduced,
                      [("common_stays", common.role("common"), reduced.role("base")),
                       ("twelve_minus_two_x_minus_four_x", VGroup(common.role("remaining_base"), common.role("minus"), common.role("remaining_coefficient")), reduced.role("remainder"))],
                      30.7, 32.8, consume=[common], syntax=[reduced.role("lhs")], discard=[common.role("open"), common.role("close")])
        self.at(33.0,FadeOut(compact))
        self.retire(compact)
        split = self.row([("lhs", "V'="), ("constant1", "(-2)", RATE), ("root6", "(x-6)", CURVE),
                          ("constant2", "(-6)", RATE), ("root2", "(x-2)", ACCENT)], 0, -.95, 36)
        self.transfer("factor_signed_constants", split,
                      [("minus_two_from_first_linear_factor", reduced.role("base"), split.role("constant1")),
                       ("first_linear_factor_root_six", reduced.role("base"), split.role("root6")),
                       ("minus_six_from_second_linear_factor", reduced.role("remainder"), split.role("constant2")),
                       ("second_linear_factor_root_two", reduced.role("remainder"), split.role("root2"))], 33.1, 35.8,
                      syntax=[split.role("lhs")])
        self.at(35.95,FadeOut(reduced))
        self.retire(reduced)
        factored = self.row([("lhs", "V'="), ("positive12", "12", RATE), ("root2", "(x-2)", ACCENT),
                             ("root6", "(x-6)", CURVE)], 0, -.95, 40)
        self.transfer("two_negatives_and_factor_order", factored,
                      [("negative_times_negative_positive_twelve", VGroup(split.role("constant1"), split.role("constant2")), factored.role("positive12")),
                       ("candidate_two_factor", split.role("root2"), factored.role("root2")),
                       ("candidate_six_factor", split.role("root6"), factored.role("root6"))],
                      36.0, 38.9, consume=[split], syntax=[factored.role("lhs")])
        self.mark("factor_derivative_ready")
        two=self.row([("meaning","x="),("value","2",ACCENT)],0,0,34)
        six=self.row([("meaning","x="),("value","6",CURVE)],0,0,34)
        roots = self.row([("zero", "V'=0:"), ("two", two), ("separator", ","), ("six", six)], 0, -1.9, 34)
        self.transfer("factors_to_candidates", roots,
                      [("zero_of_x_minus_two", factored.role("root2"), roots.role("two")),
                       ("zero_of_x_minus_six", factored.role("root6"), roots.role("six"))], 39.0, 41.8,
                      syntax=[roots.role("zero"), roots.role("separator")])
        rejected = self.put(r"6\notin(0,6):\ 12-2\cdot6=0", 0, -2.7, size=29, color=RATE)
        self.at(43.4, FadeIn(rejected))
        candidate_center=roots.role("two").get_center()
        candidate = self.row([("meaning","x="),("value","2",ACCENT)],float(candidate_center[0]),float(candidate_center[1]),34)
        self.transfer("feasible_candidate", candidate,
                      [("candidate_equation_identity", roots.role("two").role("meaning"), candidate.role("meaning")),
                       ("only_interior_candidate", roots.role("two").role("value"), candidate.role("value"))],
                      44.0, 46.4, consume=[roots], discard=[roots.role("zero"), roots.role("six"), roots.role("separator")])
        self.mark("root_candidates_ready")
        self.at(47.3)
        self.focus_end("factor_derivative")
        self.at(47.55, FadeOut(rejected))
        self.retire(compact, reduced, rejected)
        self.at(47.8, factored.animate.move_to([-1, 1.25, 0]), candidate.animate.move_to([5.2, 1.25, 0]))
        self.at(47.82)
        self.focus_begin("volume_peak")
        sign_left = self.put(r"0<x<2:\quad(-)\cdot(-)\Rightarrow V'>0", 0, .35, size=34)
        sign_right = self.put(r"2<x<6:\quad(+)\cdot(-)\Rightarrow V'<0", 0, -.40, size=34)
        summary = self.label("整个可行域先增后减，x = 2 取得最大体积", 0, -1.15, size=29)
        self.at(50.7, FadeIn(sign_left))
        self.at(55.2, FadeIn(sign_right))
        self.at(58.5, FadeIn(summary))
        self.at(60.5,sign_left.animate.set_width(5.2).move_to([-3.6,1.2,0]),
                sign_right.animate.set_width(5.2).move_to([-3.6,.35,0]),
                summary.animate.set_width(5.2).move_to([-3.6,-.5,0]),FadeOut(factored))
        self.retire(factored)
        substitution = self.row([("lhs", "V(2)="), ("height", "2", ACCENT), ("base", self.substituted_square())], 3.1, -1.1, 36,5.7)
        self.transfer("optimum_substitution", substitution,
                      [("selected_cut_enters_height", candidate.role("value"), substitution.role("height")),
                       ("objective_base_before_input_replacement", source.role("square").role("base"), substitution.role("base").role("body").role("fixed_base")),
                       ("same_selected_cut_enters_base_input", candidate.role("value"), substitution.role("base").role("body").role("input")),
                       ("square_multiplicity_stays", source.role("square").role("count"), substitution.role("base").role("count"))], 61.0, 63.5,
                      syntax=[substitution.role("lhs"), substitution.role("base").role("body").role("close")])
        evaluated = self.row([("lhs", "V(2)="), ("height", "2", ACCENT), ("times", r"\times"),
                              ("base", "8^2", CURVE)], 3.1, -1.1, 38,5.7)
        self.transfer("optimum_evaluation", evaluated,
                      [("height_at_two", substitution.role("height"), evaluated.role("height")),
                       ("base_eight_squared", substitution.role("base"), evaluated.role("base"))], 63.6, 65.6,
                      consume=[substitution], syntax=[evaluated.role("lhs"), evaluated.role("times")])
        result = self.put(r"=128\ \mathrm{cm}^3", 3.1, -2.1, size=38, color=CURVE)
        self.at(67.5, FadeIn(result))
        self.mark("volume_peak_ready")
        self.end_chapter()

    def closing(self, cue):
        self.begin_chapter(cue)
        faces = self.panels(2, math.pi / 2)
        original_condition = self.label("原条件：无额外高度下限", 3.5, 2.65, size=26, width=5.7)
        original_result = self.put(r"x=2\ \mathrm{cm},\quad V=128\ \mathrm{cm}^3", 3.5, 2, size=34, color=CURVE, width=5.7)
        original_dimensions = self.put(r"8\times8\times2\ \mathrm{cm}", 3.5, 1.1, size=35, width=5.7)
        self.beat(.13, FadeIn(faces), FadeIn(original_condition), FadeIn(original_result), FadeIn(original_dimensions),
                  FadeIn(self.label("尺寸 → 同一变量 → 目标与可行域", 3.5, -.1, size=27, width=5.7)),
                  FadeIn(self.label("变化率 → 单调性 → 全范围比较", 3.5, -1, size=27, width=5.7)))
        self.sample("closing_binding", x_cm=2, min_height_cm=0, dimensions_cm=dimensions(2), volume_cm3=volume(2), feasible=True)
        self.mark("chapter_chain_ready")
        self.focus_begin("chapter_chain")
        self.beat(.70)
        self.focus_end("chapter_chain")
        self.beat(.78, FadeIn(self.label("约束改变，沿同一模型重新判断", 3.5, -2.25, size=28, color=ACCENT, width=5.7)))
        self.mark("feasibility_transfer_ready")
        self.focus_begin("feasibility_transfer")
        rejected = self.label("旧解 x = 2：高度不足，排除", 3.5, 1.1, size=27, color=RATE, width=5.7)
        self.at(29.15)
        self.at(29.30, FadeOut(original_condition), FadeOut(original_result), FadeOut(original_dimensions))
        self.retire(original_condition, original_result, original_dimensions)
        self.mark("closing_old_values_cleared")
        self.at(29.55, FadeIn(self.label("当前条件：盒高至少 3 cm", 3.5, 2.65, size=26, width=5.7)),
                FadeIn(self.put(r"3\leq x<6\quad(\mathrm{cm})", 3.5, 2, size=34, color=ACCENT, width=5.7)), FadeIn(rejected))
        self.mark("closing_old_solution_excluded")
        x, driver = ValueTracker(2), Group()

        def update(_):
            size = x.get_value()
            faces.become(self.panels(size, math.pi / 2))
            self.sample("closing_binding", x_cm=size, min_height_cm=3, dimensions_cm=dimensions(size), volume_cm3=volume(size), feasible=feasible(size, 3))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.at(30.1)
        self.at(30.5,FadeOut(rejected))
        self.retire(rejected)
        relocated = self.label("旧解 x = 2：高度不足，排除", -3.3, -2.3, size=27, color=RATE, width=5.7)
        self.at(31.4,FadeIn(relocated))
        self.mark("closing_rejection_relocated")
        self.at(32.4)
        self.at(32.8, x.animate.set_value(3), rate_func=linear)
        self.mark("closing_current_box_ready")
        self.at(33.0, FadeIn(self.put(r"x=3\ \mathrm{cm},\quad V=108\ \mathrm{cm}^3", 3.5, 1.15, size=32, color=CURVE, width=5.7)),
                FadeIn(self.put(r"6\times6\times3\ \mathrm{cm}", 3.5, .4, size=31, width=5.7)))
        self.mark("closing_current_optimum_ready")
        self.end_chapter()
        driver.clear_updaters()


class DerivativeCh08TraceableProbeV009(DerivativeCh08TraceableV009):
    """Diagnostic only: reuse the exact three changed methods and local clocks."""

    def construct(self):
        if tuple(c["id"] for c in self.cues) not in (("objective", "optimize", "closing"),("objective","optimize"),("objective",),("closing",)):
            raise ValueError("Probe must contain exactly the three revised methods")
        self.motion_samples = []
        for cue in self.cues:
            self.until(cue["start"])
            getattr(self, cue["id"])(cue)
