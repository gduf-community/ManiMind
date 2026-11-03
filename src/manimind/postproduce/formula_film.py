"""Render and review a full visual refinement while preserving approved audio."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from . import formula_refinement as partial, pilot, preset_audition as common
from manimind.render.manim_renderer import (
    _render_environment, build_manim_render_command, extract_keyframes, write_scene_code,
)


def timeline_for(plan):
    timeline = common.read_json(pilot.ROOT / plan["timeline"])
    for cue in timeline["cues"]:
        if cue["id"] == "landing_condition":
            cue["anchors"].extend({"id": name, "meaning": meaning} for name, meaning in (
                ("term_relocated", "The whole gravity term has cleared and crossed the equals sign"),
                ("height_doubled", "Both sides have been multiplied by two"),
                ("square_time_isolated", "Both sides have been divided by positive g"),
            ))
    return timeline


def check_timing(plan, events):
    measured = {row["id"]: row["time"] for row in events["events"]}
    original = common.read_json(pilot.ROOT / plan["original_events"])
    for row in original["events"]:
        if abs(measured[row["id"]] - row["time"]) > 1 / 30 + 1e-5:
            raise ValueError(f"Original visual event drifted: {row['id']}")
    alignment = common.read_json(pilot.ROOT / plan["alignment"])
    if abs(events["duration"] - alignment["duration"]) > 1 / 30:
        raise ValueError("Visual duration no longer matches the selected narration")
    checks = []
    for row in alignment["segments"]:
        anchor = measured[row["anchor"]]
        passed = row["start"] + 1e-5 >= anchor if row["relation"] == "after" else row["end"] <= anchor + 1e-5
        checks.append({"id": row["id"], "anchor": row["anchor"], "time": anchor,
                       "start": row["start"], "end": row["end"], "passed": passed})
    if not all(row["passed"] for row in checks):
        raise ValueError(f"Narration crossed a visual semantic boundary: {checks}")
    return checks


def render(plan_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    plan = common.read_json(plan_path)
    partial.verify_base(plan)
    watched = [pilot.ROOT / name for name in plan["sources"]]
    before = {str(path): common.sha(path) for path in watched}
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(plan_path, output / "plan.json")
    for path in watched:
        target = output / "source" / path.relative_to(pilot.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    common.write_json(output / "timeline.json", timeline_for(plan))
    config = output / "render.yml"
    with config.open("x", encoding="utf-8") as stream:
        stream.write('camera:\n  background_color: "#101416"\n  fps: 30\ntex:\n  template: "basic_ctex"\n')
    code = write_scene_code((pilot.ROOT / plan["scene"]).read_text(), output_dir=output, segment_id="formula-film")
    command = build_manim_render_command(code_path=code, scene_class_name=plan["scene_class"],
        output_dir=output, segment_id="formula-film", quality="h", config_file=config)
    env = _render_environment()
    env.update(PYTHONPATH=os.pathsep.join(str(pilot.ROOT / folder) for folder in ("src", "examples")),
               MANIMIND_FREEFORM_OUTPUT=str(output), MANIMIND_DISABLE_DOTENV="1", PYTHONDONTWRITEBYTECODE="1")
    print(json.dumps({"status": "rendering", "output": str(output)}), flush=True)
    with (output / "render.log").open("x") as log:
        result = subprocess.run(command, env=env, cwd=pilot.ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
    if result.returncode:
        raise RuntimeError(f"Full visual render failed; retain {output / 'render.log'}")
    if before != {str(path): common.sha(path) for path in watched}:
        raise ValueError("Scene implementation changed during render")
    videos = list((output / "manim/media/manimgl").glob("**/formula-film.mp4"))
    if len(videos) != 1:
        raise ValueError("Expected exactly one full visual master")
    video = videos[0]
    info = pilot.probe(video)
    check_video(info, plan["duration"], silent=True)
    checks = check_timing(plan, common.read_json(output / "visual-events.json"))
    common.write_json(output / "render.json", {"video": str(video), "video_sha256": common.sha(video),
        "input_hashes": before, "plan_sha256": common.sha(output / "plan.json"), "command": command,
        "narration_boundary_checks": checks, "writer": "Full formula renderer",
        "consumers": ["independent reviewer", "release gate"], "lifecycle": "This render attempt",
        "invalidation": "Any scene, plan, media, events, trajectory or evidence change"})
    inspect(output)
    return video


def check_video(info, duration, *, silent=False):
    kinds = sorted(row["codec_type"] for row in info["streams"])
    expected = ["video"] if silent else ["audio", "video"]
    row = next(row for row in info["streams"] if row["codec_type"] == "video")
    if (kinds != expected or [row["width"], row["height"]] != [1920, 1080]
            or row["avg_frame_rate"] != "30/1" or int(row["nb_frames"]) != round(duration * 30)
            or row["codec_name"] != "h264" or row["pix_fmt"] != "yuv420p"
            or row["profile"] not in {"High", "Main", "Constrained Baseline"}
            or abs(float(row["duration"]) - duration) > 1 / 30
            or abs(float(row.get("start_time", 0))) > 1 / 30):
        raise ValueError("Full video failed timing, frame-count or native playback checks")
    if not silent:
        audio = next(row for row in info["streams"] if row["codec_type"] == "audio")
        if abs(float(audio["duration"]) - duration) > .05 or abs(float(audio.get("start_time", 0))) > .05:
            raise ValueError("Audio/video duration or starting timestamp changed")


def inspect(output):
    from PIL import Image, ImageDraw

    output = Path(output).resolve()
    rendered = common.read_json(output / "render.json")
    plan = common.read_json(output / "plan.json")
    moments = plan["review_times"]
    evidence = extract_keyframes(video_path=rendered["video"], output_dir=output / "frames",
                                timestamps=moments, ffmpeg_executable=pilot.FFMPEG)
    if not evidence.success or len(evidence.frame_paths) != len(moments):
        raise ValueError("Incomplete full-film pixel evidence")
    frames = [{"time": time, "path": path, "sha256": common.sha(path)}
              for time, path in zip(moments, evidence.frame_paths, strict=True)]
    sheets = []
    for offset in range(0, len(frames), 6):
        sheet = Image.new("RGB", (1440, 1296), "#202226")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(frames[offset:offset + 6]):
            with Image.open(row["path"]) as original:
                thumb = original.copy()
                thumb.thumbnail((720, 405))
            x, y = index % 2 * 720, index // 2 * 432
            sheet.paste(thumb, (x, y + 26))
            draw.text((x + 8, y + 7), f"{row['time']:.3f}s", fill="white")
        path = output / "frames" / f"contact-{offset // 6 + 1:02d}.jpg"
        sheet.save(path, quality=94)
        sheets.append({"path": str(path), "sha256": common.sha(path)})
    common.write_json(output / "review-input.json", {"render": rendered, "frames": frames, "sheets": sheets,
        "events": common.read_json(output / "visual-events.json"),
        "motion_files": [{"path": str(output / name), "sha256": common.sha(output / name)}
                         for name in plan["motion_files"]],
        "instruction": "Review actual intermediate pixels, semantic identity, positive-root math and narration timing. Do not claim listening or student comprehension testing."})


def bindings(output):
    output = Path(output)
    rendered = common.read_json(output / "render.json")
    plan = common.read_json(output / "plan.json")
    if common.sha(output / "plan.json") != rendered["plan_sha256"]:
        raise ValueError("Plan changed since render")
    for path, expected in rendered["input_hashes"].items():
        if common.sha(path) != expected:
            raise ValueError("Scene implementation changed since render")
    if common.sha(rendered["video"]) != rendered["video_sha256"]:
        raise ValueError("Full visual master changed")
    evidence = common.read_json(output / "review-input.json")
    if evidence["render"] != rendered:
        raise ValueError("Evidence belongs to a different render")
    for row in [*evidence["frames"], *evidence["sheets"], *evidence["motion_files"]]:
        if common.sha(row["path"]) != row["sha256"]:
            raise ValueError("Reviewed pixels or motion changed")
    events = common.read_json(output / "visual-events.json")
    if evidence["events"] != events:
        raise ValueError("Reviewed visual events changed")
    check_timing(plan, events)
    return {"plan_sha256": common.sha(output / "plan.json"),
            "video_sha256": rendered["video_sha256"], "base_video_sha256": plan["base_video_sha256"],
            "evidence_sha256": common.sha(output / "review-input.json"),
            "events_sha256": common.sha(output / "visual-events.json")}


def mux_command(visual, base, target, duration):
    return [pilot.FFMPEG, "-v", "error", "-n", "-i", visual, "-i", base,
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
            "-t", str(duration), "-movflags", "+faststart", target]


def release(output, review_path):
    output, review_path = Path(output).resolve(), Path(review_path).resolve()
    current = bindings(output)
    review = common.read_json(review_path)
    if (review.get("status") != "pass" or review.get("reviewer_role") != "independent"
            or not review.get("reviewer_agent") or review.get("bindings") != current
            or review.get("blocking_findings") != [] or review.get("release_authorized") is not True):
        raise ValueError("Current independent full-film review required before composition")
    plan = common.read_json(output / "plan.json")
    base, _ = partial.verify_base(plan)
    visual = common.read_json(output / "render.json")["video"]
    playback = output / "playback"
    playback.mkdir(exist_ok=False)
    full = playback / "projectile-vox-v01-all-formula-motion.mp4"
    pilot.run(mux_command(visual, base["video"], full, plan["duration"]), timeout=180)
    check_video(pilot.probe(full), plan["duration"])
    if partial.packet_hash(full, "0:a:0") != partial.packet_hash(base["video"], "0:a:0"):
        raise ValueError("Selected V01 audio packets changed")
    if partial.packet_hash(full, "0:v:0") != partial.packet_hash(visual, "0:v:0"):
        raise ValueError("Approved visual packets changed")
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", full, "-f", "null", "-"], timeout=180)
    result = {"video": str(full), "sha256": common.sha(full), "duration": plan["duration"],
        "bindings": current, "review": str(review_path), "review_sha256": common.sha(review_path),
        "audio_packets_unchanged": True, "approved_visual_packets_unchanged": True,
        "full_decode_passed": True, "authorship": plan["authorship"],
        "limitations": ["No new listening or student comprehension test", "Supervised refinement, not an isolated model benchmark"],
        "writer": "Full-film release gate", "consumers": ["user", "auditor"],
        "lifecycle": "This approved derivative", "invalidation": "Any media, timing, plan or review change"}
    common.write_json(output / "delivery.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("render")
    command.add_argument("--plan", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    for name in ("bindings", "release"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "release":
            command.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "render":
        value = {"video": str(render(args.plan, args.output))}
    elif args.command == "bindings":
        value = bindings(args.output)
    else:
        value = release(args.output, args.review)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
