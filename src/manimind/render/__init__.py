"""Rendering helpers for turning generated scene code into reviewable evidence."""

from .manim_renderer import (
    DEFAULT_MANIM_BACKEND,
    FrameExtractionResult,
    ManimBackend,
    ManimRenderResult,
    build_manim_render_command,
    extract_keyframes,
    render_manim_scene,
    write_scene_code,
)

__all__ = [
    "DEFAULT_MANIM_BACKEND",
    "FrameExtractionResult",
    "ManimBackend",
    "ManimRenderResult",
    "build_manim_render_command",
    "extract_keyframes",
    "render_manim_scene",
    "write_scene_code",
]
