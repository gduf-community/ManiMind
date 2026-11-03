"""A bounded, provider-neutral shot contract and deterministic frame compiler."""

from copy import deepcopy
import json
import math
import re

from .catalog import COLORS
from .expressions import compile_expression

SCHEMA_VERSION = "components-0.1"


class PlanError(ValueError):
    pass


def exact(value, fields, where):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise PlanError(f"{where}: expected exactly {sorted(fields)}")


def text(value, maximum, where):
    if (not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum
            or any(ord(c) < 32 for c in value) or "\\" in value):
        raise PlanError(f"{where}: plain text of 1..{maximum} characters required")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", value):
        raise PlanError("Invalid identifier")


def numeric(value, lower=-1000, upper=1000):
    if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
        raise PlanError(f"Finite number in [{lower},{upper}] required")
    return float(value)


def parse_plan(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PlanError(f"Duplicate key: {key}")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda x: (_ for _ in ()).throw(PlanError(f"Nonfinite: {x}")))
    return validate_plan(value)


def validate_plan(plan):
    exact(plan, {"schema_version", "id", "title", "provenance", "shots"}, "plan")
    if plan["schema_version"] != SCHEMA_VERSION:
        raise PlanError("Unsupported schema")
    identifier(plan["id"])
    text(plan["title"], 40, "title")
    exact(plan["provenance"], {"kind", "author", "interventions"}, "provenance")
    if not isinstance(plan["provenance"]["kind"], str) or plan["provenance"]["kind"] not in {"engineering_fixture", "model_output"}:
        raise PlanError("Explicit authorship required")
    text(plan["provenance"]["author"], 80, "author")
    interventions = plan["provenance"]["interventions"]
    if not isinstance(interventions, list) or len(interventions) > 30:
        raise PlanError("Invalid intervention ledger")
    for intervention in interventions:
        text(intervention, 200, "intervention")
    shots = plan["shots"]
    if not isinstance(shots, list) or not 1 <= len(shots) <= 20:
        raise PlanError("Expected 1..20 shots")
    ids = []
    total = 0
    for shot in shots:
        validate_shot(shot)
        ids.append(shot["id"])
        total += shot["duration"]
    if len(ids) != len(set(ids)) or total > 600:
        raise PlanError("Duplicate shots or excessive duration")
    return deepcopy(plan)


def validate_shot(shot):
    exact(shot, {"id", "title", "goal", "duration", "caption", "axes", "parameters", "components", "keyframes"}, "shot")
    identifier(shot["id"])
    text(shot["title"], 24, "shot title")
    text(shot["goal"], 160, "goal")
    numeric(shot["duration"], 3, 90)
    if not isinstance(shot["caption"], list) or not 1 <= len(shot["caption"]) <= 2:
        raise PlanError("One or two caption lines required")
    for line in shot["caption"]:
        text(line, 40, "caption")
    axes = shot["axes"]
    exact(axes, {"x_range", "y_range", "x_label", "y_label", "equal_units"}, "axes")
    if type(axes["equal_units"]) is not bool:
        raise PlanError("equal_units must be boolean")
    for axis in ("x", "y"):
        limits = axes[f"{axis}_range"]
        if not isinstance(limits, list) or len(limits) != 3:
            raise PlanError("Axis needs [minimum,maximum,step]")
        lo, hi, step = [numeric(v) for v in limits]
        if not lo < hi or not lo <= 0 <= hi or step <= 0 or not 1 <= (hi - lo) / step <= 10:
            raise PlanError("Axes must include zero and have 1..10 tick intervals")
        text(axes[f"{axis}_label"], 12, "axis label")
    params = shot["parameters"]
    if not isinstance(params, dict) or len(params) > 8:
        raise PlanError("At most eight parameters")
    for name, value in params.items():
        if not re.fullmatch(r"[a-z][a-z0-9]{0,7}", name) or name == "x":
            raise PlanError("Parameter name invalid or reserved x")
        numeric(value, -100, 100)
    components = shot["components"]
    if not isinstance(components, list) or not 1 <= len(components) <= 16:
        raise PlanError("Expected 1..16 components")
    ids, rows = [], 0
    common = {"id", "kind", "label", "color"}
    fields = {"curve": {"expression"}, "point": {"position"},
              "segment": {"start", "end", "dashed"}, "vector": {"start", "end"},
              "formula": {"lhs", "source"}, "readout": {"expression", "unit", "decimals"}}
    for component in components:
        if not isinstance(component, dict) or not isinstance(component.get("kind"), str) or component["kind"] not in fields:
            raise PlanError("Unknown component capability")
        kind = component["kind"]
        exact(component, common | fields[kind], kind)
        identifier(component["id"])
        ids.append(component["id"])
        text(component["label"], 14, "component label")
        if not isinstance(component["color"], str) or component["color"] not in COLORS:
            raise PlanError("Unknown semantic color")
        symbols = set(params) | ({"x"} if kind in {"curve", "formula"} else set())
        if kind in {"curve", "readout"}:
            compile_expression(component["expression"], symbols)
        for field in {"point": ("position",), "segment": ("start", "end"), "vector": ("start", "end")}.get(kind, ()):
            if not isinstance(component[field], list) or len(component[field]) != 2:
                raise PlanError("2D coordinate expressions required")
            for expression in component[field]:
                compile_expression(expression, set(params))
        if kind == "segment" and type(component["dashed"]) is not bool:
            raise PlanError("Dashed must be boolean")
        if kind == "formula":
            if not isinstance(component["lhs"], str) or not re.fullmatch(r"[a-z](?:\(x\))?", component["lhs"]):
                raise PlanError("Formula lhs must be a symbol or function of x")
            identifier(component["source"])
        if kind == "vector" and not axes["equal_units"]:
            raise PlanError("Vectors require equal mathematical unit scaling")
        if kind == "readout":
            text(component["unit"], 10, "readout unit")
            if type(component["decimals"]) is not int or not 0 <= component["decimals"] <= 4:
                raise PlanError("Readout precision must be 0..4")
        rows += 1
    if len(ids) != len(set(ids)) or rows > 6:
        raise PlanError("Duplicate component IDs or more than six explanation rows")
    by_id = {c["id"]: c for c in components}
    for component in components:
        if component["kind"] == "formula" and by_id.get(component["source"], {}).get("kind") != "curve":
            raise PlanError("Formula must bind to an existing curve, not a separate expression")
    frames = shot["keyframes"]
    if not isinstance(frames, list) or not 2 <= len(frames) <= 12:
        raise PlanError("Expected 2..12 keyframes")
    previous = -1
    for frame in frames:
        exact(frame, {"at", "values"}, "keyframe")
        at = numeric(frame["at"], 0, 1)
        if at <= previous or not isinstance(frame["values"], dict) or set(frame["values"]) != set(params):
            raise PlanError("Keyframes must be ordered with complete parameter states")
        for value in frame["values"].values():
            numeric(value, -100, 100)
        previous = at
    if frames[0]["at"] != 0 or frames[-1]["at"] != 1 or frames[0]["values"] != params:
        raise PlanError("Keyframes need initial state at 0 and final state at 1")
    if frames[-1]["values"] != frames[-2]["values"] or frames[-2]["at"] > 0.85:
        raise PlanError("Reserve at least 15% terminal hold with unchanged final values")


