"""Native ManimGL rendering and measured frame evidence for component plans.

The wrapper must bind absolute plan_path and asset_dir class attributes. Scene
state lives for one render, is written only by this scene, and is consumed by
the independent reviewer via frame-audit.json. Starting another render replaces
that report; changes to input/source/font invalidate previous evidence. Text
bitmaps are disposable assets, not project facts or collaboration context.

Curves are finite polylines; measurements are native object data, not pixel OCR,
continuity proofs, or teaching-quality approval. No model code is executed.
"""

import json
import math
from pathlib import Path

import numpy as np
from manimlib import (
    Arrow, Axes, DashedLine, Dot, Group, LEFT, Line, RIGHT, Scene, Tex, VMobject,
)

from ..experiments.layout_guard import check_boxes
from .catalog import (COLORS, FONT_INDEX, FONT_MEDIUM_INDEX, FONT_SEMIBOLD_INDEX,
                      NUMBER_FONT_PATH, NUMBER_FONT_INDEX)
from .plan import CompiledShot, validate_plan
from .typography import FONT, FONT_PATH, text_image, RasterNumber, bitmap_colors


FPS = 30
PLOT_REGION = [-5.6, 0.55, -1.95, 2.0]
SIDEBAR = [1.65, 6.2, -2.35, 2.35]
SCREEN = [-6.85, 6.85, -3.85, 3.85]
TOLERANCE = 2e-5  # ManimGL stores native geometry in float32.
AXIS_COLOR, BORDER_COLOR = "#737D89", "#4C5662"


def _box(mobject):
    return [float(mobject.get_left()[0]), float(mobject.get_right()[0]),
            float(mobject.get_bottom()[1]), float(mobject.get_top()[1])]


def _xy(point):
    return list(map(float, point[:2]))


def _close(actual, expected):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    return a.shape == b.shape and np.isfinite(a).all() and np.allclose(
        a, b, atol=TOLERANCE, rtol=1e-7
    )


def _inside(points, bounds, tolerance=TOLERANCE):
    p = np.asarray(points, dtype=float).reshape(-1, 2)
    return bool(np.isfinite(p).all() and
                (p[:, 0] >= bounds[0] - tolerance).all() and
                (p[:, 0] <= bounds[1] + tolerance).all() and
                (p[:, 1] >= bounds[2] - tolerance).all() and
                (p[:, 1] <= bounds[3] + tolerance).all())


def _visible_colors(mobject):
    colors = []
    for member in mobject.get_family():
        if not isinstance(member, VMobject) or not member.has_points():
            continue
        if member.get_fill_opacity() > 0:
            colors.extend(member.get_fill_colors())
        if member.get_stroke_width() > 0 and member.get_stroke_opacity() > 0:
            colors.extend(member.get_stroke_colors())
    return sorted({color.upper() for color in colors} | set(bitmap_colors(mobject)))


def _row_layout(components):
    groups = [[c for c in components if c["kind"] == "formula"],
              [c for c in components if c["kind"] not in {"formula", "readout"}],
              [c for c in components if c["kind"] == "readout"]]
    groups = [group for group in groups if group]
    heights = {"formula": 1.1, "readout": .68}
    gap = .34
    total = sum(heights.get(c["kind"], .47) for c in components) + gap * (len(groups) - 1)
    factor = min(1.0, (SIDEBAR[3] - SIDEBAR[2] - .24) / total)
    cursor = .12 + total * factor / 2
    rows = []
    for group in groups:
        for component in group:
            height = heights.get(component["kind"], .47) * factor
            rows.append((component, [SIDEBAR[0], SIDEBAR[1], cursor - height, cursor]))
            cursor -= height
        cursor -= gap * factor
    return rows


def _plot_bounds(axes):
    xmin, xmax, _ = axes["x_range"]
    ymin, ymax, _ = axes["y_range"]
    left, right, bottom, top = PLOT_REGION
    if axes["equal_units"]:
        scale = min((right - left) / (xmax - xmin), (top - bottom) / (ymax - ymin))
        width, height = scale * (xmax - xmin), scale * (ymax - ymin)
        cx, cy = (left + right) / 2, (bottom + top) / 2
        return [cx - width / 2, cx + width / 2, cy - height / 2, cy + height / 2]
    return list(PLOT_REGION)


