"""Checks that formula-heavy scenes include matching visual companions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


VISUAL_COMPANION_TOKENS = {
    "graph": ("Axes(", ".plot(", ".get_graph(", "ParametricFunction(", "FunctionGraph("),
    "point": ("Dot(", "point", "c2p("),
    "line": ("Line(", "TangentLine", "get_secant", "get_tangent", "slope"),
    "arrow": ("Arrow(", "Vector(", "CurvedArrow(", "DoubleArrow("),
    "area": ("get_area", "get_riemann_rectangles", "Rectangle(", "Polygon(", "fill_opacity"),
    "plane": ("NumberPlane(", "Axes(", "ComplexPlane("),
}

FORMULA_HINTS = {
    "derivative": ("'", "d}{d", "frac{d", "dx", "slope", "tangent"),
    "integral": ("int", "\\int", "area", "sum", "riemann"),
    "function": ("f(", "y=", "x^", "x**", "graph"),
    "vector": ("vec", "matrix", "Vector", "\\begin{bmatrix}", "\\begin{pmatrix}"),
}

REQUIRED_COMPANIONS = {
    "derivative": {"graph", "point", "line"},
    "integral": {"graph", "area"},
    "function": {"graph"},
    "vector": {"arrow", "plane"},
}


@dataclass(slots=True)
class FormulaVisualBindingFinding:
    segment_id: str
    status: str
    issues: list[str] = field(default_factory=list)
    formula_hints: list[str] = field(default_factory=list)
    visual_companions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_formula_visual_binding(
    segment: dict[str, Any],
    formulas: list[str],
) -> FormulaVisualBindingFinding:
    """Check whether formulas have suitable visual companion objects."""
    segment_id = str(segment.get("segment_id") or "unknown")
    code = segment.get("scene_code")
    if not isinstance(code, str) or not code.strip():
        return FormulaVisualBindingFinding(
            segment_id=segment_id,
            status="block",
            issues=["formula segment is missing scene_code"],
        )

    formula_text = " ".join(str(item) for item in formulas)
    lowered = f"{formula_text} {code}".lower()
    formula_hints = [
        name
        for name, tokens in FORMULA_HINTS.items()
        if any(token.lower() in lowered for token in tokens)
    ]
    visual_companions = [
        name
        for name, tokens in VISUAL_COMPANION_TOKENS.items()
        if any(token in code for token in tokens)
    ]

    issues: list[str] = []
    if formulas and not formula_hints:
        formula_hints.append("formula")
    if formulas and not visual_companions:
        issues.append("formula scene has no visual companion objects")

    for hint in formula_hints:
        required = REQUIRED_COMPANIONS.get(hint)
        if not required:
            continue
        if not required.intersection(visual_companions):
            issues.append(
                f"{hint} formula lacks expected visual companion: "
                + ", ".join(sorted(required))
            )

    return FormulaVisualBindingFinding(
        segment_id=segment_id,
        status="pass" if not issues else "block",
        issues=issues,
        formula_hints=formula_hints,
        visual_companions=visual_companions,
    )
