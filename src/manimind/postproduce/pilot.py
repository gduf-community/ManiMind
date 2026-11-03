"""A bounded, cue-timed production experiment, separate from pipeline-run.

This module prepares assets and evidence; it cannot approve its own render.
An independent reviewer must write a hash-bound report before final muxing.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import subprocess
import wave

from ..bootstrap import repo_root
from ..render.manim_renderer import extract_keyframes, render_manim_scene

ROOT = repo_root()
OUTPUT = ROOT / "outputs/velocity-pilot"
CONTEXT = ROOT / "runtime/projects/velocity-pilot"
SESSION = ROOT / "runtime/sessions/velocity-pilot-20261014"
SPEC = ROOT / "configs/velocity-pilot.json"
SCENE = ROOT / "examples/instantaneous_velocity.py"
CONFIG = ROOT / "configs/velocity-pilot-manimgl.yml"
FFMPEG = ROOT / "manimgl_env/bin/ffmpeg"
FFPROBE = ROOT / "manimgl_env/bin/ffprobe"
SAMPLE_RATE = 48000


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str | Path], timeout: int = 180) -> str:
    result = subprocess.run([str(v) for v in command], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    return result.stdout


def probe(path: Path) -> dict:
    return json.loads(run([FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", path]))


def cue_duration(audio_seconds: float, minimum: float, fps: int = 30) -> float:
    """Keep 0.3s visual lead-in and at least 0.65s breathing room on a frame grid."""
    if audio_seconds <= 0 or fps <= 0 or minimum < 0:
        raise ValueError("Invalid cue timing")
    return math.ceil(max(audio_seconds + 0.95, minimum) * fps) / fps


def check_spec_provenance(timeline: dict) -> None:
    if timeline.get("spec_sha256") != sha256(SPEC):
        raise ValueError("Narration is stale; run prepare again")


def render_input_hashes() -> dict[str, str]:
    return {f"{name}_sha256": sha256(path) for name, path in
            [("source", SCENE), ("timeline", OUTPUT / "timeline.json"), ("config", CONFIG), ("spec", SPEC)]}


async def prepare(provider: str) -> None:
    spec = read_json(SPEC)
    audio_dir = OUTPUT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    cues, cursor = [], 0.0
    for index, cue in enumerate(spec["cues"]):
        text = "".join(cue["subtitle_lines"])
        spoken = cue.get("spoken", text)
        name = f"{index + 1:02d}-{cue['id']}"
        source = audio_dir / f"{name}.{'mp3' if provider == 'edge' else 'aiff'}"
        cache_key = hashlib.sha256(json.dumps([provider, spoken, spec["voice"], spec["speech_rate"]]).encode()).hexdigest()
        stamp = audio_dir / f"{name}.json"
        if not (source.exists() and stamp.exists() and read_json(stamp).get("key") == cache_key):
            if provider == "edge":
                import edge_tts
                await edge_tts.Communicate(spoken, spec["voice"], rate=spec["speech_rate"]).save(str(source))
            else:
                run(["say", "-v", "Tingting", "-r", "240", "-o", source, spoken])
            write_json(stamp, {"key": cache_key, "provider": provider, "voice": spec["voice"] if provider == "edge" else "Tingting"})
        raw = audio_dir / f"{name}-raw.wav"
        run([FFMPEG, "-v", "error", "-y", "-i", source, "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", raw])
        with wave.open(str(raw), "rb") as wav:
            audio_seconds = wav.getnframes() / wav.getframerate()
        duration = cue_duration(audio_seconds, cue["min_duration"], spec["fps"])
        padded = audio_dir / f"{name}.wav"
        run([FFMPEG, "-v", "error", "-y", "-i", raw, "-af", "adelay=300,apad", "-t", f"{duration:.9f}", "-c:a", "pcm_s16le", padded])
        cues.append({**cue, "text": text, "start": round(cursor, 9), "duration": duration,
                     "audio_duration": audio_seconds, "speech_start": round(cursor + 0.3, 9),
                     "audio_path": str(padded.relative_to(ROOT))})
        cursor += duration
        print(f"{name}: speech={audio_seconds:.2f}s, cue={duration:.2f}s", flush=True)
    timeline = {"project_id": spec["project_id"], "fps": spec["fps"], "provider": provider,
                "voice": spec["voice"] if provider == "edge" else "Tingting", "duration": round(cursor, 9),
                "spec_sha256": sha256(SPEC), "cues": cues}
    write_json(OUTPUT / "timeline.json", timeline)
    # Concatenating PCM here prepares the narration asset; no final video exists yet.
    with wave.open(str(audio_dir / "narration.wav"), "wb") as output:
        output.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        for cue in cues:
            with wave.open(str(ROOT / cue["audio_path"]), "rb") as source:
                output.writeframes(source.readframes(source.getnframes()))
    write_json(CONTEXT / "production-context.json", {
        "scope": "long_term", "writer_role": "planner", "consumer_roles": ["manim_worker", "reviewer", "lead"],
        "lifecycle": "project", "invalidation_rule": "Any change to spec, mathematical model, or narration invalidates downstream review.",
        "spec": spec, "timeline": "outputs/velocity-pilot/timeline.json",
        "tasks": [{"owner": "manim_worker", "artifact": "examples/instantaneous_velocity.py"},
                  {"owner": "reviewer", "artifact": "runtime/projects/velocity-pilot/review.json"}],
        "html_segments": [], "manim_segments": ["InstantaneousVelocity"],
        "paper_summary": {"applicable": False, "reason": "Elementary illustrative model; derivation is recorded in facts."}})
    write_json(SESSION / "production-session.json", {
        "scope": "short_term", "writer_role": "coordinator", "consumer_roles": ["lead", "reviewer"],
        "lifecycle": "this production attempt", "invalidation_rule": "Discard or replace when source or render changes.",
        "phase": "narration_prepared", "duration": cursor})
    print(f"Prepared {cursor:.2f}s; provider={provider}", flush=True)


def render(quality: str) -> None:
    timeline = read_json(OUTPUT / "timeline.json")
    check_spec_provenance(timeline)
    before = render_input_hashes()
    result = render_manim_scene(segment_id=f"velocity-{quality}", scene_code=SCENE.read_text(encoding="utf-8"),
                                scene_class_name="InstantaneousVelocity", output_dir=OUTPUT,
                                quality=quality, config_file=CONFIG, timeout_seconds=1800)
    write_json(SESSION / f"render-{quality}.json", result.to_dict())
    if not result.success:
        raise RuntimeError(json.dumps(result.to_dict(), ensure_ascii=False))
    if before != render_input_hashes() or sha256(Path(result.code_path)) != before["source_sha256"]:
        raise ValueError("Input changed during rendering; rerender the new version")
    write_json(OUTPUT / "render.json", {**result.to_dict(), **before})
    print(result.video_path, flush=True)


def collect_hashes(video: Path) -> dict[str, str]:
    return {"source": sha256(SCENE), "spec": sha256(SPEC), "timeline": sha256(OUTPUT / "timeline.json"),
            "config": sha256(CONFIG), "video": sha256(video), "audio": sha256(OUTPUT / "audio/narration.wav")}


def inspect() -> None:
    from PIL import Image, ImageDraw, ImageStat

    rendered = read_json(OUTPUT / "render.json")
    video = Path(rendered["video_path"])
    for label, current in [("source", SCENE), ("timeline", OUTPUT / "timeline.json"), ("config", CONFIG)]:
        if rendered[f"{label}_sha256"] != sha256(current):
            raise ValueError(f"Stale render: {label} changed")
    timeline = read_json(OUTPUT / "timeline.json")
    check_spec_provenance(timeline)
    metadata = probe(video)
    stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    seconds = float(stream["duration"])
    if abs(seconds - timeline["duration"]) > 0.15:
        raise ValueError(f"Video timing drift: {seconds} vs {timeline['duration']}")
    # Include the stable algebra holds and full-brightness zoom baseline, not
    # just uniformly spaced transition samples.
    cue_samples = {"algebra": (0.18, 0.27, 0.40, 0.55, 0.66, 0.88), "zoom": (0.18, 0.35, 0.55, 0.88)}
    requests = [(cue["id"], round(cue["start"] + cue["duration"] * fraction, 3))
                for cue in timeline["cues"] for fraction in cue_samples.get(cue["id"], (0.18, 0.55, 0.88))]
    evidence = extract_keyframes(video_path=video, output_dir=OUTPUT / "frames",
                                 timestamps=[t for _, t in requests], ffmpeg_executable=FFMPEG)
    if not evidence.success or evidence.missing_timestamps or len(evidence.frame_paths) != len(requests):
        raise RuntimeError(f"Incomplete frame evidence: {evidence.to_dict()}")
    frame_index, sheets = [], []
    for batch in range(0, len(requests), 12):
        sheet = Image.new("RGB", (1600, 4 * 252), "#202226")
        draw = ImageDraw.Draw(sheet)
        for offset, ((cue_id, timestamp), path) in enumerate(zip(requests[batch:batch + 12], evidence.frame_paths[batch:batch + 12])):
            with Image.open(path) as frame:
                grey = frame.convert("L")
                contrast = ImageStat.Stat(grey).stddev[0]
                if contrast < 8:
                    raise ValueError(f"Blank or low-contrast frame: {path}")
                thumb = frame.copy()
                thumb.thumbnail((533, 225))
                x, y = (offset % 3) * 533, (offset // 3) * 252
                sheet.paste(thumb, (x, y + 24))
                draw.text((x + 6, y + 5), f"{cue_id} / {timestamp:.2f}s", fill="white")
                frame_index.append({"cue": cue_id, "time": timestamp, "path": path,
                                    "sha256": sha256(Path(path)), "contrast": round(contrast, 3)})
        path = OUTPUT / "frames" / f"contact-{batch // 12 + 1:02d}.jpg"
        sheet.save(path, quality=92)
        sheets.append(str(path))
    review_input = {"project_id": "velocity-pilot", "hashes": collect_hashes(video), "video_path": str(video),
                    "source_path": str(SCENE), "timeline_path": str(OUTPUT / "timeline.json"),
                    "duration": seconds, "resolution": [stream["width"], stream["height"]],
                    "frames": frame_index, "contact_sheets": sheets,
                    "required_checks": ["mathematics", "visual_layout", "narrative", "cue_timing", "actual_zoom"],
                    "review_instruction": "Independent reviewer must inspect image pixels and source, record limitations and blockers; never infer quality from contrast alone."}
    write_json(OUTPUT / "review-input.json", review_input)
    print(json.dumps({"duration": seconds, "resolution": review_input["resolution"], "contact_sheets": sheets}, ensure_ascii=False), flush=True)


def validate_review(review: dict, current_hashes: dict, frames: list[dict] | None = None, *, require_zoom: bool = True) -> None:
    if review.get("reviewer_role") != "reviewer" or not review.get("reviewer_id"):
        raise ValueError("Independent reviewer identity is required")
    if review.get("status") != "approved" or review.get("blockers") != []:
        raise ValueError("Review has not passed")
    if review.get("hashes") != current_hashes:
        raise ValueError("Review is stale: an input changed after approval")
    required = {"mathematics", "visual_layout", "narrative", "cue_timing", "actual_zoom"}
    if not require_zoom:
        required.remove("actual_zoom")
    checks = review.get("checks", {})
    if any(checks.get(name) != "pass" for name in required):
        raise ValueError("Review is missing required checks")
    inspected = review.get("inspected_frames")
    if not isinstance(inspected, list) or not inspected or not all(isinstance(p, str) for p in inspected):
        raise ValueError("Reviewer must inspect actual frames")
    if frames is not None:
        indexed = {frame["path"]: frame["sha256"] for frame in frames}
        for path in inspected:
            if path not in indexed or not Path(path).is_file() or sha256(Path(path)) != indexed[path]:
                raise ValueError("Reviewed frame is missing, changed, or belongs to a different render")


def assemble() -> None:
    evidence = read_json(OUTPUT / "review-input.json")
    video = Path(evidence["video_path"])
    review = read_json(CONTEXT / "review.json")
    validate_review(review, collect_hashes(video), evidence["frames"])
    timeline = read_json(OUTPUT / "timeline.json")
    check_spec_provenance(timeline)
    output = OUTPUT / "instantaneous-velocity.mp4"
    # Audio was padded per cue before rendering. No setpts, atempo, or global stretch.
    run([FFMPEG, "-v", "error", "-y", "-i", video, "-i", OUTPUT / "audio/narration.wav",
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-af", "loudnorm=I=-18:TP=-1.5:LRA=7", "-t", str(timeline["duration"]),
         "-movflags", "+faststart", output])
    metadata = probe(output)
    video_stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    audio_stream = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
    if abs(float(video_stream["duration"]) - float(audio_stream["duration"])) > 0.15:
        raise ValueError("Final A/V duration mismatch")
    run([FFMPEG, "-v", "error", "-i", output, "-f", "null", "-"], timeout=300)
    srt = []
    for index, cue in enumerate(timeline["cues"], 1):
        srt.append(f"{index}\n{srt_time(cue['start'])} --> {srt_time(cue['start'] + cue['duration'])}\n" + "\n".join(cue["subtitle_lines"]))
    (OUTPUT / "instantaneous-velocity.srt").write_text("\n\n".join(srt) + "\n", encoding="utf-8")
    write_json(OUTPUT / "delivery.json", {"video": str(output), "sha256": sha256(output), "duration": float(video_stream["duration"]),
                                         "resolution": [video_stream["width"], video_stream["height"]],
                                         "fps": video_stream["avg_frame_rate"], "voice": timeline["voice"],
                                         "review": str(CONTEXT / "review.json"), "review_sha256": sha256(CONTEXT / "review.json"),
                                         "source": str(SCENE), "timeline": str(OUTPUT / "timeline.json"),
                                         "limitations": ["Agent-directed pilot, not an unattended pipeline benchmark.",
                                                          "Synthetic narration; no human voice performance.",
                                                          "No student comprehension study has been performed."]})
    print(json.dumps(read_json(OUTPUT / "delivery.json"), ensure_ascii=False, indent=2), flush=True)


def srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    whole_seconds, milliseconds = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "render", "inspect", "assemble"])
    parser.add_argument("--provider", choices=["edge", "say"], default="edge")
    parser.add_argument("--quality", choices=["l", "m", "h"], default="m")
    args = parser.parse_args()
    if args.action == "prepare":
        asyncio.run(prepare(args.provider))
    elif args.action == "render":
        render(args.quality)
    elif args.action == "inspect":
        inspect()
    else:
        assemble()


if __name__ == "__main__":
    main()