def _segment(component, start, end):
    line_class = DashedLine if component["dashed"] else Line
    kwargs = {"dash_length": .095, "positive_space_ratio": .52} if component["dashed"] else {}
    line = line_class(start, end, buff=0, color=COLORS[component["color"]], stroke_width=1.7, **kwargs)
    if component["dashed"]:
        # ManimGL's final dash can undershoot the requested end. Correct that
        # native Line explicitly instead of weakening the measured endpoint check.
        line[-1].put_start_and_end_on(line[-1].get_start(), end)
    return line


class ComponentScene(Scene):
    plan_path: Path
    asset_dir: Path
    font = FONT
    font_path = FONT_PATH

    default_camera_config = {
        "fps": FPS, "resolution": (1920, 1080), "background_color": "#101216",
        "frame_config": {"frame_shape": (128 / 9, 8.0)},
    }

    def __init__(self, *args, camera_config=None, **kwargs):
        config = dict(camera_config or {})
        width, height = config.get("resolution", (1920, 1080))
        if width * 9 != height * 16:
            raise ValueError("ComponentScene requires a 16:9 resolution")
        config.update(fps=FPS, background_color="#101216",
                      frame_config={"frame_shape": (128 / 9, 8.0)})
        super().__init__(*args, camera_config=config, **kwargs)

    def setup(self):
        super().setup()
        for name in ("plan_path", "asset_dir"):
            path = getattr(self, name, None)
            if not isinstance(path, Path) or not path.is_absolute():
                raise ValueError(f"Wrapper must bind {name} to an absolute Path")
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        self.frames_checked = 0
        self.audit_issues = set()
        self.shot_records = []
        self._audit_closed = False
        self._audit_stream = (self.asset_dir / "frame-audit.json").open("w", encoding="utf-8")
        self._audit_stream.write('{"frames":[')
        try:
            if self.skip_animations or self.start_at_animation_number is not None or self.end_at_animation_number is not None:
                raise ValueError("Frame evidence requires a complete, non-skipping render")
            self.plan = validate_plan(json.loads(self.plan_path.read_text(encoding="utf-8")))
            self.expected_frames = sum(round(s["duration"] * FPS) for s in self.plan["shots"])
        except Exception as error:
            self.audit_issues.add(f"setup_error:{type(error).__name__}:{error}")
            self._finish_audit(False)
            raise

    def get_time_progression(self, run_time, **kwargs):
        if self.skip_animations:
            raise ValueError("Skipping frames invalidates component evidence")
        return np.arange(1, round(run_time * FPS) + 1, dtype=float) / FPS

    def _text(self, text, size=24, color="ink", *, weight="regular", numeric=False):
        index = {"regular": FONT_INDEX, "medium": FONT_MEDIUM_INDEX, "semibold": FONT_SEMIBOLD_INDEX}[weight]
        return text_image(text, self.asset_dir, size, COLORS[color],
                          font=self.font, font_path=NUMBER_FONT_PATH if numeric else self.font_path,
                          font_index=NUMBER_FONT_INDEX if numeric else index)

    @staticmethod
    def _fit(mobject, width, height, size, minimum):
        factor = min(1, width / max(mobject.get_width(), 1e-8),
                     height / max(mobject.get_height(), 1e-8))
        if size * factor < minimum - 1e-6:
            raise ValueError(f"Content does not fit at readable size {minimum}: "
                             f"needs {mobject.get_width():.3f} x {mobject.get_height():.3f}")
        return mobject.scale(factor)

    def _label(self, key, mobject, row=None):
        self.labels[key] = mobject
        if row is not None:
            self.row_members[row].append(mobject)
        self.add(mobject)
        return mobject

    def _mapping(self):
        spec = self.shot["axes"]
        xmin, xmax, _ = spec["x_range"]
        ymin, ymax, _ = spec["y_range"]
        low, high = self.axes.c2p(xmin, ymin), self.axes.c2p(xmax, ymax)
        return {"origin": _xy(self.axes.c2p(0, 0)),
                "scale": [float((high[0] - low[0]) / (xmax - xmin)),
                          float((high[1] - low[1]) / (ymax - ymin))],
                "plot": [float(low[0]), float(high[0]), float(low[1]), float(high[1])],
                "equal_units": spec["equal_units"]}

    def _expected_point(self, point):
        return [self.mapping["origin"][i] + self.mapping["scale"][i] * point[i] for i in (0, 1)]

    def _build_axes(self):
        spec = self.shot["axes"]
        left, right, bottom, top = _plot_bounds(spec)
        self.axes = Axes(
            x_range=spec["x_range"], y_range=spec["y_range"],
            width=right - left, height=top - bottom,
            axis_config={"include_tip": False, "include_numbers": False,
                         "include_ticks": True, "tick_size": 0.035, "stroke_width": 1.2,
                         "color": AXIS_COLOR},
        )
        self.axes.shift(np.array([left, bottom, 0]) -
                        self.axes.c2p(spec["x_range"][0], spec["y_range"][0]))
        self.mapping = self._mapping()
        self.add(self.axes)
        # Border ticks and protected gutters keep moving geometry away from glyphs.
        self.add(Line([left, bottom, 0], [right, bottom, 0], color=BORDER_COLOR, stroke_width=.85),
                 Line([left, bottom, 0], [left, top, 0], color=BORDER_COLOR, stroke_width=.85))
        self.axis_ticks = []
        for axis in ("x", "y"):
            number_line = getattr(self.axes, f"{axis}_axis")
            values, marks = number_line.get_tick_range(), number_line.get_tick_marks()
            if len(values) != len(marks):
                raise ValueError("Native tick count mismatch")
            for index, (value, mark) in enumerate(zip(values, marks)):
                label = self._text(f"{value:g}", size=19, color="muted", numeric=True)
                if axis == "x":
                    target = [self.axes.c2p(value, 0)[0], bottom, 0]
                    label.move_to(np.array(target) + [0, -0.32, 0])
                else:
                    target = [left, self.axes.c2p(0, value)[1], 0]
                    label.move_to(np.array(target) + [-0.18, 0, 0], aligned_edge=RIGHT)
                mark.move_to(target)
                key = f"axis.{axis}.tick.{index}"
                self._label(key, label)
                self.axis_ticks.append({"axis": axis, "value": float(value), "mark": mark, "label": key})
        x_label = self._fit(self._text(spec["x_label"], 20, "muted"), 5, .3, 20, 18)
        y_label = self._fit(self._text(spec["y_label"], 20, "muted"), 5, .3, 20, 18)
        self._label("axis.x.unit", x_label.move_to([(left + right) / 2, -2.65, 0]))
        self._label("axis.y.unit", y_label.move_to([left, 2.4, 0], aligned_edge=LEFT))

    def _tick_evidence(self):
        records, issues = [], []
        left, right, bottom, top = self.mapping["plot"]
        for tick in self.axis_ticks:
            axis, value = tick["axis"], tick["value"]
            label, mark = self.labels[tick["label"]], tick["mark"]
            target = ([self._expected_point([value, 0])[0], bottom] if axis == "x"
                      else [left, self._expected_point([0, value])[1]])
            actual = _xy(mark.get_center())
            label_anchor = _xy(label.get_center() if axis == "x" else label.get_right())
            expected_anchor = [target[0], bottom - .32] if axis == "x" else [left - .18, target[1]]
            box = _box(label)
            if not _close(actual, target) or not _close(label_anchor, expected_anchor):
                issues.append(f"tick_label_mismatch:{tick['label']}")
            if box[0] < right and box[1] > left and box[2] < top and box[3] > bottom:
                issues.append(f"tick_label_inside_plot:{tick['label']}")
            records.append({"axis": axis, "value": value, "mark": actual, "expected_mark": target,
                            "label_anchor": label_anchor, "expected_anchor": expected_anchor})
        return records, issues

    def _build_shot(self, shot):
        self.clear()
        self.shot = shot
        self.compiled = CompiledShot(shot)
        initial = self.compiled.evaluate(0)
        self.labels, self.objects, self.row_members = {}, {}, {}
        self.number_anchors, self.formula_latex, self.row_bounds = {}, {}, {}
        self._build_axes()
        header = self._fit(self._text(shot["title"], 36, weight="semibold"), 12.5, .55, 36, 30)
        self._label("header", header.move_to([-6.1, 3.18, 0], aligned_edge=LEFT))
        caption_lines = [self._fit(self._text(line, 22), 12.5, .32, 22, 20)
                         for line in shot["caption"]]
        caption = Group(*caption_lines).arrange(np.array([0, -1, 0]), buff=.1)
        caption.move_to([0, -3.25, 0])
        for i, line in enumerate(caption_lines):
            self._label(f"caption.{i}", line)

        for component, bounds in _row_layout(shot["components"]):
            cid, kind, color = component["id"], component["kind"], COLORS[component["color"]]
            value = initial["objects"][cid]
            self.row_members[cid] = []
            row_height = bounds[3] - bounds[2]
            y = (bounds[3] + bounds[2]) / 2
            self.row_bounds[cid] = bounds
            is_detail = kind in {"formula", "readout"}
            label_y = y + min(.32, (row_height - .24) / 2) if kind == "formula" else y
            label_size = 18 if kind == "formula" else 21
            label = self._fit(self._text(component["label"], label_size,
                                        "muted" if is_detail else "ink"),
                              2.5 if kind == "readout" else 3.85, .3, label_size, label_size - 2)
            self._label(f"row.{cid}.label", label.move_to([1.85 if is_detail else 2.22, label_y, 0], aligned_edge=LEFT), cid)
            if not is_detail:
                if kind == "point":
                    self.add(Dot([1.93, label_y, 0], radius=.031).set_color(color))
                else:
                    self.add(Line([1.81, label_y, 0], [2.05, label_y, 0], color=color, stroke_width=2.3))

            if kind == "formula":
                # The compiler owns safe LaTeX and its curve binding; never compile per frame.
                obj = Tex(value["latex"], font_size=38, template="basic_ctex", color=color)
                self._fit(obj, 4.15, row_height - .38, 38, 30)
                obj.move_to([1.85, y - .13, 0], aligned_edge=LEFT)
                self.formula_latex[cid] = value["latex"]
                self._label(f"row.{cid}.formula", obj, cid)
            elif kind == "readout":
                unit = self._fit(self._text(component["unit"], 18, "muted"), .85, .28, 18, 16)
                unit.move_to([6.1, y, 0], aligned_edge=RIGHT)
                self._label(f"row.{cid}.unit", unit, cid)
                anchor = [float(unit.get_left()[0]) - .16, y, 0]
                self.number_anchors[cid] = anchor
                obj = RasterNumber(round(value["value"], component["decimals"]), self.asset_dir,
                                   decimals=component["decimals"], size=32, color=color,
                                   font_path=NUMBER_FONT_PATH, font_index=NUMBER_FONT_INDEX)
                obj.move_to(anchor, aligned_edge=RIGHT)
                self._label(f"row.{cid}.value", obj, cid)
            elif kind == "curve":
                obj = VMobject(color=color, stroke_width=3.1)
                obj.set_points_as_corners([self.axes.c2p(*p) for p in value["points"]])
            elif kind == "point":
                obj = Dot(self.axes.c2p(*value["position"]), radius=.043, color=color)
            else:
                start, end = [self.axes.c2p(*value[p]) for p in ("start", "end")]
                if kind == "vector":
                    obj = Arrow(start, end, buff=0, color=color, thickness=1.5, tip_width_ratio=3.8,
                                max_tip_length_to_length_ratio=.16)
                else:
                    obj = _segment(component, start, end)
            # Arrow/Dot constructor fill defaults override the generic color argument.
            if kind != "readout":
                obj.set_color(color)
            self.objects[cid] = obj
            if not is_detail:
                self.add(obj)
        self.required_labels = sorted(self.labels)
        self.shot_records.append({"shot": shot["id"], "mapping": self.mapping,
                                  "required_labels": self.required_labels,
                                  "row_bounds": self.row_bounds,
                                  "start_frame": self.frames_checked + 1,
                                  "frame_count": round(shot["duration"] * FPS)})

    def _sync(self, state):
        for component in self.shot["components"]:
            cid, kind = component["id"], component["kind"]
            obj, value = self.objects[cid], state["objects"][cid]
            if kind == "curve":
                obj.set_points_as_corners([self.axes.c2p(*p) for p in value["points"]])
            elif kind == "point":
                obj.move_to(self.axes.c2p(*value["position"]))
            elif kind in {"segment", "vector"}:
                start, end = [self.axes.c2p(*value[p]) for p in ("start", "end")]
                if not np.isfinite([start, end]).all() or np.linalg.norm(end - start) < 1e-7:
                    raise ValueError(f"Degenerate or nonfinite {kind}:{cid}")
                if kind == "segment" and component["dashed"]:
                    # ManimGL DashedLine has no root points; its inherited endpoint
                    # transform raises. Rebuild native dashes, retaining the scene object.
                    obj.become(_segment(component, start, end))
                else:
                    obj.put_start_and_end_on(start, end)
            elif kind == "readout":
                # Keep displayed precision identical to the data audit.
                obj.set_value(round(value["value"], component["decimals"]))
                obj.move_to(self.number_anchors[cid], aligned_edge=RIGHT)
            elif value["latex"] != self.formula_latex[cid]:
                raise ValueError(f"Formula changed within shot:{cid}")

    def _audit_frame(self, fraction, state, shot_frame):
        boxes = {key: _box(obj) for key, obj in self.labels.items()}
        # Register leaf labels once, not their enclosing row Groups. Thus nesting
        # is excluded, while sibling labels, different rows and all axes still collide.
        issues = check_boxes(boxes, SCREEN, gap=0.035)
        if sorted(boxes) != self.required_labels:
            issues.append("label_registry_changed")
        row_boxes = {}
        for cid, members in self.row_members.items():
            member_boxes = [_box(obj) for obj in members]
            row_boxes[cid] = [min(b[0] for b in member_boxes), max(b[1] for b in member_boxes),
                              min(b[2] for b in member_boxes), max(b[3] for b in member_boxes)]
        issues.extend(check_boxes(row_boxes, SIDEBAR, gap=0.035))
        for cid, box in row_boxes.items():
            if not _inside([[box[0], box[2]], [box[1], box[3]]], self.row_bounds[cid]):
                issues.append(f"row_overflow:{cid}")
        mapping = self._mapping()
        for field in ("origin", "scale", "plot"):
            if not _close(mapping[field], self.mapping[field]):
                issues.append(f"axis_mapping_changed:{field}")
        if not _close(mapping["plot"], _plot_bounds(self.shot["axes"])):
            issues.append("axis_plot_mismatch")
        if mapping["equal_units"] and not _close(*mapping["scale"]):
            issues.append("axis_units_unequal")
        ticks, tick_issues = self._tick_evidence()
        issues.extend(tick_issues)

        actual, expected, colors = {}, {}, {}
        for component in self.shot["components"]:
            cid, kind = component["id"], component["kind"]
            obj, value = self.objects[cid], state["objects"][cid]
            colors[cid] = {"actual": _visible_colors(obj), "expected": COLORS[component["color"]]}
            if colors[cid]["actual"] != [colors[cid]["expected"]]:
                issues.append(f"color_mismatch:{cid}")
            if kind == "readout":
                actual[cid] = {"value": float(obj.get_value()), "display": obj.num_string}
                expected[cid] = {"value": round(value["value"], component["decimals"]),
                                 "unrounded_value": value["value"]}
                if not _close(actual[cid]["value"], expected[cid]["value"]):
                    issues.append(f"readout_mismatch:{cid}")
                number = expected[cid]["value"] or 0.0
                expected[cid]["display"] = f"{number:.{component['decimals']}f}"
                if actual[cid]["display"] != expected[cid]["display"]:
                    issues.append(f"readout_display_mismatch:{cid}")
                if not _close(_xy(obj.get_right()), self.number_anchors[cid][:2]):
                    issues.append(f"readout_anchor_mismatch:{cid}")
                continue
            if kind == "formula":
                actual[cid] = {"latex": obj.get_tex()}
                expected[cid] = value
                if actual[cid] != expected[cid]:
                    issues.append(f"formula_mismatch:{cid}")
                continue
            if kind == "curve":
                anchors = [self._expected_point(p) for p in value["points"]]
                controls = []
                for a, b in zip(anchors, anchors[1:]):
                    controls.extend([a, [(x + y) / 2 for x, y in zip(a, b)]])
                controls.append(anchors[-1])
                actual[cid] = {"points": [_xy(p) for p in obj.get_anchors()],
                               "control_points": [_xy(p) for p in obj.get_points()]}
                expected[cid] = {"points": anchors, "control_points": controls}
            elif kind == "point":
                actual[cid] = {"position": _xy(obj.get_center())}
                expected[cid] = {"position": self._expected_point(value["position"])}
            else:
                actual[cid] = {"start": _xy(obj.get_start()), "end": _xy(obj.get_end())}
                expected[cid] = {key: self._expected_point(value[key]) for key in ("start", "end")}
                if math.dist(actual[cid]["start"], actual[cid]["end"]) < 1e-7:
                    issues.append(f"degenerate_geometry:{cid}")
            for field, target in expected[cid].items():
                if not _close(actual[cid][field], target):
                    issues.append(f"geometry_mismatch:{cid}:{field}")
                if not _inside(actual[cid][field], mapping["plot"]):
                    issues.append(f"geometry_outside_plot:{cid}:{field}")
        return {"frame": self.frames_checked + 1, "shot": self.shot["id"],
                "shot_frame": shot_frame, "fraction": fraction,
                "time": self.frames_checked / FPS, "parameters": state["parameters"],
                "boxes": boxes, "row_boxes": row_boxes, "mapping": mapping,
                "actual": actual, "expected": expected, "colors": colors, "ticks": ticks,
                "issues": sorted(set(issues))}

    def construct(self):
        complete = False
        try:
            for shot in self.plan["shots"]:
                self._build_shot(shot)
                frames = round(shot["duration"] * FPS)
                self.pre_play()
                previous = 0
                for index, time in enumerate(self.get_time_progression(frames / FPS)):
                    # N actual video frames contain both endpoints; no extra terminal wait.
                    fraction = index / (frames - 1)
                    state = self.compiled.evaluate(fraction)
                    self._sync(state)
                    self.update_frame(float(time - previous))
                    previous = time
                    record = self._audit_frame(fraction, state, index)
                    payload = json.dumps(record, ensure_ascii=False, allow_nan=False)
                    self.emit_frame()
                    if self.frames_checked:
                        self._audit_stream.write(",")
                    self._audit_stream.write(payload)
                    self.frames_checked += 1
                    self.audit_issues.update(record["issues"])
                self.post_play()
                self._audit_stream.flush()
            complete = self.frames_checked == self.expected_frames
        except Exception as error:
            self.audit_issues.add(f"render_error:{type(error).__name__}:{error}")
            raise
        finally:
            self._finish_audit(complete)

    def _finish_audit(self, complete):
        if self._audit_closed:
            return
        if not complete:
            self.audit_issues.add("incomplete_frame_coverage")
        report = {"frames_checked": self.frames_checked,
                  "visual_style": "studio-0.2",
                  "expected_frames": getattr(self, "expected_frames", None),
                  "issues": sorted(self.audit_issues), "complete": complete, "fps": FPS,
                  "frame_index_base": 1, "shots": self.shot_records,
                  "source_paths": [str(Path(__file__).resolve()),
                                   str(Path(__file__).with_name("typography.py").resolve())],
                  "plan_path": str(self.plan_path),
                  "limitations": [
                      "Native label boxes and finite geometry samples are not pixel OCR or aesthetic approval.",
                      "Polyline anchors and quadratic control points are checked; continuity between mathematical samples is not proved.",
                      "Geometry intersections and containing row/label nesting are intentional; leaf label collisions are checked.",
                      "Plot bounds apply to point centers and line endpoints/curve controls, not dot radius, stroke or arrowhead pixels.",
                      "Readout evidence compares native rounded values; unrounded mathematical values are retained separately.",
                      "Each shot emits round(duration*30) frames with fraction i/(N-1), including both endpoints.",
                  ]}
        self._audit_stream.write("]")
        for key, value in report.items():
            self._audit_stream.write("," + json.dumps(key) + ":")
            json.dump(value, self._audit_stream, ensure_ascii=False, allow_nan=False)
        self._audit_stream.write("}\n")
        self._audit_stream.close()
        self._audit_closed = True

    def tear_down(self):
        if hasattr(self, "_audit_stream") and not self._audit_closed:
            self._finish_audit(False)
        super().tear_down()
