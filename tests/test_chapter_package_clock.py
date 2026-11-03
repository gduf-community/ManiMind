import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import wave

import pytest

from manimind.postproduce import chapter_package, chapter_package_clock as clock, pilot


def wav(path, data, rate=48000, channels=1):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(data)


def pin(path):
    return {"path": str(Path(path).resolve()), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def fake_native():
    def bound(row):
        if pin(row["path"]) != row:
            raise ValueError("Changed receipt")
        return Path(row["path"])
    return SimpleNamespace(_receipt=pin, _bound=bound,
                           common=SimpleNamespace(read_json=lambda p: json.loads(Path(p).read_text())),
                           _state=lambda *args: {"writer": "test", "consumers": ["test"],
                                                "lifecycle": "fixture", "invalidation": "fixture changed"})


def source_fixture(tmp_path):
    first, second = tmp_path / "a.wav", tmp_path / "b.wav"
    wav(first, b"\x11\x00" * 100)
    wav(second, b"\x22\x00" * 200)
    expected = bytearray(4800 * 2)
    expected[100 * 2:200 * 2] = clock._pcm(first)
    expected[1000 * 2:1200 * 2] = clock._pcm(second)
    wav(tmp_path / "voice-mix.wav", expected)
    alignment = {"units": [{"id": "a", "start": 100 / 48000}, {"id": "b", "start": 1000 / 48000}],
                 "inputs": [{"wav": str(first), "sha256": pin(first)["sha256"]},
                            {"wav": str(second), "sha256": pin(second)["sha256"]}]}
    records = {"delivery.json": {"bindings": {"candidate": str(tmp_path)}},
               "candidate.json": {"alignment": str(tmp_path / "alignment.json"),
                                  "voiced_delivery": str(tmp_path / "voiced.json")},
               "alignment.json": alignment, "voiced.json": {}}
    for name, data in records.items():
        (tmp_path / name).write_text(json.dumps(data))
    return {"project_id": "test", "duration": .1, "source_delivery": pin(tmp_path / "delivery.json")}, bytes(expected)


def test_private_native_namespace_and_explicit_pins():
    before = chapter_package._code()
    one, two = clock.native_namespace(), clock.native_namespace()
    assert one is not two
    assert one.CONTRACT == clock.CONTRACT != chapter_package.CONTRACT
    assert chapter_package._code() == before
    assert one._code() == before + [pin(clock.__file__), pin(__file__)]
    one.ROOT = Path("/not-the-real-root")
    assert two.ROOT == chapter_package.ROOT


def test_original_guard(monkeypatch):
    monkeypatch.setattr(clock, "NATIVE_SHA", "0" * 64)
    with pytest.raises(ValueError, match="Frozen"):
        clock.native_namespace()


def test_command_keeps_all_video_frames_and_uses_original_pcm():
    command = clock.encoding_command("ffmpeg", list("abcdefgh"), "mix.wav", "out.mp4")
    filters = command[command.index("-filter_complex") + 1]
    assert "concat=n=8:v=1:a=0,settb=1/30,setpts=N[v]" in filters
    assert "[v0][v1][v2][v3][v4][v5][v6][v7]" in filters
    assert command[command.index("-r") + 1] == "30"
    assert "8:a:0" in command and "-shortest" not in command
    assert all(term not in filters for term in ("atrim", "atempo", "scale", "crop"))
    with pytest.raises(ValueError):
        clock.encoding_command("ffmpeg", ["a"], "mix", "out")


@pytest.mark.parametrize("kind", ("valid", "raw_changed", "mix_changed", "overlap"))
def test_exact_original_unit_reconstruction(tmp_path, kind):
    source, expected = source_fixture(tmp_path)
    if kind == "raw_changed":
        wav(tmp_path / "a.wav", b"\x33\x00" * 100)
    elif kind == "mix_changed":
        wav(tmp_path / "voice-mix.wav", b"\x00\x00" * 4800)
    elif kind == "overlap":
        path = tmp_path / "alignment.json"
        data = json.loads(path.read_text())
        data["units"][1]["start"] = 0
        path.write_text(json.dumps(data))
    if kind == "valid":
        row, actual = clock._source_pcm(fake_native(), source)
        assert actual == expected and row["frames"] == 4800
        assert [item["frames"] for item in row["units"]] == [100, 200]
    else:
        with pytest.raises(ValueError):
            clock._source_pcm(fake_native(), source)


@pytest.mark.parametrize("rate,channels", ((44100, 1), (48000, 2)))
def test_wrong_pcm_format_rejected(tmp_path, rate, channels):
    path = tmp_path / "wrong.wav"
    wav(path, b"\x00" * 400, rate, channels)
    with pytest.raises(ValueError):
        clock._pcm(path)


def test_mix_all_samples_and_tamper_guard(tmp_path, monkeypatch):
    source, expected = source_fixture(tmp_path)
    native = fake_native()
    plan = {"sources": [source] * 8}
    mix = tmp_path / "chapter.wav"
    record = clock._write_mix(native, plan, mix)
    packet = {"frame_clock": clock.MODE, "pcm_audio": record, "duration": .8}
    assert clock._pcm(mix) == expected * 8
    clock._verify_pcm(native, plan, packet)
    damaged = bytearray(expected * 8)
    damaged[-1] = 1
    wav(mix, damaged)
    record["mix"] = pin(mix)
    with pytest.raises(ValueError, match="changed or moved"):
        clock._verify_pcm(native, plan, packet)


def test_real_eight_clip_clock_and_order(tmp_path):
    counts = [3, 4, 5, 6, 7, 8, 9, 10]
    colors = ["black", "red", "green", "blue", "yellow", "magenta", "cyan", "white"]
    videos = []
    for index, (count, color) in enumerate(zip(counts, colors, strict=True)):
        video = tmp_path / f"{index}.mp4"
        pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-f", "lavfi", "-i",
                   f"color=c={color}:s=1920x1080:r=30", "-f", "lavfi", "-i", "sine=sample_rate=48000",
                   "-frames:v", str(count), "-t", str(count / 30), "-c:v", "libx264", "-preset", "ultrafast",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "1", video], timeout=60)
        videos.append(video)
    mix = tmp_path / "raw.wav"
    wav(mix, b"\x00\x00" * (sum(counts) * 1600))
    target = tmp_path / "chapter.mp4"
    pilot.run(clock.encoding_command(pilot.FFMPEG, videos, mix, target), timeout=60)
    info = clock.native_namespace()._media(target, sum(counts) / 30)
    video = next(row for row in info["streams"] if row["codec_type"] == "video")
    assert int(video["nb_frames"]) == sum(counts) and video["r_frame_rate"] == "30/1"
    result = subprocess.run([str(pilot.FFMPEG), "-v", "error", "-i", str(target), "-map", "0:v:0",
                             "-vf", "scale=1:1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    pixels = [tuple(result.stdout[i:i + 3]) for i in range(0, len(result.stdout), 3)]
    expected = [(0, 0, 0), (255, 0, 0), (0, 128, 0), (0, 0, 255),
                (255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
    assert len(pixels) == sum(counts)
    offset = 0
    for count, rgb in zip(counts, expected, strict=True):
        assert all(max(abs(a - b) for a, b in zip(pixel, rgb, strict=True)) < 25 for pixel in pixels[offset:offset + count])
        offset += count
