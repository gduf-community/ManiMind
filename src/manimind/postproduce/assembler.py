"""Assemble reviewed Manim segment videos into a project-level preview cut."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..models import ContextScope, ProjectPlan


@dataclass(slots=True)
class VideoAssemblyResult:
    project_id: str
    success: bool
    output_path: str
    concat_list_path: str
    segment_video_paths: list[str] = field(default_factory=list)
    missing_segments: list[str] = field(default_factory=list)
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def collect_segment_video_paths(plan: ProjectPlan) -> tuple[list[str], list[str]]:
    """Collect Manim render evidence video paths in manifest segment order."""
    video_paths: list[str] = []
    missing_segments: list[str] = []
    for segment in plan.segments:
        evidence = _read_context_content(
            plan,
            f"{plan.project_id}.manim.{segment.id}.render_evidence",
        )
        render = evidence.get("render") if isinstance(evidence, dict) else {}
        video_path = render.get("video_path") if isinstance(render, dict) else None
        if not isinstance(video_path, str) or not _existing_file(video_path):
            missing_segments.append(segment.id)
            continue
        video_paths.append(video_path)
    return video_paths, missing_segments


def assemble_manim_video(
    plan: ProjectPlan,
    *,
    output_name: str | None = None,
    ffmpeg_executable: str | Path = "ffmpeg",
    timeout_seconds: int = 120,
) -> VideoAssemblyResult:
    """Concatenate reviewed Manim segment videos into one mp4 preview cut."""
    output_dir = Path(plan.runtime_layout.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_output_name = output_name or f"{plan.project_id}-final.mp4"
    output_path = output_dir / safe_output_name
    concat_list_path = output_dir / "concat-list.txt"
    segment_video_paths, missing_segments = collect_segment_video_paths(plan)
    result = VideoAssemblyResult(
        project_id=plan.project_id,
        success=False,
        output_path=str(output_path),
        concat_list_path=str(concat_list_path),
        segment_video_paths=segment_video_paths,
        missing_segments=missing_segments,
    )
    if missing_segments:
        result.error = "missing_segment_videos"
        return result
    if not segment_video_paths:
        result.error = "no_segment_videos"
        return result

    _write_concat_list(concat_list_path, segment_video_paths)
    command = [
        str(ffmpeg_executable),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-c",
        "copy",
        str(output_path),
    ]
    result.command = command
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        result.error = f"ffmpeg_not_found: {exc}"
        return result
    except subprocess.TimeoutExpired as exc:
        result.error = f"ffmpeg_timeout_after_{timeout_seconds}s"
        result.stdout_tail = _tail(exc.stdout)
        result.stderr_tail = _tail(exc.stderr)
        return result

    result.exit_code = completed.returncode
    result.stdout_tail = _tail(completed.stdout)
    result.stderr_tail = _tail(completed.stderr)
    if completed.returncode != 0:
        result.error = "ffmpeg_concat_failed"
        return result
    if not _existing_file(output_path):
        result.error = "ffmpeg_succeeded_but_output_missing"
        return result

    result.success = True
    return result


def _write_concat_list(path: Path, video_paths: list[str]) -> None:
    lines = [
        f"file '{_escape_concat_path(Path(video_path).resolve())}'"
        for video_path in video_paths
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _escape_concat_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "'\\''")


def _read_context_content(plan: ProjectPlan, key: str) -> object | None:
    path = _context_file_path(plan, key, ContextScope.LONG_TERM)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("content") if isinstance(payload, dict) else payload


def _context_file_path(plan: ProjectPlan, key: str, scope: ContextScope) -> Path:
    if scope == ContextScope.LONG_TERM:
        base = Path(plan.runtime_layout.project_context_dir)
    else:
        base = Path(plan.runtime_layout.session_context_root)
    return base / f"{key.replace('.', '-')}.json"


def _existing_file(path: str | Path) -> bool:
    target = Path(path)
    return target.exists() and target.is_file() and target.stat().st_size > 0


def _tail(value: str | bytes | None, max_chars: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-max_chars:]
