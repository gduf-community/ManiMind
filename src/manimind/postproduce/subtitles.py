"""Generate subtitle assets from narration scripts and segment render evidence."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..models import ContextScope, ProjectPlan
from .assembler import collect_segment_video_paths


@dataclass(slots=True)
class SubtitleCue:
    index: int
    segment_id: str
    start_seconds: float
    end_seconds: float
    text: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SubtitleBuildResult:
    project_id: str
    success: bool
    output_path: str
    cues: list[dict[str, object]] = field(default_factory=list)
    missing_segments: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SubtitleMuxResult:
    project_id: str
    success: bool
    video_path: str
    subtitle_path: str
    output_path: str
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SubtitleBurnResult:
    project_id: str
    success: bool
    video_path: str
    subtitle_path: str
    output_path: str
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_subtitle_file(
    plan: ProjectPlan,
    *,
    output_name: str | None = None,
    ffmpeg_executable: str | Path = "ffmpeg",
    timeout_seconds: int = 30,
) -> SubtitleBuildResult:
    """Build a project SRT aligned to actual rendered segment durations."""
    output_dir = Path(plan.runtime_layout.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (output_name or f"{plan.project_id}.srt")
    narration_by_segment = _narration_by_segment(plan)
    video_paths, missing_segments = collect_segment_video_paths(plan)
    result = SubtitleBuildResult(
        project_id=plan.project_id,
        success=False,
        output_path=str(output_path),
        missing_segments=missing_segments,
    )
    if missing_segments:
        result.error = "missing_segment_videos"
        return result
    if len(video_paths) != len(plan.segments):
        result.error = "segment_video_count_mismatch"
        return result

    cues: list[SubtitleCue] = []
    cursor = 0.0
    cue_index = 1
    for segment, video_path in zip(plan.segments, video_paths, strict=True):
        duration = _probe_video_duration(
            video_path,
            ffmpeg_executable=ffmpeg_executable,
            timeout_seconds=timeout_seconds,
        )
        if duration is None or duration <= 0:
            result.error = f"duration_probe_failed:{segment.id}"
            return result
        text = narration_by_segment.get(segment.id) or segment.narration
        chunks = _subtitle_chunks(text)
        if not chunks:
            cursor += duration
            continue
        chunk_weights = [max(1, len(chunk)) for chunk in chunks]
        weight_total = sum(chunk_weights)
        local_cursor = cursor
        for chunk_index, (chunk, weight) in enumerate(zip(chunks, chunk_weights, strict=True)):
            chunk_duration = duration * weight / weight_total
            chunk_end = (
                cursor + duration
                if chunk_index == len(chunks) - 1
                else local_cursor + chunk_duration
            )
            cues.append(
                SubtitleCue(
                    index=cue_index,
                    segment_id=segment.id,
                    start_seconds=local_cursor,
                    end_seconds=chunk_end,
                    text=_normalize_subtitle_text(chunk),
                )
            )
            cue_index += 1
            local_cursor = chunk_end
        cursor += duration

    output_path.write_text(_render_srt(cues), encoding="utf-8-sig")
    result.cues = [cue.to_dict() for cue in cues]
    result.success = True
    return result


def mux_subtitle_track(
    plan: ProjectPlan,
    *,
    video_path: str | Path | None = None,
    subtitle_path: str | Path | None = None,
    output_name: str | None = None,
    ffmpeg_executable: str | Path = "ffmpeg",
    timeout_seconds: int = 120,
) -> SubtitleMuxResult:
    """Mux an SRT file into an MP4 as a soft subtitle track."""
    output_dir = Path(plan.runtime_layout.output_dir)
    input_video = Path(video_path or output_dir / f"{plan.project_id}-final.mp4")
    input_subtitle = Path(subtitle_path or output_dir / f"{plan.project_id}.srt")
    output_path = output_dir / (output_name or f"{plan.project_id}-final-subtitled.mp4")
    result = SubtitleMuxResult(
        project_id=plan.project_id,
        success=False,
        video_path=str(input_video),
        subtitle_path=str(input_subtitle),
        output_path=str(output_path),
    )
    if not _existing_file(input_video):
        result.error = "video_missing"
        return result
    if not _existing_file(input_subtitle):
        result.error = "subtitle_missing"
        return result

    command = [
        str(ffmpeg_executable),
        "-y",
        "-i",
        str(input_video),
        "-i",
        str(input_subtitle),
        "-c:v",
        "copy",
        "-c:s",
        "mov_text",
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
        result.error = "ffmpeg_subtitle_mux_failed"
        return result
    if not _existing_file(output_path):
        result.error = "ffmpeg_succeeded_but_output_missing"
        return result

    result.success = True
    return result


def burn_subtitle_track(
    plan: ProjectPlan,
    *,
    video_path: str | Path | None = None,
    subtitle_path: str | Path | None = None,
    output_name: str | None = None,
    ffmpeg_executable: str | Path = "ffmpeg",
    timeout_seconds: int = 180,
) -> SubtitleBurnResult:
    """Burn an SRT subtitle file into video pixels for platform-safe previews."""
    output_dir = Path(plan.runtime_layout.output_dir)
    input_video = Path(video_path or output_dir / f"{plan.project_id}-final.mp4")
    input_subtitle = Path(subtitle_path or output_dir / f"{plan.project_id}.srt")
    output_path = output_dir / (output_name or f"{plan.project_id}-final-burned.mp4")
    result = SubtitleBurnResult(
        project_id=plan.project_id,
        success=False,
        video_path=str(input_video),
        subtitle_path=str(input_subtitle),
        output_path=str(output_path),
    )
    if not _existing_file(input_video):
        result.error = "video_missing"
        return result
    if not _existing_file(input_subtitle):
        result.error = "subtitle_missing"
        return result

    command = [
        str(ffmpeg_executable),
        "-y",
        "-i",
        str(input_video),
        "-vf",
        _subtitle_filter(input_subtitle),
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "veryfast",
        "-an",
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
        result.error = "ffmpeg_subtitle_burn_failed"
        return result
    if not _existing_file(output_path):
        result.error = "ffmpeg_succeeded_but_output_missing"
        return result

    result.success = True
    return result


def _narration_by_segment(plan: ProjectPlan) -> dict[str, str]:
    content = _read_context_content(plan, f"{plan.project_id}.narration.script")
    if not isinstance(content, dict):
        return {}
    narrations: dict[str, str] = {}
    segments = content.get("segments")
    if not isinstance(segments, list):
        return narrations
    for item in segments:
        if not isinstance(item, dict):
            continue
        segment_id = item.get("segment_id")
        text = item.get("narration_text")
        if isinstance(segment_id, str) and isinstance(text, str) and text.strip():
            narrations[segment_id] = _repair_mojibake(text.strip())
    return narrations


def _render_srt(cues: list[SubtitleCue]) -> str:
    blocks: list[str] = []
    for cue in cues:
        blocks.append(
            "\n".join([
                str(cue.index),
                f"{_format_srt_time(cue.start_seconds)} --> {_format_srt_time(cue.end_seconds)}",
                cue.text,
            ])
        )
    return "\n\n".join(blocks) + "\n"


def _format_srt_time(seconds: float) -> str:
    milliseconds_total = max(0, int(round(seconds * 1000)))
    milliseconds = milliseconds_total % 1000
    total_seconds = milliseconds_total // 1000
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _normalize_subtitle_text(text: str, max_line_chars: int = 32) -> str:
    text = _repair_mojibake(text)
    text = " ".join(text.strip().split())
    if len(text) <= max_line_chars:
        return text
    lines: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_line_chars, len(text))
        lines.append(text[start:end])
        start = end
    return "\n".join(lines)


def _subtitle_chunks(text: str, max_chunk_chars: int = 34) -> list[str]:
    text = _repair_mojibake(text)
    text = " ".join(text.strip().split())
    if not text:
        return []
    chunks: list[str] = []
    for sentence in _split_sentences(text):
        chunks.extend(_chunk_long_sentence(sentence, max_chunk_chars=max_chunk_chars))
    return chunks


def _split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    terminators = "。！？；.!?;"
    for index, char in enumerate(text):
        if char in terminators:
            sentence = text[start : index + 1].strip()
            if sentence:
                sentences.append(sentence)
            start = index + 1
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _chunk_long_sentence(sentence: str, *, max_chunk_chars: int) -> list[str]:
    if len(sentence) <= max_chunk_chars:
        return [sentence]
    chunks: list[str] = []
    start = 0
    soft_breaks = "，、, "
    while start < len(sentence):
        end = min(start + max_chunk_chars, len(sentence))
        if end < len(sentence):
            break_at = max(sentence.rfind(mark, start, end) for mark in soft_breaks)
            if break_at > start + max_chunk_chars // 2:
                end = break_at + 1
        chunks.append(sentence[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]


def _repair_mojibake(text: str) -> str:
    """Repair the common GBK-as-Latin-1 mojibake seen in old runtime contexts."""
    if not _looks_like_latin1_mojibake(text):
        return text
    try:
        repaired = text.encode("latin-1").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return repaired if _has_cjk(repaired) else text


def _looks_like_latin1_mojibake(text: str) -> bool:
    markers = ("Ï", "Î", "Ã", "Ç", "Ê", "£", "¡", "µ", "Æ", "Ð")
    return any(marker in text for marker in markers)


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _probe_video_duration(
    video_path: str | Path,
    *,
    ffmpeg_executable: str | Path = "ffmpeg",
    timeout_seconds: int = 30,
) -> float | None:
    ffprobe = _ffprobe_executable(ffmpeg_executable)
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        str(video_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return None


def _ffprobe_executable(ffmpeg_executable: str | Path) -> str:
    path = Path(ffmpeg_executable)
    if path.name.lower().startswith("ffmpeg"):
        return str(path.with_name(path.name.replace("ffmpeg", "ffprobe", 1)))
    return "ffprobe"


def _subtitle_filter(path: Path) -> str:
    escaped = str(path.resolve()).replace("\\", "/")
    escaped = escaped.replace(":", "\\:").replace("'", "\\'")
    return f"subtitles='{escaped}'"


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
