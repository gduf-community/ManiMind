"""Temporal motion checks for extracted render frames."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import subprocess

from .frame_quality import _load_rgb_pixels, _rgb_to_luma


@dataclass(slots=True)
class MotionQualityMetrics:
    frame_paths: list[str]
    frame_count: int = 0
    mean_luma_delta: float = 0.0
    changed_pixel_ratio: float = 0.0
    status: str = "block"
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def analyze_motion_quality(
    frame_paths: list[str | Path],
    *,
    ffmpeg_executable: str | Path = "ffmpeg",
    min_frame_count: int = 2,
    min_mean_luma_delta: float = 1.5,
    min_changed_pixel_ratio: float = 0.01,
    changed_pixel_threshold: float = 8.0,
) -> MotionQualityMetrics:
    """Measure whether extracted frames show meaningful temporal change."""
    paths = [Path(path) for path in frame_paths]
    metrics = MotionQualityMetrics(frame_paths=[str(path) for path in paths])
    metrics.frame_count = len(paths)

    if len(paths) < min_frame_count:
        metrics.issues.append(
            f"motion check needs at least {min_frame_count} frames, got {len(paths)}"
        )
        return metrics

    frames: list[tuple[int, int, list[float]]] = []
    try:
        for path in paths:
            width, height, rgb = _load_rgb_pixels(path, ffmpeg_executable)
            frames.append((width, height, _rgb_to_luma(rgb)))
    except (FileNotFoundError, ValueError, subprocess.SubprocessError) as exc:
        metrics.issues.append(f"frame could not be decoded for motion check: {exc}")
        return metrics

    dimensions = {(width, height) for width, height, _ in frames}
    if len(dimensions) != 1:
        metrics.issues.append("motion check frames have inconsistent dimensions")
        return metrics

    total_delta = 0.0
    changed_pixels = 0
    comparisons = 0
    for (_, _, previous), (_, _, current) in zip(frames, frames[1:]):
        for before, after in zip(previous, current):
            delta = abs(after - before)
            total_delta += delta
            if delta >= changed_pixel_threshold:
                changed_pixels += 1
            comparisons += 1

    if comparisons == 0:
        metrics.issues.append("motion check has no comparable pixels")
        return metrics

    metrics.mean_luma_delta = round(total_delta / comparisons, 3)
    metrics.changed_pixel_ratio = round(changed_pixels / comparisons, 5)

    if metrics.mean_luma_delta < min_mean_luma_delta:
        metrics.issues.append(
            f"frame-to-frame luma change too low: {metrics.mean_luma_delta}, expected at least {min_mean_luma_delta}"
        )
    if metrics.changed_pixel_ratio < min_changed_pixel_ratio:
        metrics.issues.append(
            f"changed pixel ratio too low: {metrics.changed_pixel_ratio}, expected at least {min_changed_pixel_ratio}"
        )

    metrics.status = "pass" if not metrics.issues else "block"
    return metrics
