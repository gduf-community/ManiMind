"""Deterministic checks for rendered video evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .frame_quality import FrameQualityMetrics, analyze_frame_quality
from .motion_quality import MotionQualityMetrics, analyze_motion_quality


@dataclass(slots=True)
class RenderEvidenceFinding:
    segment_id: str
    status: str
    issues: list[str] = field(default_factory=list)
    video_path: str | None = None
    frame_paths: list[str] = field(default_factory=list)
    frame_quality: list[dict[str, object]] = field(default_factory=list)
    motion_quality: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_render_evidence(
    evidence: dict[str, Any],
    *,
    approved_manim: dict[str, Any] | None = None,
) -> RenderEvidenceFinding:
    """Assess one ``*.render_evidence`` context payload without using an LLM."""
    segment_id = str(evidence.get("segment_id") or "unknown")
    render = evidence.get("render") if isinstance(evidence.get("render"), dict) else {}
    frames = evidence.get("frames") if isinstance(evidence.get("frames"), dict) else {}
    issues: list[str] = []
    quality_results: list[FrameQualityMetrics] = []
    motion_result: MotionQualityMetrics | None = None

    if not render.get("success"):
        issues.append(render.get("error") or "manim render did not succeed")

    if approved_manim and evidence_code_is_stale(approved_manim, evidence):
        issues.append(
            "rendered code is stale: render.code_path does not match approved scene_code"
        )

    video_path = render.get("video_path")
    if not isinstance(video_path, str) or not video_path:
        issues.append("render evidence is missing video_path")
        video_path = None
    elif not _existing_nonempty_file(video_path):
        issues.append(f"video_path does not exist or is empty: {video_path}")

    if not frames.get("success"):
        issues.append(frames.get("error") or "frame extraction did not succeed")

    raw_frame_paths = frames.get("frame_paths", [])
    frame_paths = [path for path in raw_frame_paths if isinstance(path, str)]
    if not frame_paths:
        issues.append("render evidence has no extracted frame paths")
    else:
        missing_frames = [
            path for path in frame_paths if not _existing_nonempty_file(path)
        ]
        if missing_frames:
            issues.append(
                "frame paths do not exist or are empty: "
                + ", ".join(missing_frames[:3])
            )
        else:
            quality_results = [analyze_frame_quality(path) for path in frame_paths]
            for quality in quality_results:
                issues.extend(
                    f"{Path(quality.frame_path).name}: {issue}"
                    for issue in quality.issues
                )
            if not any(quality.issues for quality in quality_results):
                motion_result = analyze_motion_quality(frame_paths)
                issues.extend(
                    f"motion continuity: {issue}"
                    for issue in motion_result.issues
                )

    return RenderEvidenceFinding(
        segment_id=segment_id,
        status="pass" if not issues else "block",
        issues=issues,
        video_path=video_path,
        frame_paths=frame_paths,
        frame_quality=[
            quality.to_dict()
            for quality in quality_results
        ],
        motion_quality=motion_result.to_dict() if motion_result else None,
    )


def _existing_nonempty_file(path: str) -> bool:
    target = Path(path)
    return target.exists() and target.is_file() and target.stat().st_size > 0


def evidence_code_is_stale(
    approved_manim: dict[str, Any],
    evidence: dict[str, Any],
) -> bool:
    """Return True when render evidence points at code older than approved Manim."""
    approved_code = approved_manim.get("scene_code")
    render = evidence.get("render") if isinstance(evidence.get("render"), dict) else {}
    code_path = render.get("code_path") if isinstance(render, dict) else None
    if not isinstance(approved_code, str) or not isinstance(code_path, str):
        return False
    path = Path(code_path)
    if not path.exists() or not path.is_file():
        return True
    try:
        rendered_code = path.read_text(encoding="utf-8")
    except OSError:
        return True
    return rendered_code != approved_code
