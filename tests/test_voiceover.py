import json
import subprocess
from pathlib import Path

from manimind.bootstrap import build_runtime_layout
from manimind.models import RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle
from manimind.postproduce import build_voiceover_audio, mux_voiceover_track
from manimind.workflow import build_project_plan


def _plan(root: Path):
    plan = build_project_plan(
        project_id="voice-demo",
        title="Voice Demo",
        source_bundle=SourceBundle(paper_path="paper.pdf"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="one",
                goal="Show one",
                narration="Fallback one.",
                modality=SegmentModality.MANIM,
            )
        ],
    )
    layout = build_runtime_layout("voice-demo", root=root)
    plan.runtime_layout = RuntimeLayout(
        project_context_dir=layout.project_context_dir,
        session_context_root=layout.session_context_root,
        output_dir=layout.output_dir,
        bootstrap_report=layout.bootstrap_report,
        doctor_report=layout.doctor_report,
    )
    return plan


def _write_context(plan, key: str, content) -> None:
    path = Path(plan.runtime_layout.project_context_dir) / f"{key.replace('.', '-')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"key": key, "content": content}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_build_voiceover_audio_writes_text_and_audio(monkeypatch, tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    _write_context(
        plan,
        "voice-demo.narration.script",
        {"segments": [{"segment_id": "seg-1", "narration_text": "第一段旁白。"}]},
    )

    def fake_run(command, **kwargs):
        script = command[-1]
        marker = "SetOutputToWaveFile('"
        start = script.index(marker) + len(marker)
        end = script.index("');", start)
        Path(script[start:end]).write_bytes(b"wav")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = build_voiceover_audio(
        plan,
        voice_name="Test Voice",
        rate=1,
        platform_name="win32",
    )

    assert result.success is True
    assert Path(result.output_path).read_bytes() == b"wav"
    assert "第一段旁白。" in Path(result.narration_text_path).read_text(encoding="utf-8")
    assert "Test Voice" in result.command[-1]
    assert "$s.Rate=1" in result.command[-1]


def test_build_voiceover_audio_uses_macos_say(monkeypatch, tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    def fake_run(command, **kwargs):
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_bytes(b"wav")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = build_voiceover_audio(
        plan,
        voice_name="Tingting",
        rate=2,
        platform_name="darwin",
    )

    assert result.success is True
    assert result.command[0] == "say"
    assert result.command[1:3] == ["-v", "Tingting"]
    assert result.command[3:5] == ["-r", "210"]
    assert "--file-format=WAVE" in result.command
    assert Path(result.output_path).read_bytes() == b"wav"


def test_mux_voiceover_track_scales_video_when_durations_differ(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    output_dir = Path(plan.runtime_layout.output_dir)
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    video = output_dir / "voice-demo-final-burned.mp4"
    audio = audio_dir / "voice-demo-voiceover.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    durations = iter(["10.0\n", "15.0\n"])

    def fake_run(command, **kwargs):
        if "ffprobe" in str(command[0]):
            return subprocess.CompletedProcess(command, 0, next(durations), "")
        Path(command[-1]).write_bytes(b"muxed")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = mux_voiceover_track(plan)

    assert result.success is True
    assert result.video_duration_seconds == 10.0
    assert result.audio_duration_seconds == 15.0
    assert Path(result.output_path).read_bytes() == b"muxed"
    assert "-filter_complex" in result.command
    assert any("setpts=1.500000*PTS" in item for item in result.command)


def test_mux_voiceover_track_blocks_missing_audio(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    output_dir = Path(plan.runtime_layout.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "voice-demo-final-burned.mp4").write_bytes(b"video")

    result = mux_voiceover_track(plan)

    assert result.success is False
    assert result.error == "audio_missing"
