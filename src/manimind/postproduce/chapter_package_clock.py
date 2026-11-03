"""Versioned 30-fps/original-PCM adapter over the unchanged chapter publisher.

Each call owns a fresh private native namespace. Its contract and implementation
pins explicitly include this adapter; no canonical module or old plan is edited.
All original source, identity, review, decode, pixel and release gates remain.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import wave


ROOT = Path(__file__).resolve().parents[3]
NATIVE = Path(__file__).with_name("chapter_package.py")
NATIVE_SHA = "67a5d1d489bdf8c91b98692b2bca2d5db1f8e75046d432537ca557625f15a784"
CONTRACT = "chapter-package-frame-clock-v2"
MODE = "ordinal-30fps-original-pcm-v1"
RATE = 48000


def _guard():
    if hashlib.sha256(NATIVE.read_bytes()).hexdigest() != NATIVE_SHA:
        raise ValueError("Frozen original publisher changed")


def _pcm(path):
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) != (1, 2, RATE, "NONE"):
            raise ValueError("Require original mono PCM16 48-kHz audio")
        data = stream.readframes(stream.getnframes())
        if len(data) != stream.getnframes() * 2:
            raise ValueError("Incomplete original PCM")
        return data


def _source_pcm(native, source):
    delivery = native.common.read_json(source["source_delivery"]["path"])
    candidate = native.common.read_json(Path(delivery["bindings"]["candidate"]) / "candidate.json")
    alignment_path = Path(candidate["alignment"])
    alignment = native.common.read_json(alignment_path)
    voiced = Path(candidate["voiced_delivery"])
    mix = voiced.parent / "voice-mix.wav"
    count = round(source["duration"] * RATE)
    expected, units, previous = bytearray(count * 2), [], 0
    for unit, item in zip(alignment["units"], alignment["inputs"], strict=True):
        pin = native._receipt(item["wav"])
        if pin["sha256"] != item["sha256"]:
            raise ValueError("Original unit WAV changed")
        data = _pcm(pin["path"])
        start = round(unit["start"] * RATE)
        end = start + len(data) // 2
        if start < previous or start < 0 or end > count:
            raise ValueError("Cannot overlap, truncate or move an original unit")
        expected[start * 2:end * 2] = data
        units.append({"id": unit["id"], "wav": pin, "start_sample": start, "frames": len(data) // 2})
        previous = end
    actual = _pcm(mix)
    if actual != expected:
        raise ValueError("Native voice mix differs from complete approved original units")
    return {"project_id": source["project_id"], "frames": count,
            "alignment": native._receipt(alignment_path), "voiced_delivery": native._receipt(voiced),
            "native_mix": native._receipt(mix), "pcm_sha256": hashlib.sha256(actual).hexdigest(),
            "units": units}, actual


def _write_mix(native, plan, target):
    rows = []
    with target.open("xb") as raw, wave.open(raw, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        for source in plan["sources"]:
            row, data = _source_pcm(native, source)
            stream.writeframes(data)
            rows.append(row)
    total = sum(row["frames"] for row in rows)
    if total != round(sum(source["duration"] for source in plan["sources"]) * RATE):
        raise ValueError("Original PCM/frame clocks disagree")
    return {"mode": MODE, "mix": native._receipt(target), "frames": total,
            "sample_rate": RATE, "channels": 1, "sample_width": 2, "sources": rows,
            "audio_trimmed": False, "speed_changed": False, "original_samples_preserved": True,
            **native._state("Original-PCM chapter assembler", ["fresh media reviewer", "publisher"],
                            "This exact original-sample reconstruction")}


def _verify_pcm(native, plan, packet):
    row = packet.get("pcm_audio", {})
    if (packet.get("frame_clock") != MODE or row.get("mode") != MODE
            or row.get("audio_trimmed") is not False or row.get("speed_changed") is not False
            or row.get("original_samples_preserved") is not True
            or (row.get("sample_rate"), row.get("channels"), row.get("sample_width")) != (RATE, 1, 2)):
        raise ValueError("Require an honest unchanged-original-PCM clock record")
    mix = native._bound(row["mix"])
    with wave.open(str(mix), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) != (1, 2, RATE, "NONE"):
            raise ValueError("Chapter PCM format changed")
        if stream.getnframes() != row["frames"] or row["frames"] != round(packet["duration"] * RATE):
            raise ValueError("Chapter PCM duration changed")
        for source, recorded in zip(plan["sources"], row["sources"], strict=True):
            current, data = _source_pcm(native, source)
            if recorded != current or stream.readframes(current["frames"]) != data:
                raise ValueError("A complete original PCM segment changed or moved")
        if stream.readframes(1):
            raise ValueError("Unaccounted chapter audio")


def encoding_command(ffmpeg, videos, mix, output):
    if len(videos) != 8:
        raise ValueError("Require the eight complete source videos")
    command, filters, labels = [ffmpeg, "-v", "error", "-n"], [], []
    for index, video in enumerate(videos):
        command += ["-i", video]
        filters.append(f"[{index}:v:0]setpts=PTS-STARTPTS[v{index}]")
        labels.append(f"[v{index}]")
    command += ["-i", mix]
    # Original sources are verified CFR30. Reindex all retained frames, without
    # letting decoded AAC packet padding introduce inter-lesson video gaps.
    filters.append("".join(labels) + "concat=n=8:v=1:a=0,settb=1/30,setpts=N[v]")
    return command + ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "8:a:0",
                      "-map_metadata", "-1", "-map_chapters", "-1", "-c:v", "libx264",
                      "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30",
                      "-fps_mode", "cfr", "-c:a", "aac", "-ar", "48000", "-ac", "1",
                      "-b:a", "192k", "-sn", "-dn", "-movflags", "+faststart", output]


def _assemble(native, plan_path, review_path):
    plan = native.common.read_json(plan_path)
    native._actor(plan)
    current = native.bindings(plan_path)
    review = native._receipt(review_path)
    native._review(plan, review_path, "chapter_assembly", current)
    candidate = Path(plan["output"]) / "candidate"
    candidate.mkdir(exist_ok=False)
    native._write(candidate / "pending.json", {"status": "pending_not_released", "bindings": current,
                  "review": review, **native._state("Frame-clock assembler", ["operator"], "One encoding attempt")})
    segments, duration = native._segments(plan)
    videos = []
    for source, verified in zip(plan["sources"], plan["verified"], strict=True):
        native.check_video(native.pilot.probe(verified["video"]["path"]), source["duration"])
        videos.append(verified["video"]["path"])
    pcm = _write_mix(native, plan, candidate / "chapter-voice-mix.wav")
    video = candidate / "chapter-candidate.mp4"
    command = encoding_command(native.pilot.FFMPEG, videos, pcm["mix"]["path"], video)
    native.pilot.run(command, timeout=1800)
    info = native._media(video, duration)
    frames = Path(plan["session"]) / "chapter-boundaries"
    frames.mkdir(exist_ok=False)
    boundaries = []
    for index, segment in enumerate(segments[1:], 1):
        boundary = {}
        for label, time in (("before", segment["interval"][0] - 1 / 30), ("after", segment["interval"][0])):
            target = frames / f"{index:02d}-{label}.png"
            native.pilot.run([native.pilot.FFMPEG, "-v", "error", "-n", "-ss", str(time), "-i", video,
                              "-map", "0:v:0", "-frames:v", "1", target], timeout=60)
            boundary[label] = {**native._receipt(target), "time": time, "video_sha256": native.common.sha(video)}
        boundaries.append(boundary)
    if native.bindings(plan_path) != current or native._receipt(review_path) != review:
        raise ValueError("Chapter sources or assembly approval changed")
    native._review(plan, review_path, "chapter_assembly", current)
    packet = {"contract": CONTRACT, "status": "candidate_not_released", "stage": "chapter_media",
              "source_bindings": current, "assembly_review": review, "video": native._receipt(video),
              "duration": duration, "probe": info, "segments": segments, "boundaries": boundaries,
              "command": [str(item) for item in command], "full_decode_passed": True,
              "frame_clock": MODE, "pcm_audio": pcm, "listening_reviewed": False, "student_tested": False,
              **native._state("Frame-clock chapter assembler", ["fresh media reviewer", "publisher"], "This exact candidate")}
    _verify_pcm(native, plan, packet)
    native._write(candidate / "candidate.json", packet)
    native._write(Path(plan["session"]) / "chapter-media-input.json", {
        "stage": "chapter_media", "bindings": packet,
        "report_target": str(Path(plan["session"]) / "chapter-media-review.json"),
        "required_checks": ["full_lesson", "captions", "av_continuity", "seven seams", "original PCM"],
        **native._state("Frame-clock chapter assembler", ["fresh media reviewer"], "This candidate only")})
    return packet


def native_namespace():
    _guard()
    spec = importlib.util.spec_from_file_location("manimind.postproduce._private_chapter_clock_native", NATIVE)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    original_code, original_prepare, original_candidate = native._code, native.prepare, native._candidate
    native.CONTRACT = CONTRACT
    native._code = lambda: original_code() + [native._receipt(__file__), native._receipt(ROOT / "tests/test_chapter_package_clock.py")]

    def prepare_checked(request):
        if native.common.read_json(request).get("frame_clock") != MODE:
            raise ValueError("Explicit new frame-clock request required")
        return original_prepare(request)

    def candidate_checked(plan_path):
        packet = original_candidate(plan_path)
        _verify_pcm(native, native.common.read_json(plan_path), packet)
        return packet

    native.prepare = prepare_checked
    native.assemble = lambda plan, review: _assemble(native, plan, review)
    native._candidate = candidate_checked
    return native


def prepare(request):
    return native_namespace().prepare(request)


def bindings(plan):
    return native_namespace().bindings(plan)


def assemble(plan, review):
    return native_namespace().assemble(plan, review)


def release(plan, review, desktop):
    return native_namespace().release(plan, review, desktop)


def main(argv=None):
    return native_namespace().main(argv)


if __name__ == "__main__":
    main()
