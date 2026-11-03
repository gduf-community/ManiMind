"""Versioned, fail-closed data contract. Never evaluate model expressions."""

from copy import deepcopy
import json
import math
import re

PRIMITIVES = {"graph", "moving_point", "increment_triangle", "secant", "tangent", "ratio"}
BINDINGS = {"delta_t", "delta_s", "average_slope"}
FOCUS = {"interval", "displacement", "ratio", "convergence"}


class SpecError(ValueError):
    pass


def keys(obj, required, where):
    if not isinstance(obj, dict) or set(obj) != set(required):
        raise SpecError(f"{where}: expected exactly {sorted(required)}")


def number(value, where, low=-1000, high=1000):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise SpecError(f"{where}: finite number in [{low},{high}] required")
    return float(value)


def plain_text(value, where, maximum):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise SpecError(f"{where}: 1..{maximum} characters required")
    if not re.fullmatch(r"[\u3400-\u9fffA-Za-z0-9 ，。！？：、（）()=+\-.,?！]+", value):
        raise SpecError(f"{where}: plain Chinese/ASCII text only, no markup or commands")


def polynomial(coefficients, x):
    result = 0.0
    for coefficient in reversed(coefficients):
        result = result * x + coefficient
    return result


def derivative(coefficients, x):
    return polynomial([i * c for i, c in enumerate(coefficients)][1:], x)


def extrema(coefficients, end):
    candidates = [0.0, end]
    padded = list(coefficients) + [0] * (4 - len(coefficients))
    a, b, c = 3 * padded[3], 2 * padded[2], padded[1]
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            candidates.append(-c / b)
    elif b * b - 4 * a * c >= 0:
        root = math.sqrt(b * b - 4 * a * c)
        candidates += [(-b - root) / (2 * a), (-b + root) / (2 * a)]
    values = [polynomial(coefficients, t) for t in candidates if 0 <= t <= end]
    return min(values), max(values)


def values(model, h):
    t = model["focus"]
    coefficients = model["coefficients"]
    start = polynomial(coefficients, t)
    end = polynomial(coefficients, t + h)
    return {"delta_t": h, "delta_s": end - start, "average_slope": (end - start) / h,
            "tangent_slope": derivative(coefficients, t), "p": [t, start], "q": [t + h, end], "r": [t + h, start]}


def validate_model(model):
    keys(model, {"kind", "coefficients", "focus", "domain"}, "model")
    if model["kind"] != "polynomial":
        raise SpecError("Only polynomial models are supported")
    coefficients = model["coefficients"]
    if not isinstance(coefficients, list) or not 2 <= len(coefficients) <= 4:
        raise SpecError("Polynomial coefficients must be [constant,linear,quadratic?,cubic?]")
    for c in coefficients:
        number(c, "coefficient", -50, 50)
    if coefficients[-1] == 0:
        raise SpecError("Highest polynomial coefficient must be nonzero")
    domain = model["domain"]
    if not isinstance(domain, list) or len(domain) != 2 or type(domain[0]) not in (int, float) or domain[0] != 0:
        raise SpecError("This position-time component requires domain [0,end]")
    end = number(domain[1], "domain end", 1, 8)
    focus = number(model["focus"], "focus", 0.1, end - 0.01)
    low, high = extrema(coefficients, end)
    if low < -1e-8 or not 0 < high <= 1000 or abs(derivative(coefficients, focus)) > 1000:
        raise SpecError("V1 requires nonnegative positions <=1000 and bounded slope")


