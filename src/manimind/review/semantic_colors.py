"""Cross-segment semantic color consistency checks for Manim code."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


COLOR_NAMES = (
    "BLUE",
    "BLUE_A",
    "BLUE_B",
    "BLUE_C",
    "YELLOW",
    "YELLOW_A",
    "YELLOW_B",
    "YELLOW_C",
    "GREEN",
    "GREEN_A",
    "GREEN_B",
    "GREEN_C",
    "RED",
    "RED_A",
    "RED_B",
    "RED_C",
    "PURPLE",
    "PURPLE_A",
    "PURPLE_B",
    "PURPLE_C",
    "GOLD",
    "TEAL",
    "ORANGE",
    "WHITE",
    "GREY",
    "GRAY",
)

_MAP_ENTRY_RE = re.compile(
    r"""(?P<symbol>[rubf]*["'][^"']+["'])\s*:\s*(?P<color>[A-Z][A-Z0-9_]*)"""
)
_SET_COLOR_BY_TEX_RE = re.compile(
    r"""set_color_by_tex\(\s*(?P<symbol>[rubf]*["'][^"']+["'])\s*,\s*(?P<color>[A-Z][A-Z0-9_]*)"""
)


@dataclass(slots=True)
class SemanticColorFinding:
    status: str
    issues: list[str] = field(default_factory=list)
    symbol_colors: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_semantic_color_consistency(
    manim_outputs: list[dict[str, Any]],
) -> SemanticColorFinding:
    """Check that repeated math symbols keep the same color across segments."""
    symbol_colors: dict[str, dict[str, list[str]]] = {}

    for item in manim_outputs:
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("segment_id") or "unknown")
        content = item.get("content")
        if not isinstance(content, dict):
            continue
        code = content.get("scene_code")
        if not isinstance(code, str):
            continue
        for symbol, color in extract_semantic_color_map(code).items():
            colors = symbol_colors.setdefault(symbol, {})
            segments = colors.setdefault(color, [])
            if segment_id not in segments:
                segments.append(segment_id)

    issues: list[str] = []
    for symbol, colors in sorted(symbol_colors.items()):
        if len(colors) > 1:
            desc = ", ".join(
                f"{color} in {segments}"
                for color, segments in sorted(colors.items())
            )
            issues.append(f"symbol {symbol!r} uses inconsistent colors: {desc}")

    return SemanticColorFinding(
        status="pass" if not issues else "block",
        issues=issues,
        symbol_colors=symbol_colors,
    )


def extract_semantic_color_map(code: str) -> dict[str, str]:
    """Extract common Manim tex-to-color mappings from generated scene code."""
    colors: dict[str, str] = {}
    for match in _MAP_ENTRY_RE.finditer(code):
        color = match.group("color")
        if color in COLOR_NAMES:
            colors[_clean_symbol(match.group("symbol"))] = color
    for match in _SET_COLOR_BY_TEX_RE.finditer(code):
        color = match.group("color")
        if color in COLOR_NAMES:
            colors[_clean_symbol(match.group("symbol"))] = color
    return colors


def _clean_symbol(raw: str) -> str:
    symbol = raw.strip()
    while symbol and symbol[0] in "rubfRUBF":
        symbol = symbol[1:]
    if len(symbol) >= 2 and symbol[0] in {"'", '"'} and symbol[-1] == symbol[0]:
        symbol = symbol[1:-1]
    return symbol.strip()
