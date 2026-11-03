"""Basic frame quality metrics for rendered animation evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import sqrt
from pathlib import Path
import subprocess


@dataclass(slots=True)
class FrameQualityMetrics:
    frame_path: str
    width: int = 0
    height: int = 0
    mean_luma: float = 0.0
    contrast: float = 0.0
    edge_density: float = 0.0
    status: str = "block"
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def analyze_frame_quality(
    frame_path: str | Path,
    *,
    ffmpeg_executable: str | Path = "ffmpeg",
    min_width: int = 640,
    min_height: int = 360,
    min_contrast: float = 8.0,
    min_edge_density: float = 0.0015,
) -> FrameQualityMetrics:
    """Return simple visual quality metrics for one frame.

    The thresholds are deliberately modest. They are meant to catch blank,
    corrupt, tiny, or near-static frames before a more subjective visual review.
    """
    path = Path(frame_path)
    metrics = FrameQualityMetrics(frame_path=str(path))
    try:
        width, height, rgb = _load_rgb_pixels(path, ffmpeg_executable)
    except (FileNotFoundError, ValueError, subprocess.SubprocessError) as exc:
        metrics.issues.append(f"frame could not be decoded: {exc}")
        return metrics

    metrics.width = width
    metrics.height = height
    lumas = _rgb_to_luma(rgb)
    if not lumas:
        metrics.issues.append("frame has no pixels")
        return metrics

    mean = sum(lumas) / len(lumas)
    variance = sum((value - mean) ** 2 for value in lumas) / len(lumas)
    metrics.mean_luma = round(mean, 3)
    metrics.contrast = round(sqrt(variance), 3)
    metrics.edge_density = round(_edge_density(lumas, width, height), 5)

    if width < min_width or height < min_height:
        metrics.issues.append(
            f"frame resolution too low: {width}x{height}, expected at least {min_width}x{min_height}"
        )
    if mean < 2.0:
        metrics.issues.append("frame is near-black")
    if mean > 253.0:
        metrics.issues.append("frame is near-white")
    if metrics.contrast < min_contrast:
        metrics.issues.append(
            f"frame contrast too low: {metrics.contrast}, expected at least {min_contrast}"
        )
    if metrics.edge_density < min_edge_density:
        metrics.issues.append(
            f"frame visual detail too low: {metrics.edge_density}, expected at least {min_edge_density}"
        )

    metrics.status = "pass" if not metrics.issues else "block"
    return metrics


def _load_rgb_pixels(
    path: Path,
    ffmpeg_executable: str | Path,
) -> tuple[int, int, bytes]:
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(str(path))
    data = path.read_bytes()
    if data.startswith(b"P6"):
        return _parse_ppm(data)

    completed = subprocess.run(
        [
            str(ffmpeg_executable),
            "-v",
            "error",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "ppm",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace")[-500:]
        raise ValueError(error or "ffmpeg failed to decode frame")
    return _parse_ppm(completed.stdout)


def _parse_ppm(data: bytes) -> tuple[int, int, bytes]:
    tokens: list[bytes] = []
    index = 0
    while len(tokens) < 4:
        while index < len(data) and data[index:index + 1].isspace():
            index += 1
        if index < len(data) and data[index:index + 1] == b"#":
            while index < len(data) and data[index:index + 1] not in {b"\n", b"\r"}:
                index += 1
            continue
        start = index
        while index < len(data) and not data[index:index + 1].isspace():
            index += 1
        tokens.append(data[start:index])
    if tokens[0] != b"P6":
        raise ValueError("expected binary PPM P6 frame")
    width = int(tokens[1])
    height = int(tokens[2])
    max_value = int(tokens[3])
    if max_value != 255:
        raise ValueError("only 8-bit PPM frames are supported")
    if data[index:index + 2] == b"\r\n":
        index += 2
    elif index < len(data) and data[index:index + 1].isspace():
        index += 1
    else:
        raise ValueError("PPM header is missing the pixel-data separator")
    rgb = data[index:]
    expected = width * height * 3
    if len(rgb) < expected:
        raise ValueError("PPM pixel data is truncated")
    return width, height, rgb[:expected]


def _rgb_to_luma(rgb: bytes) -> list[float]:
    return [
        0.2126 * rgb[index] + 0.7152 * rgb[index + 1] + 0.0722 * rgb[index + 2]
        for index in range(0, len(rgb), 3)
    ]


def _edge_density(lumas: list[float], width: int, height: int) -> float:
    if width < 2 or height < 2:
        return 0.0
    edge_count = 0
    comparisons = 0
    threshold = 20.0
    for y in range(height - 1):
        row = y * width
        next_row = (y + 1) * width
        for x in range(width - 1):
            value = lumas[row + x]
            if abs(value - lumas[row + x + 1]) > threshold:
                edge_count += 1
            if abs(value - lumas[next_row + x]) > threshold:
                edge_count += 1
            comparisons += 2
    return edge_count / comparisons if comparisons else 0.0