def parameter_state(shot, fraction):
    numeric(fraction, 0, 1)
    keyframes = shot["keyframes"]
    for left, right in zip(keyframes, keyframes[1:]):
        if fraction <= right["at"]:
            alpha = (fraction - left["at"]) / (right["at"] - left["at"])
            return {key: value + alpha * (right["values"][key] - value) for key, value in left["values"].items()}
    return dict(keyframes[-1]["values"])


class CompiledShot:
    """Compile once, evaluate every object against the same frame state."""

    def __init__(self, shot):
        validate_shot(shot)
        self.shot = deepcopy(shot)
        self.expressions = {}
        self.formulas = {}
        for component in shot["components"]:
            kind, cid = component["kind"], component["id"]
            symbols = set(shot["parameters"]) | ({"x"} if kind in {"curve", "formula"} else set())
            if "expression" in component:
                self.expressions[cid] = compile_expression(component["expression"], symbols)
            else:
                for field in ("position", "start", "end"):
                    if field in component:
                        self.expressions[cid, field] = [compile_expression(e, symbols) for e in component[field]]
        for component in shot["components"]:
            if component["kind"] == "formula":
                self.formulas[component["id"]] = component["lhs"] + "=" + self.expressions[component["source"]].latex()

    def evaluate(self, fraction):
        params = parameter_state(self.shot, fraction)
        objects = {}
        xmin, xmax, _ = self.shot["axes"]["x_range"]
        ymin, ymax, _ = self.shot["axes"]["y_range"]
        for component in self.shot["components"]:
            cid, kind = component["id"], component["kind"]
            if kind == "curve":
                points = [[xmin + (xmax - xmin) * i / 120, 0] for i in range(121)]
                for point in points:
                    point[1] = self.expressions[cid].evaluate({**params, "x": point[0]})
                # Unsupported clipping/discontinuities fail visibly; never silently truncate geometry.
                if any(not ymin - 1e-8 <= p[1] <= ymax + 1e-8 for p in points):
                    raise PlanError(f"Curve outside axes: {cid}")
                objects[cid] = {"points": points}
            elif kind == "formula":
                objects[cid] = {"latex": self.formulas[cid]}
            elif kind == "readout":
                objects[cid] = {"value": self.expressions[cid].evaluate(params)}
            else:
                obj = {field: [e.evaluate(params) for e in self.expressions[cid, field]]
                       for field in ("position", "start", "end") if field in component}
                for point in obj.values():
                    if not xmin <= point[0] <= xmax or not ymin <= point[1] <= ymax:
                        raise PlanError(f"Point outside axes: {cid}")
                if kind in {"segment", "vector"} and math.dist(obj["start"], obj["end"]) < 1e-7:
                    raise PlanError(f"Degenerate {kind}: {cid}")
                objects[cid] = obj
        return {"parameters": params, "objects": objects}


def preflight(plan, fps=30):
    plan = validate_plan(plan)
    if type(fps) is not int or fps not in (15, 30, 60):
        raise PlanError("Unsupported fps")
    reports = []
    cursor = 0
    for shot in plan["shots"]:
        compiled = CompiledShot(shot)
        frames = round(shot["duration"] * fps)
        for frame in range(frames):
            compiled.evaluate(frame / (frames - 1))
        reports.append({"shot": shot["id"], "frames_checked": frames,
                        "start_frame": cursor, "end_frame": cursor + frames,
                        "end_state": compiled.evaluate(1)})
        cursor += frames
    return {"schema_version": SCHEMA_VERSION, "fps": fps, "total_frames": cursor,
            "duration": cursor / fps, "shots": reports, "status": "pass",
            "limitations": ["Finite sampled curves, not a proof of continuity or arbitrary mathematics.",
                            "Data checks do not approve teaching quality or rendered pixel layout."]}
