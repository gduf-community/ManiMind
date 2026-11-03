"""Trusted native ManimGL components driven only by validated SceneSpec data.

Render-local state belongs to this scene. The orchestrator supplies an explicit
asset directory; full frame measurements are retained there for independent QA.
"""

import json
from pathlib import Path

import numpy as np
from manimlib import Axes, ValueTracker, Dot, Line, DashedLine, DecimalNumber, Group, Mobject, LEFT, RIGHT

from ..experiments.scene_support import BenchmarkScene, cn, formula, output_dir, INK, CYAN, YELLOW, CORAL, GREEN, MUTED
from .schema import validate_spec, values, polynomial, polynomial_tex
from .geometry import axis_plan, clip_line, audit_frame


class SpecLesson(BenchmarkScene):
    def setup(self):
        super().setup()
        self.spec = validate_spec(json.loads((output_dir() / "scene-spec.json").read_text(encoding="utf-8")))
        self.frame_records = {}
        self.ready_for_audit = False

    def construct(self):
        spec, model = self.spec, self.spec["model"]
        plan = axis_plan(model)
        xmin, xmax, ymin, ymax = plan["plot"]
        axes = Axes(x_range=(0, plan["x_max"], plan["x_step"]), y_range=(0, plan["y_max"], plan["y_step"]),
                    width=xmax - xmin, height=ymax - ymin,
                    axis_config={"include_tip": False, "include_numbers": False, "color": MUTED})
        axes.shift(np.array([xmin, ymin, 0]) - axes.c2p(0, 0))
        origin, corner = axes.c2p(0, 0), axes.c2p(plan["x_max"], plan["y_max"])
        self.mapping = {"origin": list(map(float, origin[:2])), "scale": [float((corner[0] - origin[0]) / plan["x_max"]), float((corner[1] - origin[1]) / plan["y_max"])],
                        "plot": [float(origin[0]), float(corner[0]), float(origin[1]), float(corner[1])]}
        curve = axes.get_graph(lambda t: polynomial(model["coefficients"], t), x_range=(0, plan["x_max"]), color=INK, stroke_width=3)
        labels = {}
        for axis, step, end in [("t", plan["x_step"], plan["x_max"]), ("s", plan["y_step"], plan["y_max"])]:
            for i in range(1, int(end / step + 1e-8) + 1):
                value = i * step
                label = formula(f"{value:g}", size=28, color=MUTED)
                if axis == "t":
                    label.move_to(axes.c2p(value, 0) + np.array([0, -0.28, 0]))
                else:
                    label.move_to(axes.c2p(0, value) + np.array([-0.24, 0, 0]), aligned_edge=RIGHT)
                labels[f"tick_{axis}_{i}"] = label
        labels["axis_t"] = formula(r"t\;/\;\mathrm{s}", size=28, color=CYAN).move_to([-0.05, -2.25, 0])
        labels["axis_s"] = formula(r"s\;/\;\mathrm{m}", size=28, color=YELLOW).move_to([-5.4, 2.05, 0], aligned_edge=LEFT)
        labels["model"] = formula(polynomial_tex(model["coefficients"]), size=34).move_to([3.35, 2.05, 0])
        self.h_tracker = ValueTracker(spec["initial_h"])
        initial = values(model, spec["initial_h"])
        p = axes.c2p(*initial["p"])
        pdot = Dot(p, radius=0.062, fill_color=YELLOW)
        qdot = Dot(axes.c2p(*initial["q"]), radius=0.055, fill_color=CYAN)
        labels["point_p"] = formula("P", size=28, color=YELLOW).move_to(p + np.array([-0.25, 0.27, 0]))
        dt_line = Line(p, axes.c2p(*initial["r"]), color=CYAN, stroke_width=4)
        ds_line = Line(axes.c2p(*initial["r"]), axes.c2p(*initial["q"]), color=YELLOW, stroke_width=4)
        secant = Line(p, axes.c2p(*initial["q"]), color=CORAL, stroke_width=4)
        tdirection = [self.mapping["scale"][0], self.mapping["scale"][1] * initial["tangent_slope"]]
        tangent_ends = clip_line(list(p[:2]), tdirection, self.mapping["plot"])
        tangent = DashedLine(*[np.array([*v, 0]) for v in tangent_ends], color=GREEN, stroke_width=7, dash_length=0.11)
        tangent.set_opacity(0)

        colors = {"delta_t": CYAN, "delta_s": YELLOW, "average_slope": CORAL}
        names = {"delta_t": "时间差", "delta_s": "位移差", "average_slope": "平均速度"}
        symbols = {"delta_t": r"\Delta t", "delta_s": r"\Delta s", "average_slope": r"\bar v"}
        units = {"delta_t": r"\mathrm{s}", "delta_s": r"\mathrm{m}", "average_slope": r"\mathrm{m/s}"}
        self.numbers = {}
        row_y = {}
        for i, row in enumerate(spec["readouts"]):
            key, y = row["bind"], 1.1 - 0.72 * i
            row_y[key] = y
            labels[f"name_{key}"] = cn(names[key], size=28, color=colors[key]).move_to([0.75, y, 0], aligned_edge=LEFT)
            labels[f"symbol_{key}"] = formula(symbols[key] + r"\approx", size=30, color=colors[key]).move_to([2.45, y, 0])
            number = DecimalNumber(initial[key], num_decimal_places=row["decimals"], font_size=32, color=colors[key])
            self.numbers[key] = number
            labels[f"value_{key}"] = number
            labels[f"unit_{key}"] = formula(units[key], size=28, color=colors[key]).move_to([5.18, y, 0], aligned_edge=LEFT)
        labels["ratio"] = formula(r"\bar v=\frac{\Delta s}{\Delta t}", size=38, color=CORAL).move_to([3.4, -1.18, 0])
        labels["secant_legend"] = cn("割线", size=28, color=CORAL).move_to([1.9, -2.16, 0])
        labels["tangent_legend"] = cn("切线", size=28, color=GREEN).move_to([4.65, -2.16, 0])
        secant_key = Line([0.85, -2.16, 0], [1.4, -2.16, 0], color=CORAL, stroke_width=4)
        tangent_key = DashedLine([3.6, -2.16, 0], [4.15, -2.16, 0], color=GREEN, stroke_width=7, dash_length=0.1)
        tangent_key.set_opacity(0)
        labels["tangent_legend"].set_opacity(0)
        emphasis = Line([0.75, 0, 0], [5.95, 0, 0], color=CYAN, stroke_width=1.5)
        self.add(axes, curve, tangent, dt_line, ds_line, secant, pdot, qdot, *labels.values(), secant_key, tangent_key, emphasis)
        self.labels = labels
        self.required_labels = sorted(labels)
        self.tangent = tangent
        self.geom = {"pdot": pdot, "qdot": qdot, "dt": dt_line, "ds": ds_line, "secant": secant}

        def sync(_mob):
            state = values(model, self.h_tracker.get_value())
            q, r = axes.c2p(*state["q"]), axes.c2p(*state["r"])
            qdot.move_to(q)
            dt_line.put_start_and_end_on(p, r)
            ds_line.put_start_and_end_on(r, q)
            ends = clip_line(list(p[:2]), list((q - p)[:2]), self.mapping["plot"])
            secant.put_start_and_end_on(*[np.array([*v, 0]) for v in ends])
            for key, number in self.numbers.items():
                number.set_value(state[key]).move_to([4.9, row_y[key], 0], aligned_edge=RIGHT)

        controller = Mobject()
        controller.add_updater(sync)
        self.add(controller)
        self.ready_for_audit = True
        for index, stage in enumerate(spec["stages"]):
            with self.cue(index, stage["title"]):
                binding = {"interval": "delta_t", "displacement": "delta_s", "ratio": "average_slope", "convergence": "average_slope"}[stage["focus"]]
                emphasis.set_color(colors[binding]).move_to([3.35, row_y[binding] - 0.26, 0])
                if index == 2:
                    self.beat(0.16, tangent.animate.set_opacity(1), tangent_key.animate.set_opacity(1), labels["tangent_legend"].animate.set_opacity(1))
                else:
                    self.beat(0.10)
                self.beat(0.46 if stage["pace"] == "early" else 0.58, self.h_tracker.animate.set_value(stage["h_to"]))
        controller.clear_updaters()

    def update_mobjects(self, dt):
        super().update_mobjects(dt)
        if not self.ready_for_audit:
            return
        boxes = {key: [float(obj.get_left()[0]), float(obj.get_right()[0]), float(obj.get_bottom()[1]), float(obj.get_top()[1])]
                 for key, obj in self.labels.items()}
        line_points = lambda line: [list(map(float, line.get_start()[:2])), list(map(float, line.get_end()[:2]))]
        record = {"frame": round(self.time * self.camera.fps), "time": self.time, "cue": self.cue_index,
                  "h": float(self.h_tracker.get_value()), "boxes": boxes,
                  "readouts": {k: float(v.get_value()) for k, v in self.numbers.items()},
                  "p": list(map(float, self.geom["pdot"].get_center()[:2])), "q": list(map(float, self.geom["qdot"].get_center()[:2])),
                  "r": list(map(float, self.geom["dt"].get_end()[:2])),
                  "increments": {"delta_t": line_points(self.geom["dt"]), "delta_s": line_points(self.geom["ds"])},
                  "secant": line_points(self.geom["secant"]), "tangent": line_points(self.tangent)}
        record["issues"] = audit_frame(record, self.spec["model"], self.mapping, self.required_labels)
        self.frame_records[record["frame"]] = record

    def tear_down(self):
        if self.ready_for_audit:
            records = sorted(self.frame_records.values(), key=lambda r: r["frame"])
            report = {"mapping": self.mapping, "required_labels": self.required_labels, "frames": records,
                      "frames_checked": len(records), "issues": sorted({i for r in records for i in r["issues"]}),
                      "limitations": ["Geometry/label measurements are not OCR or educational-quality approval",
                                      "Invisible future labels reserve space; intentional geometry intersections are allowed"]}
            (output_dir() / "frame-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        super().tear_down()
