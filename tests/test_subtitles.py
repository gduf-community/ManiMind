import json
import subprocess
from pathlib import Path

from manimind.bootstrap import build_runtime_layout
from manimind.models import RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle
from manimind.postproduce import (
    build_subtitle_file,
    burn_subtitle_track,
    mux_subtitle_track,
)
from manimind.postproduce.subtitles import _normalize_subtitle_text, _subtitle_chunks
from manimind.workflow import build_project_plan


def _plan(root: Path):
    plan = build_project_plan(
        project_id="subtitle-demo",
        title="Subtitle Demo",
        source_bundle=SourceBundle(paper_path="paper.pdf"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="one",
                goal="Show one",
                narration="Fallback one.",
                modality=SegmentModality.MANIM,
            ),
            SegmentSpec(
                id="seg-2",
                title="two",
                goal="Show two",
                narration="Fallback two.",
                modality=SegmentModality.MANIM,
            ),
        ],
    )
    layout = build_runtime_layout("subtitle-demo", root=root)
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


def _write_render_evidence(plan, segment_id: str, video_path: Path) -> None:
    _write_context(
        plan,
        f"subtitle-demo.manim.{segment_id}.render_evidence",
        {
            "segment_id": segment_id,
            "render": {"success": True, "video_path": str(video_path)},
            "frames": {"success": True, "frame_paths": []},
        },
    )


def test_build_subtitle_file_uses_narration_script_and_actual_durations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    video_1 = tmp_path / "seg-1.mp4"
    video_2 = tmp_path / "seg-2.mp4"
    video_1.write_bytes(b"one")
    video_2.write_bytes(b"two")
    _write_render_evidence(plan, "seg-1", video_1)
    _write_render_evidence(plan, "seg-2", video_2)
    _write_context(
        plan,
        "subtitle-demo.narration.script",
        {
            "segments": [
                {"segment_id": "seg-1", "narration_text": "第一段旁白。"},
                {"segment_id": "seg-2", "narration_text": "第二段旁白。"},
            ]
        },
    )

    durations = iter(["2.5\n", "3.25\n"])

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=next(durations),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = build_subtitle_file(plan, output_name="demo.srt")

    assert result.success is True
    assert len(result.cues) == 2
    text = Path(result.output_path).read_text(encoding="utf-8-sig")
    assert "00:00:00,000 --> 00:00:02,500" in text
    assert "00:00:02,500 --> 00:00:05,750" in text
    assert "第一段旁白。" in text
    assert "第二段旁白。" in text


def test_build_subtitle_file_blocks_missing_segment_video(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    result = build_subtitle_file(plan)

    assert result.success is False
    assert result.error == "missing_segment_videos"
    assert result.missing_segments == ["seg-1", "seg-2"]


def test_subtitle_text_repairs_latin1_gbk_mojibake() -> None:
    assert _normalize_subtitle_text("ÏëÏóÒ»ÏÂ") == "想象一下"


def test_subtitle_chunks_split_long_chinese_narration() -> None:
    chunks = _subtitle_chunks(
        "第一句先建立直觉。第二句继续解释一个更长的过程，"
        "需要被拆开显示，避免整段文字压在画面底部。"
    )

    assert len(chunks) >= 3
    assert chunks[0] == "第一句先建立直觉。"
    assert all(len(chunk) <= 34 for chunk in chunks)


def test_mux_subtitle_track_writes_output(monkeypatch, tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    output_dir = Path(plan.runtime_layout.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    video = output_dir / "subtitle-demo-final.mp4"
    subtitle = output_dir / "subtitle-demo.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    def fake_run(command, **kwargs):
        Path(command[-1]).write_bytes(b"muxed")
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = mux_subtitle_track(plan)

    assert result.success is True
    assert Path(result.output_path).read_bytes() == b"muxed"
    assert result.command[:6] == ["ffmpeg", "-y", "-i", str(video), "-i", str(subtitle)]
    assert "-c:s" in result.command
    assert "mov_text" in result.command


def test_mux_subtitle_track_blocks_missing_subtitle(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    output_dir = Path(plan.runtime_layout.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "subtitle-demo-final.mp4").write_bytes(b"video")

    result = mux_subtitle_track(plan)

    assert result.success is False
    assert result.error == "subtitle_missing"


def test_burn_subtitle_track_writes_output(monkeypatch, tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    output_dir = Path(plan.runtime_layout.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    video = output_dir / "subtitle-demo-final.mp4"
    subtitle = output_dir / "subtitle-demo.srt"
    video.write_bytes(b"video")
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    def fake_run(command, **kwargs):
        Path(command[-1]).write_bytes(b"burned")
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = burn_subtitle_track(plan)

    assert result.success is True
    assert Path(result.output_path).read_bytes() == b"burned"
    assert result.command[:4] == ["ffmpeg", "-y", "-i", str(video)]
    assert "-vf" in result.command
    assert "subtitles=" in result.command[result.command.index("-vf") + 1]
    assert "libx264" in result.command


def test_burn_subtitle_track_blocks_missing_video(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    result = burn_subtitle_track(plan)

    assert result.success is False
    assert result.error == "video_missing"