def validate_spec(spec, task=None):
    keys(spec, {"schema_version", "title", "learning_goal", "model", "initial_h", "primitives", "readouts", "stages"}, "scene")
    if spec["schema_version"] != "1.0":
        raise SpecError("Unsupported schema version")
    plain_text(spec["title"], "title", 20)
    plain_text(spec["learning_goal"], "learning_goal", 100)
    validate_model(spec["model"])
    initial = number(spec["initial_h"], "initial_h", 0.01, 2)
    if spec["model"]["focus"] + initial > spec["model"]["domain"][1]:
        raise SpecError("Q is outside the model domain")
    primitives = spec["primitives"]
    if not isinstance(primitives, list) or not all(isinstance(x, str) for x in primitives) or len(primitives) != len(PRIMITIVES) or set(primitives) != PRIMITIVES:
        raise SpecError("V1 requires the six supported primitives exactly once")
    readouts = spec["readouts"]
    if not isinstance(readouts, list) or len(readouts) != 3:
        raise SpecError("Exactly three typed readouts required")
    bindings = []
    for row in readouts:
        keys(row, {"bind", "decimals"}, "readout")
        if not isinstance(row["bind"], str) or row["bind"] not in BINDINGS or type(row["decimals"]) is not int or row["decimals"] != {"delta_t": 4, "delta_s": 4, "average_slope": 2}[row["bind"]]:
            raise SpecError("Readouts use enum bindings and fixed 4/4/2 precision")
        bindings.append(row["bind"])
    if set(bindings) != BINDINGS:
        raise SpecError("Missing or duplicate readout binding")
    stages = spec["stages"]
    if not isinstance(stages, list) or len(stages) != 3:
        raise SpecError("V1 requires three continuous stages")
    previous = initial
    for i, stage in enumerate(stages):
        keys(stage, {"title", "h_to", "focus", "pace"}, f"stage {i}")
        plain_text(stage["title"], "stage title", 16)
        h = number(stage["h_to"], "h_to", 0.01, 2)
        if not h < previous:
            raise SpecError("Positive h must decrease strictly; never divide by zero")
        if not isinstance(stage["focus"], str) or stage["focus"] not in FOCUS or (i == 2 and stage["focus"] != "convergence"):
            raise SpecError("Last stage must focus on convergence")
        if not isinstance(stage["pace"], str) or stage["pace"] not in {"early", "balanced"} or (i < 2 and stage["pace"] != "early"):
            raise SpecError("First two stages require early pacing")
        previous = h
    if task is not None:
        if spec["model"] != task["model"] or spec["initial_h"] != task["h_sequence"][0] or [s["h_to"] for s in stages] != task["h_sequence"][1:]:
            raise SpecError("Model or h sequence differs from frozen task")
    return deepcopy(spec)


def parse_spec(reply, task=None):
    text = reply.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise SpecError(f"Duplicate JSON key: {k}")
            result[k] = v
        return result
    try:
        parsed = json.loads(text, object_pairs_hook=unique,
                            parse_constant=lambda v: (_ for _ in ()).throw(SpecError(f"Nonfinite JSON: {v}")))
    except json.JSONDecodeError as exc:
        raise SpecError(f"Invalid JSON at line {exc.lineno}") from None
    return validate_spec(parsed, task)


def polynomial_tex(coefficients):
    terms = []
    for power in range(len(coefficients) - 1, -1, -1):
        coefficient = coefficients[power]
        if coefficient == 0:
            continue
        magnitude = abs(coefficient)
        body = "" if power and magnitude == 1 else f"{magnitude:g}"
        body += ("t" if power == 1 else f"t^{{{power}}}") if power else ""
        terms.append(("-" if coefficient < 0 else "+") + body)
    return "s(t)=" + "".join(terms).lstrip("+")


CONTRACT = {
    "schema_version": "1.0", "title": "中文标题，至多20字", "learning_goal": "中文目标，至多100字",
    "model": {"kind": "polynomial", "coefficients": "从task复制数字数组，常数项在前", "focus": "从task复制", "domain": "从task复制"},
    "initial_h": "task.h_sequence[0]", "primitives": sorted(PRIMITIVES),
    "readouts": [{"bind": "delta_t", "decimals": 4}, {"bind": "delta_s", "decimals": 4}, {"bind": "average_slope", "decimals": 2}],
    "stages": [
        {"title": "过程描述，至多16字", "h_to": "task.h_sequence[1]", "focus": "interval或displacement或ratio", "pace": "early"},
        {"title": "过程描述", "h_to": "task.h_sequence[2]", "focus": "interval或displacement或ratio", "pace": "early"},
        {"title": "过程描述", "h_to": "task.h_sequence[3]", "focus": "convergence", "pace": "early或balanced"}
    ]
}
