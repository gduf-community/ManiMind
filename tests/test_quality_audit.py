import json
from pathlib import Path

from manimind.bootstrap import build_runtime_layout
from manimind.models import RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle
from manimind.review import run_quality_audit
from manimind.workflow import build_project_plan


def _plan(root: Path):
    plan = build_project_plan(
        project_id="audit-demo",
        title="Audit Demo",
        source_bundle=SourceBundle(paper_path="paper.pdf"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="main",
                goal="Explain function",
                narration="Show the function.",
                modality=SegmentModality.MANIM,
                formulas=["function f(x)=x"],
            )
        ],
    )
    layout = build_runtime_layout("audit-demo", root=root)
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


def _write_ppm(path: Path, width: int, height: int, pixels: bytes) -> None:
    path.write_bytes(f"P6\n{width} {height}\n255\n".encode("ascii") + pixels)


def _checkerboard_pixels(width: int, height: int, block: int = 16) -> bytes:
    data = bytearray()
    for y in range(height):
        for x in range(width):
            bright = ((x // block) + (y // block)) % 2 == 0
            value = 235 if bright else 18
            data.extend([value, value, value])
    return bytes(data)


def _shift_pixels(pixels: bytes, offset: int = 3) -> bytes:
    stride = offset * 3
    return pixels[stride:] + pixels[:stride]


def _good_scene_code() -> str:
    return """
from manim import *
class Main(Scene):
    def construct(self):
        axes = Axes()
        graph = axes.plot(lambda x: x, color=BLUE)
        dot = Dot(color=YELLOW)
        label = MathTex(r"f(x)=x", tex_to_color_map={r"x": BLUE})
        tracker = ValueTracker(0)
        self.play(Create(axes), Create(graph))
        self.play(FadeIn(dot), Write(label))
        self.play(tracker.animate.set_value(1), run_time=1)
        self.wait(1)
"""


def test_quality_audit_passes_complete_runtime_evidence(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    video = tmp_path / "scene.mp4"
    code_path = tmp_path / "scene.py"
    frame_1 = tmp_path / "frame-1.ppm"
    frame_2 = tmp_path / "frame-2.ppm"
    pixels = _checkerboard_pixels(640, 360)
    video.write_bytes(b"video")
    code_path.write_text(_good_scene_code(), encoding="utf-8")
    _write_ppm(frame_1, 640, 360, pixels)
    _write_ppm(frame_2, 640, 360, _shift_pixels(pixels))

    _write_context(
        plan,
        "audit-demo.manim.seg-1.approved",
        {
            "segment_id": "seg-1",
            "scene_code": _good_scene_code(),
            "scene_class_name": "Main",
        },
    )
    _write_context(
        plan,
        "audit-demo.manim.seg-1.render_evidence",
        {
            "segment_id": "seg-1",
            "render": {"success": True, "video_path": str(video), "code_path": str(code_path)},
            "frames": {"success": True, "frame_paths": [str(frame_1), str(frame_2)]},
        },
    )

    report = run_quality_audit(plan)

    assert report.status == "pass"
    assert report.checked_segments == ["seg-1"]
    assert report.stale_evidence_segments == []
    assert report.output_path
    assert report.summary_path
    assert Path(report.output_path).exists()
    summary = Path(report.summary_path)
    assert summary.exists()
    summary_text = summary.read_text(encoding="utf-8")
    assert "# Quality Summary: audit-demo" in summary_text
    assert "Status: pass" in summary_text
    assert "seg-1 - main" in summary_text
    assert str(frame_1.resolve()).replace("\\", "/") in summary_text


def test_quality_audit_blocks_stale_render_evidence(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    video = tmp_path / "scene.mp4"
    code_path = tmp_path / "scene.py"
    frame_1 = tmp_path / "frame-1.ppm"
    frame_2 = tmp_path / "frame-2.ppm"
    pixels = _checkerboard_pixels(640, 360)
    video.write_bytes(b"video")
    code_path.write_text("from manim import *\nclass Old(Scene): pass\n", encoding="utf-8")
    _write_ppm(frame_1, 640, 360, pixels)
    _write_ppm(frame_2, 640, 360, _shift_pixels(pixels))

    _write_context(
        plan,
        "audit-demo.manim.seg-1.approved",
        {
            "segment_id": "seg-1",
            "scene_code": _good_scene_code(),
            "scene_class_name": "Main",
        },
    )
    _write_context(
        plan,
        "audit-demo.manim.seg-1.render_evidence",
        {
            "segment_id": "seg-1",
            "render": {"success": True, "video_path": str(video), "code_path": str(code_path)},
            "frames": {"success": True, "frame_paths": [str(frame_1), str(frame_2)]},
        },
    )

    report = run_quality_audit(plan, write_report=False)

    assert report.status == "block"
    assert report.stale_evidence_segments == ["seg-1"]
    assert any(
        "rendered code is stale" in issue
        for finding in report.render_evidence_findings
        for issue in finding["issues"]
    )


def test_quality_audit_blocks_missing_render_evidence(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    _write_context(
        plan,
        "audit-demo.manim.seg-1.approved",
        {
            "segment_id": "seg-1",
            "scene_code": _good_scene_code(),
            "scene_class_name": "Main",
        },
    )

    report = run_quality_audit(plan, write_report=False)

    assert report.status == "block"
    assert report.missing_evidence_segments == ["seg-1"]
    assert report.missing_manim_segments == []
    assert report.output_path is None


def test_quality_audit_blocks_missing_manim_output(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    report = run_quality_audit(plan, write_report=False)

    assert report.status == "block"
    assert report.missing_manim_segments == ["seg-1"]
    assert report.missing_evidence_segments == ["seg-1"]
