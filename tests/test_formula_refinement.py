import json
from pathlib import Path

import pytest
import sympy as sp

from manimind.postproduce import formula_refinement as subject


@pytest.fixture
def attempt(tmp_path):
    output = tmp_path / "attempt"
    output.mkdir()
    source = tmp_path / "scene.py"
    source.write_text("fixture scene")
    patch = output / "patch.mp4"
    patch.write_bytes(b"fixture encoded media, not playable")
    frame = output / "frame.jpg"
    frame.write_bytes(b"fixture image hash, not pixels")
    subject.common.write_json(output / "plan.json", {"base_video_sha256": "base"})
    rendered = {"video": str(patch), "video_sha256": subject.common.sha(patch),
                "input_hashes": {str(source): subject.common.sha(source)},
                "plan_sha256": subject.common.sha(output / "plan.json")}
    subject.common.write_json(output / "render.json", rendered)
    subject.common.write_json(output / "review-input.json", {"render": rendered,
        "frames": [{"path": str(frame), "sha256": subject.common.sha(frame)}], "sheets": []})
    subject.common.write_json(output / "motion-samples.json", {"samples": []})
    subject.common.write_json(output / "visual-events.json", {"events": []})
    return output, source, patch, frame


def test_bindings_pin_plan_source_pixels_and_actual_motion(attempt):
    output, _, patch, _ = attempt
    result = subject.bindings(output)
    assert result["patch_video_sha256"] == subject.common.sha(patch)
    assert result["motion_sha256"] == subject.common.sha(output / "motion-samples.json")
    assert len(result) == 6


@pytest.mark.parametrize("changed", ["plan", "source", "patch", "frame", "evidence_render"])
def test_stale_inputs_and_pixels_are_not_publishable(attempt, changed):
    output, source, patch, frame = attempt
    paths = {"plan": output / "plan.json", "source": source, "patch": patch, "frame": frame}
    if changed == "evidence_render":
        value = subject.common.read_json(output / "review-input.json")
        value["render"] = {}
        (output / "review-input.json").write_text(json.dumps(value))
    else:
        with paths[changed].open("ab") as stream:
            stream.write(b" ")
    with pytest.raises(ValueError, match="changed|different"):
        subject.bindings(output)


def test_no_composition_before_current_independent_review(attempt, tmp_path):
    output, _, _, _ = attempt
    report = tmp_path / "review.json"
    subject.common.write_json(report, {"status": "pass"})
    with pytest.raises(ValueError, match="independent formula-motion review"):
        subject.release(output, report)
    assert not (output / "playback").exists()


def test_outside_frame_parser_compares_pixel_digests_not_container_comments(monkeypatch):
    calls = []

    def run(command, timeout):
        calls.append(command)
        return "#format: frame checksums\n0,0,0,1,8,abc\n0,1,1,1,8,def\n"

    monkeypatch.setattr(subject.pilot, "run", run)
    assert subject.outside_frames(Path("video.mp4"), 1140, 1740) == ["abc", "def"]
    assert calls[0][calls[0].index("-map") + 1] == "0:v:0"
    assert "lt(n,1140)+gte(n,1740)" in calls[0][calls[0].index("-vf") + 1]


def test_native_and_distribution_exports_preserve_30fps_and_original_audio_packets():
    master = subject.composition_command("base.mp4", "patch.mp4", "master.mp4", 1140, 1740, 3420, 114)
    player = subject.distribution_command("master.mp4", "full.mp4")
    for command in (master, player):
        assert command[command.index("-r") + 1] == "30"
        assert command[command.index("-c:a") + 1] == "copy"
        assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert player[player.index("-profile:v") + 1] == "high"
    assert "end_frame=1140" in master[master.index("-filter_complex") + 1]
    assert "start_frame=1740:end_frame=3420" in master[master.index("-filter_complex") + 1]


def test_displayed_algebra_and_positive_root_are_equivalent():
    h, g, T = sp.symbols("h g T", positive=True)
    grounded = -h + g * T**2 / 2
    moved = g * T**2 / 2 - h
    doubled = g * T**2 - 2 * h
    isolated = T**2 - 2 * h / g
    assert sp.simplify(grounded - moved) == 0
    assert sp.simplify(doubled - 2 * moved) == 0
    assert sp.simplify(isolated - doubled / g) == 0
    assert sp.simplify(isolated.subs(T, sp.sqrt(2 * h / g))) == 0
    assert sp.sqrt(2 * h / g).is_positive
