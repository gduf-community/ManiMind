"""Deterministic checks for 3B1B-oriented Manim scene code quality."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


ANIMATION_TOKENS = (
    "self.play",
    "Create(",
    "ShowCreation(",
    "Write(",
    "FadeIn(",
    "Transform(",
    "ReplacementTransform(",
    "TransformMatchingTex(",
    "TransformMatchingShapes(",
    "LaggedStart(",
    "AnimationGroup(",
)

VISUAL_ANCHOR_TOKENS = (
    "Axes(",
    "NumberPlane(",
    "Line(",
    "Arrow(",
    "Vector(",
    "Dot(",
    "Circle(",
    "Square(",
    "Rectangle(",
    "Polygon(",
    "ParametricFunction(",
    ".plot(",
    ".get_graph(",
)

MOTION_TOKENS = (
    "ValueTracker",
    "always_redraw",
    "add_updater",
    ".animate",
    "rate_func=",
)

COLOR_TOKENS = (
    "BLUE",
    "YELLOW",
    "GREEN",
    "RED",
    "PURPLE",
    "GOLD",
    "TEAL",
    "set_color",
    "color=",
    "tex_to_color_map",
)

DYNAMIC_TEX_REDRAW_RE = re.compile(
    r"always_redraw\s*\(\s*lambda\s*:\s*(?:Math)?Tex\s*\(",
    re.MULTILINE,
)


@dataclass(slots=True)
class ManimCodeQualityFinding:
    segment_id: str
    status: str
    issues: list[str] = field(default_factory=list)
    metrics: dict[str, int | bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_manim_code_quality(
    segment: dict[str, Any],
    *,
    formula_required: bool = False,
) -> ManimCodeQualityFinding:
    """Assess one generated Manim segment for basic explainer quality signals."""
    segment_id = str(segment.get("segment_id") or "unknown")
    code = segment.get("scene_code")
    issues: list[str] = []
    if not isinstance(code, str) or not code.strip():
        return ManimCodeQualityFinding(
            segment_id=segment_id,
            status="block",
            issues=["manim segment is missing scene_code"],
            metrics={},
        )

    metrics: dict[str, int | bool] = {
        "line_count": len([line for line in code.splitlines() if line.strip()]),
        "animation_count": _count_tokens(code, ANIMATION_TOKENS),
        "wait_count": code.count("self.wait"),
        "visual_anchor_count": _count_tokens(code, VISUAL_ANCHOR_TOKENS),
        "motion_signal_count": _count_tokens(code, MOTION_TOKENS),
        "color_signal_count": _count_tokens(code, COLOR_TOKENS),
        "uses_mathtex": "MathTex(" in code,
        "uses_tex": "Tex(" in code or "MathTex(" in code,
        "uses_text": "Text(" in code or "Tex(" in code,
        "dynamic_tex_redraw_count": len(DYNAMIC_TEX_REDRAW_RE.findall(code)),
    }

    if metrics["line_count"] < 12:
        issues.append("scene code is too short to support a polished explanatory beat")
    if metrics["animation_count"] < 2:
        issues.append("scene has too few animation steps")
    if metrics["wait_count"] < 1:
        issues.append("scene has no reading pause via self.wait")
    if metrics["visual_anchor_count"] < 1:
        issues.append("scene lacks a visual anchor such as axes, geometry, graph, or marked point")
    if metrics["color_signal_count"] < 2:
        issues.append("scene lacks semantic color signals")
    if formula_required and not metrics["uses_tex"]:
        issues.append("formula segment does not use a Tex/MathTex formula object")
    if formula_required and metrics["visual_anchor_count"] < 1:
        issues.append("formula segment shows symbols without a geometric or visual companion")
    if metrics["motion_signal_count"] < 1 and metrics["animation_count"] < 4:
        issues.append("scene lacks continuous motion or sufficiently staged transformations")
    if metrics["dynamic_tex_redraw_count"] > 0:
        issues.append(
            "scene creates Tex inside always_redraw; use DecimalNumber or an updater "
            "to avoid per-frame LaTeX compilation"
        )

    return ManimCodeQualityFinding(
        segment_id=segment_id,
        status="pass" if not issues else "block",
        issues=issues,
        metrics=metrics,
    )


def _count_tokens(code: str, tokens: tuple[str, ...]) -> int:
    return sum(code.count(token) for token in tokens)
