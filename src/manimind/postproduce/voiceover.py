"""Offline voiceover generation and muxing for preview cuts."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
import sys

from ..models import ContextScope, ProjectPlan
from .subtitles import _repair_mojibake


@dataclass(slots=True)
class VoiceoverBuildResult:
    project_id: str
    success: bool
    output_path: str
    narration_text_path: str
    voice_name: str | None = None
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class VoiceoverMuxResult:
    project_id: str
    success: bool
    video_path: str
    audio_path: str
    output_path: str
    video_duration_seconds: float | None = None
    audio_duration_seconds: float | None = None
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_voiceover_audio(
    plan: ProjectPlan,
    *,
    output_name: str | None = None,
    voice_name: str | None = None,
    rate: int = 0,
    powershell_executable: str | Path = "powershell",
    say_executable: str | Path = "say",
    platform_name: str | None = None,
    timeout_seconds: int = 180,
) -> VoiceoverBuildResult:
    """Generate a WAV voiceover with the native Windows or macOS synthesizer."""
    output_dir = Path(plan.runtime_layout.output_dir)
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / (output_name or f"{plan.project_id}-voiceover.wav")
    text_path = audio_dir / f"{plan.project_id}-voiceover.txt"
    text = "\n\n".join(_narration_texts(plan))
    text_path.write_text(text, encoding="utf-8")
    result = VoiceoverBuildResult(
        project_id=plan.project_id,
        success=False,
        output_path=str(audio_path),
        narration_text_path=str(text_path),
        voice_name=voice_name,
    )
    if not text.strip():
        result.error = "narration_text_missing"
        return result

    selected_platform = platform_name or sys.platform
    if selected_platform == "darwin":
        command = _macos_say_command(
            text_path=text_path,
            audio_path=audio_path,
            voice_name=voice_name,
            rate=rate,
            say_executable=say_executable,
        )
        provider = "say"
    else:
        command = [
            str(powershell_executable),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _sapi_powershell_script(
                text_path=text_path,
                audio_path=audio_path,
                voice_name=voice_name,
                rate=rate,
            ),
        ]
        provider = "sapi"
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
        result.error = f"{provider}_not_found: {exc}"
        return result
    except subprocess.TimeoutExpired as exc:
        result.error = f"{provider}_timeout_after_{timeout_seconds}s"
        result.stdout_tail = _tail(exc.stdout)
        result.stderr_tail = _tail(exc.stderr)
        return result

    result.exit_code = completed.returncode
    result.stdout_tail = _tail(completed.stdout)
    result.stderr_tail = _tail(completed.stderr)
    if completed.returncode != 0:
        result.error = f"{provider}_voiceover_failed"
        return result
    if not _existing_file(audio_path):
        result.error = f"{provider}_succeeded_but_audio_missing"
        return result

    result.success = True
    return result


def mux_voiceover_track(
    plan: ProjectPlan,
    *,
    video_path: str | Path | None = None,
    audio_path: str | Path | None = None,
    output_name: str | None = None,
    ffmpeg_executable: str | Path = "ffmpeg",
    timeout_seconds: int = 180,
) -> VoiceoverMuxResult:
    """Mux generated voiceover into video, time-scaling video to audio duration."""
    output_dir = Path(plan.runtime_layout.output_dir)
    input_video = Path(video_path or output_dir / f"{plan.project_id}-final-burned.mp4")
    input_audio = Path(audio_path or output_dir / "audio" / f"{plan.project_id}-voiceover.wav")
    output_path = output_dir / (output_name or f"{plan.project_id}-final-voiceover.mp4")
    result = VoiceoverMuxResult(
        project_id=plan.project_id,
        success=False,
        video_path=str(input_video),
        audio_path=str(input_audio),
        output_path=str(output_path),
    )
    if not _existing_file(input_video):
        result.error = "video_missing"
        return result
    if not _existing_file(input_audio):
        result.error = "audio_missing"
        return result

    video_duration = _probe_media_duration(
        input_video,
        ffmpeg_executable=ffmpeg_executable,
        timeout_seconds=timeout_seconds,
    )
    audio_duration = _probe_media_duration(
        input_audio,
        ffmpeg_executable=ffmpeg_executable,
        timeout_seconds=timeout_seconds,
    )
    result.video_duration_seconds = video_duration
    result.audio_duration_seconds = audio_duration
    if not video_duration or not audio_duration:
        result.error = "duration_probe_failed"
        return result

    command = _build_voiceover_mux_command(
        input_video=input_video,
        input_audio=input_audio,
        output_path=output_path,
        video_duration=video_duration,
        audio_duration=audio_duration,
        ffmpeg_executable=ffmpeg_executable,
    )
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
        result.error = "ffmpeg_voiceover_mux_failed"
        return result
    if not _existing_file(output_path):
        result.error = "ffmpeg_succeeded_but_output_missing"
        return result

    result.success = True
    return result


def _build_voiceover_mux_command(
    *,
    input_video: Path,
    input_audio: Path,
    output_path: Path,
    video_duration: float,
    audio_duration: float,
    ffmpeg_executable: str | Path,
) -> list[str]:
    ratio = audio_duration / video_duration
    if abs(ratio - 1.0) < 0.03:
        return [
            str(ffmpeg_executable),
            "-y",
            "-i",
            str(input_video),
            "-i",
            str(input_audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(output_path),
        ]
    return [
        str(ffmpeg_executable),
        "-y",
        "-i",
        str(input_video),
        "-i",
        str(input_audio),
        "-filter_complex",
        f"[0:v]setpts={ratio:.6f}*PTS[v]",
        "-map",
        "[v]",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
        str(output_path),
    ]


def _narration_texts(plan: ProjectPlan) -> list[str]:
    content = _read_context_content(plan, f"{plan.project_id}.narration.script")
    texts: list[str] = []
    if isinstance(content, dict) and isinstance(content.get("segments"), list):
        for item in content["segments"]:
            if not isinstance(item, dict):
                continue
            text = item.get("narration_text")
            if isinstance(text, str) and text.strip():
                texts.append(_repair_mojibake(text.strip()))
    if texts:
        return texts
    return [
        _repair_mojibake(segment.narration)
        for segment in plan.segments
        if segment.narration
    ]


def _sapi_powershell_script(
    *,
    text_path: Path,
    audio_path: Path,
    voice_name: str | None,
    rate: int,
) -> str:
    voice_line = (
        f"$s.SelectVoice('{_ps_single_quote(voice_name)}');"
        if voice_name
        else ""
    )
    return (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"{voice_line}"
        f"$s.Rate={rate};"
        f"$text=Get-Content -LiteralPath '{_ps_single_quote(str(text_path.resolve()))}' -Raw -Encoding UTF8;"
        f"$s.SetOutputToWaveFile('{_ps_single_quote(str(audio_path.resolve()))}');"
        "$s.Speak($text);"
        "$s.Dispose();"
    )


def _macos_say_command(
    *,
    text_path: Path,
    audio_path: Path,
    voice_name: str | None,
    rate: int,
    say_executable: str | Path,
) -> list[str]:
    command = [str(say_executable)]
    if voice_name:
        command.extend(["-v", voice_name])
    if rate:
        words_per_minute = max(80, 180 + rate * 15)
        command.extend(["-r", str(words_per_minute)])
    command.extend(
        [
            "--file-format=WAVE",
            "--data-format=LEI16@22050",
            "-o",
            str(audio_path.resolve()),
            "-f",
            str(text_path.resolve()),
        ]
    )
    return command


def _probe_media_duration(
    path: str | Path,
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
        str(path),
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


def _ps_single_quote(value: str) -> str:
    return value.replace("'", "''")


def _existing_file(path: str | Path) -> bool:
    target = Path(path)
    return target.exists() and target.is_file() and target.stat().st_size > 0


def _tail(value: str | bytes | None, max_chars: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-max_chars:]
