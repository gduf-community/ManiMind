from pathlib import Path

from manimind.review import (
    analyze_frame_quality,
    analyze_motion_quality,
    assess_render_evidence,
)
from manimind.review.frame_quality import _parse_ppm


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


def test_assess_render_evidence_passes_existing_video_and_frames(tmp_path: Path) -> None:
    video = tmp_path / "scene.mp4"
    frame = tmp_path / "frame-1.ppm"
    frame_2 = tmp_path / "frame-2.ppm"
    pixels = _checkerboard_pixels(640, 360)
    video.write_bytes(b"video")
    _write_ppm(frame, 640, 360, pixels)
    _write_ppm(frame_2, 640, 360, _shift_pixels(pixels))

    finding = assess_render_evidence({
        "segment_id": "seg-1",
        "render": {"success": True, "video_path": str(video)},
        "frames": {"success": True, "frame_paths": [str(frame), str(frame_2)]},
    })

    assert finding.status == "pass"
    assert finding.issues == []
    assert finding.frame_quality[0]["width"] == 640
    assert finding.motion_quality
    assert finding.motion_quality["status"] == "pass"


def test_assess_render_evidence_blocks_missing_assets(tmp_path: Path) -> None:
    finding = assess_render_evidence({
        "segment_id": "seg-1",
        "render": {"success": False, "error": "manim_render_failed"},
        "frames": {"success": False, "frame_paths": []},
    })

    assert finding.status == "block"
    assert "manim_render_failed" in finding.issues
    assert any("video_path" in issue for issue in finding.issues)
    assert any("frame" in issue for issue in finding.issues)


def test_analyze_frame_quality_blocks_near_black_frame(tmp_path: Path) -> None:
    frame = tmp_path / "black.ppm"
    _write_ppm(frame, 640, 360, bytes([0, 0, 0]) * 640 * 360)

    metrics = analyze_frame_quality(frame)

    assert metrics.status == "block"
    assert any("near-black" in issue for issue in metrics.issues)
    assert any("contrast" in issue for issue in metrics.issues)


def test_parse_ppm_preserves_whitespace_valued_first_pixel_byte() -> None:
    rgb = bytes([12, 17, 24])

    width, height, parsed = _parse_ppm(b"P6\n1 1\n255\n" + rgb)

    assert (width, height) == (1, 1)
    assert parsed == rgb


def test_analyze_motion_quality_blocks_static_frames(tmp_path: Path) -> None:
    frame_1 = tmp_path / "static-1.ppm"
    frame_2 = tmp_path / "static-2.ppm"
    pixels = _checkerboard_pixels(640, 360)
    _write_ppm(frame_1, 640, 360, pixels)
    _write_ppm(frame_2, 640, 360, pixels)

    metrics = analyze_motion_quality([frame_1, frame_2])

    assert metrics.status == "block"
    assert metrics.mean_luma_delta == 0
    assert any("luma change" in issue for issue in metrics.issues)


def test_assess_render_evidence_blocks_static_motion(tmp_path: Path) -> None:
    video = tmp_path / "scene.mp4"
    frame_1 = tmp_path / "frame-1.ppm"
    frame_2 = tmp_path / "frame-2.ppm"
    pixels = _checkerboard_pixels(640, 360)
    video.write_bytes(b"video")
    _write_ppm(frame_1, 640, 360, pixels)
    _write_ppm(frame_2, 640, 360, pixels)

    finding = assess_render_evidence({
        "segment_id": "seg-1",
        "render": {"success": True, "video_path": str(video)},
        "frames": {"success": True, "frame_paths": [str(frame_1), str(frame_2)]},
    })

    assert finding.status == "block"
    assert finding.motion_quality
    assert finding.motion_quality["status"] == "block"
    assert any("motion continuity" in issue for issue in finding.issues)


def test_assess_render_evidence_blocks_low_quality_frame(tmp_path: Path) -> None:
    video = tmp_path / "scene.mp4"
    frame = tmp_path / "blank.ppm"
    video.write_bytes(b"video")
    _write_ppm(frame, 640, 360, bytes([1, 1, 1]) * 640 * 360)

    finding = assess_render_evidence({
        "segment_id": "seg-1",
        "render": {"success": True, "video_path": str(video)},
        "frames": {"success": True, "frame_paths": [str(frame)]},
    })

    assert finding.status == "block"
    assert any("near-black" in issue for issue in finding.issues)
    assert finding.frame_quality[0]["status"] == "block"
