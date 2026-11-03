"""Small tested geometry/layout compiler; uses no model-provided code."""

import math

from .schema import extrema, polynomial, derivative
from ..experiments.layout_guard import check_boxes

TEACHING_BOUNDS = [-6.3, 6.3, -2.5, 2.5]
PLOT_BOUNDS = [-5.4, -0.4, -1.8, 1.5]


def nice_step(value):
    power = 10 ** math.floor(math.log10(max(value, 1e-6)))
    return next(n * power for n in (1, 2, 2.5, 5, 10) if n * power >= value)


def axis_plan(model):
    maximum = extrema(model["coefficients"], model["domain"][1])[1]
    y_step = nice_step(maximum * 1.08 / 5)
    y_max = math.ceil(maximum * 1.08 / y_step) * y_step
    x_max = model["domain"][1]
    return {"x_max": x_max, "y_max": y_max, "x_step": nice_step(x_max / 4), "y_step": y_step,
            "plot": PLOT_BOUNDS}


def map_point(point, mapping):
    return [mapping["origin"][0] + mapping["scale"][0] * point[0],
            mapping["origin"][1] + mapping["scale"][1] * point[1]]


def clip_line(point, direction, bounds):
    if len(point) != 2 or len(direction) != 2 or not all(math.isfinite(v) for v in [*point, *direction, *bounds]):
        raise ValueError("Finite 2D line required")
    if math.hypot(*direction) < 1e-12:
        raise ValueError("Degenerate line")
    lo, hi = -math.inf, math.inf
    for p, d, lower, upper in zip(point, direction, bounds[::2], bounds[1::2]):
        if abs(d) < 1e-12:
            if not lower <= p <= upper:
                raise ValueError("Line misses plot")
        else:
            a, b = sorted(((lower - p) / d, (upper - p) / d))
            lo, hi = max(lo, a), min(hi, b)
    if lo >= hi:
        raise ValueError("Line has no visible segment")
    return [[p + t * d for p, d in zip(point, direction)] for t in (lo, hi)]


def on_segment(point, ends, tolerance=1e-5):
    a, b = ends
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return False
    cross = abs((point[0] - a[0]) * dy - (point[1] - a[1]) * dx) / length
    projection = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length
    return cross <= tolerance and -tolerance <= projection <= length + tolerance


def audit_frame(record, model, mapping, required_labels):
    issues = check_boxes(record["boxes"], TEACHING_BOUNDS, gap=0.035)
    if set(record["boxes"]) != set(required_labels):
        issues.append("label_registry_changed")
    h = record["h"]
    if not math.isfinite(h) or h <= 0:
        return issues + ["invalid_h"]
    t = model["focus"]
    c = model["coefficients"]
    p = [t, sum(v * t ** i for i, v in enumerate(c))]
    q = [t + h, sum(v * (t + h) ** i for i, v in enumerate(c))]
    r = [t + h, p[1]]
    expected = {"delta_t": h, "delta_s": q[1] - p[1], "average_slope": (q[1] - p[1]) / h}
    for key, value in expected.items():
        actual = record["readouts"][key]
        if not math.isfinite(actual) or abs(actual - value) > 1e-7 * max(1, abs(value)):
            issues.append(f"readout_mismatch:{key}")
    targets = {"p": p, "q": q, "r": r}
    for key, value in targets.items():
        target = map_point(value, mapping)
        if math.dist(record[key], target) > 1e-5:
            issues.append(f"point_mismatch:{key}")
    for key, points in [("delta_t", [p, r]), ("delta_s", [r, q])]:
        if any(math.dist(actual, map_point(target, mapping)) > 1e-5 for actual, target in zip(record["increments"][key], points)):
            issues.append(f"increment_mismatch:{key}")
    for point in (record["p"], record["q"]):
        if not on_segment(point, record["secant"]):
            issues.append("secant_does_not_cover_point")
    for kind in ("secant", "tangent"):
        for x, y in record[kind]:
            b = mapping["plot"]
            if not b[0] - 1e-6 <= x <= b[1] + 1e-6 or not b[2] - 1e-6 <= y <= b[3] + 1e-6:
                issues.append(f"line_outside_plot:{kind}")
        if math.dist(*record[kind]) < 1:
            issues.append(f"line_too_short:{kind}")
    if not on_segment(record["p"], record["tangent"]):
        issues.append("tangent_misses_p")
    a, b = record["tangent"]
    screen_slope = (b[1] - a[1]) / (b[0] - a[0])
    if abs(screen_slope * mapping["scale"][0] / mapping["scale"][1] - derivative(c, t)) > 1e-6:
        issues.append("tangent_slope_mismatch")
    return sorted(set(issues))
