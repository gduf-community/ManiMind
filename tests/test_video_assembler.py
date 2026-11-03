import json
import subprocess
from pathlib import Path

from manimind.bootstrap import build_runtime_layout
from manimind.models import RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle
from manimind.postproduce import assemble_manim_video, collect_segment_video_paths
from manimind.workflow import build_project_plan


def _plan(root: Path):
    plan = build_project_plan(
        project_id="assemble-demo",
        title="Assemble Demo",
        source_bundle=SourceBundle(paper_path="paper.pdf"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="one",
                goal="Show one",
                narration="One.",
                modality=SegmentModality.MANIM,
            ),
            SegmentSpec(
                id="seg-2",
                title="two",
                goal="Show two",
                narration="Two.",
                modality=SegmentModality.MANIM,
            ),
        ],
    )
    layout = build_runtime_layout("assemble-demo", root=root)
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
        f"assemble-demo.manim.{segment_id}.render_evidence",
        {
            "segment_id": segment_id,
            "render": {"success": True, "video_path": str(video_path)},
            "frames": {"success": True, "frame_paths": []},
        },
    )


def test_collect_segment_video_paths_uses_manifest_order(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    video_1 = tmp_path / "b.mp4"
    video_2 = tmp_path / "a.mp4"
    video_1.write_bytes(b"one")
    video_2.write_bytes(b"two")
    _write_render_evidence(plan, "seg-1", video_1)
    _write_render_evidence(plan, "seg-2", video_2)

    paths, missing = collect_segment_video_paths(plan)

    assert paths == [str(video_1), str(video_2)]
    assert missing == []


def test_assemble_manim_video_writes_concat_list_and_output(
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

    def fake_run(command, **kwargs):
        Path(command[-1]).write_bytes(b"final")
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = assemble_manim_video(plan, output_name="preview.mp4")

    assert result.success is True
    assert Path(result.output_path).name == "preview.mp4"
    assert Path(result.output_path).read_bytes() == b"final"
    concat_text = Path(result.concat_list_path).read_text(encoding="utf-8")
    assert str(video_1.resolve()).replace("\\", "/") in concat_text
    assert str(video_2.resolve()).replace("\\", "/") in concat_text
    assert result.command[:7] == ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i"]


def test_assemble_manim_video_blocks_missing_segment_video(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    video_1 = tmp_path / "seg-1.mp4"
    video_1.write_bytes(b"one")
    _write_render_evidence(plan, "seg-1", video_1)

    result = assemble_manim_video(plan)

    assert result.success is False
    assert result.error == "missing_segment_videos"
    assert result.missing_segments == ["seg-2"]
