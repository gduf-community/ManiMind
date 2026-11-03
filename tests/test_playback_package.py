from pathlib import Path

import pytest

from manimind.postproduce import pilot, playback_package


@pytest.fixture
def publication(tmp_path, monkeypatch):
    source = tmp_path / "original"
    source.mkdir()
    video = source / "lesson.mp4"
    video.write_bytes(b"unchanged published media")
    (source / "lesson.srt").write_text("Optional transcript", encoding="utf-8")
    review = source / "review.json"
    hashes = {"video": "reviewed-render-hash"}
    pilot.write_json(review, {
        "reviewer_role": "reviewer", "reviewer_id": "independent", "status": "approved",
        "blockers": [], "hashes": hashes, "inspected_frames": ["frame.png"],
        "checks": {key: "pass" for key in ["mathematics", "visual_layout", "narrative", "cue_timing"]},
    })
    delivery = source / "delivery.json"
    pilot.write_json(delivery, {
        "video": str(video), "sha256": pilot.sha256(video), "duration": 2,
        "review": str(review), "review_sha256": pilot.sha256(review), "hashes": hashes,
        "full_decode_passed": True, "limitations": ["No listening test"],
    })
    monkeypatch.setattr(pilot, "probe", lambda path: {"streams": [
        {"codec_type": "video"}, {"codec_type": "audio"}]})
    return delivery


def test_export_is_byte_identical_and_copies_no_sidecars(publication, tmp_path):
    output = tmp_path / "playback"
    manifest = playback_package.package_playback({"sol61": publication}, output)
    assert {p.name for p in output.iterdir()} == {"sol61.mp4", "manifest.json"}
    assert pilot.sha256(output / "sol61.mp4") == pilot.read_json(publication)["sha256"]
    assert (publication.parent / "lesson.srt").exists()
    assert manifest["videos"][0]["limitations"] == ["No listening test"]


@pytest.mark.parametrize("changed", ["video", "review", "full_decode_passed", "hashes"])
def test_rejects_changed_media_or_publication_evidence(publication, tmp_path, changed):
    data = pilot.read_json(publication)
    if changed in {"video", "review"}:
        Path(data[changed]).write_bytes(b"changed")
    elif changed == "full_decode_passed":
        data[changed] = False
    else:
        data[changed] = {"video": "different"}
    pilot.write_json(publication, data)
    with pytest.raises(ValueError):
        playback_package.package_playback({"sol61": publication}, tmp_path / "playback")
    assert not (tmp_path / "playback").exists()


def test_rejects_soft_subtitle_track(publication, tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, "probe", lambda path: {"streams": [
        {"codec_type": t} for t in ["video", "audio", "subtitle"]]})
    with pytest.raises(ValueError, match="one video and one audio"):
        playback_package.package_playback({"sol61": publication}, tmp_path / "playback")


def test_does_not_replace_existing_directory(publication, tmp_path):
    output = tmp_path / "playback"
    output.mkdir()
    sidecar = output / "sol61.srt"
    sidecar.write_text("Existing user file", encoding="utf-8")
    with pytest.raises(FileExistsError):
        playback_package.package_playback({"sol61": publication}, output)
    assert sidecar.read_text(encoding="utf-8") == "Existing user file"


def test_name_cannot_escape_playback_directory(publication, tmp_path):
    with pytest.raises(ValueError, match="simple file stems"):
        playback_package.package_playback({"../escape": publication}, tmp_path / "playback")
