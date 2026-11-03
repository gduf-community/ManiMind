from pathlib import Path
import subprocess
import sys

from manimind.render.manim_renderer import (
    _default_keyframe_timestamps,
    _ffprobe_executable,
)
from manimind.render import ManimBackend, build_manim_render_command, write_scene_code


def test_write_scene_code_uses_predictable_output_path(tmp_path: Path) -> None:
    path = write_scene_code(
        "from manim import *\n",
        output_dir=tmp_path,
        segment_id="Segment 01",
    )

    assert path == tmp_path / "manim" / "code" / "segment-01.py"
    assert path.read_text(encoding="utf-8") == "from manim import *\n"


def test_build_manim_render_command_targets_project_output_dir(tmp_path: Path) -> None:
    code_path = tmp_path / "manim" / "code" / "seg-1.py"
    config_path = tmp_path / "manimgl.yml"
    config_path.write_text("tex:\n  template: basic_ctex\n", encoding="utf-8")
    command = build_manim_render_command(
        code_path=code_path,
        scene_class_name="DemoScene",
        output_dir=tmp_path,
        segment_id="seg-1",
        quality="l",
        renderer_executable="manimgl-test",
        config_file=config_path,
    )

    assert command[:5] == ["manimgl-test", str(code_path), "DemoScene", "-w", "-l"]
    assert str(code_path) in command
    assert "DemoScene" in command
    assert command[5:9] == [
        "--video_dir",
        str(tmp_path / "manim" / "media" / "manimgl"),
        "--file_name",
        "seg-1",
    ]
    assert command[-2:] == ["--config_file", str(config_path)]


def test_build_manimce_render_command_remains_available(tmp_path: Path) -> None:
    code_path = tmp_path / "manim" / "code" / "seg-1.py"
    command = build_manim_render_command(
        code_path=code_path,
        scene_class_name="DemoScene",
        output_dir=tmp_path,
        segment_id="seg-1",
        quality="h",
        backend=ManimBackend.MANIM_CE,
        python_executable=sys.executable,
    )

    assert command[:5] == [sys.executable, "-m", "manim", "render", "-qh"]
    assert command[-2:] == [
        "--media_dir",
        str(tmp_path / "manim" / "media" / "manimce"),
    ]


def test_default_keyframes_fall_back_when_duration_probe_fails(tmp_path: Path) -> None:
    assert _default_keyframe_timestamps(
        tmp_path / "missing.mp4",
        ffmpeg_executable=tmp_path / "missing-ffmpeg",
    ) == [1.0, 4.0, 8.0]


def test_default_keyframes_use_video_duration(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="8.0\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert _default_keyframe_timestamps(tmp_path / "scene.mp4") == [0.64, 4.0, 7.2]


def test_ffprobe_executable_tracks_custom_ffmpeg_path() -> None:
    assert _ffprobe_executable(Path("tools") / "ffmpeg.exe").endswith("ffprobe.exe")
