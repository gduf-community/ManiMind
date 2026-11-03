"""Versioned visual refinements with unchanged narration and a fresh review gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

from . import pilot, preset_audition as common
from manimind.render.manim_renderer import build_manim_render_command, write_scene_code, extract_keyframes, _render_environment


def verify_base(plan):
    delivery = common.read_json(plan["base_delivery"])
    video = Path(delivery["video"])
    if (common.sha(video) != plan["base_video_sha256"] or delivery["sha256"] != plan["base_video_sha256"]
            or not delivery.get("full_decode_passed") or common.sha(delivery["review"]) != delivery["review_sha256"]):
        raise ValueError("Base media or its delivery/review binding changed")
    review = common.read_json(delivery["review"])
    if review.get("status") != "pass" or review.get("bindings") != delivery["bindings"]:
        raise ValueError("A genuine passed base timing review is required")
    info = pilot.probe(video)
    if sorted(row["codec_type"] for row in info["streams"]) != ["audio", "video"]:
        raise ValueError("Expected the approved AV-only viewing preview")
    stream = next(row for row in info["streams"] if row["codec_type"] == "video")
    if [stream["width"], stream["height"]] != [1920, 1080] or stream["avg_frame_rate"] != "30/1":
        raise ValueError("Refinement requires the current 1080p30 base")
    if (plan["fps"] != 30 or plan["replace_start"] < 0 or plan["replace_duration"] <= 0
            or plan["replace_start"] + plan["replace_duration"] > float(info["format"]["duration"])):
        raise ValueError("Invalid replacement interval")
    return delivery, info


def render(plan_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    plan = common.read_json(plan_path)
    verify_base(plan)
    scene = pilot.ROOT / plan["scene"]
    watched = [scene, pilot.ROOT / "src/manimind/components/formula_motion.py",
               pilot.ROOT / "src/manimind/experiments/visual_first_support.py",
               pilot.ROOT / "src/manimind/experiments/freeform_support.py",
               pilot.ROOT / "src/manimind/components/typography.py", Path(__file__)]
    before = {str(path): common.sha(path) for path in watched}
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(plan_path, output / "plan.json")
    (output / "source").mkdir()
    for path in watched:
        shutil.copyfile(path, output / "source" / path.name)
    anchors = ["vertical_equation_linked", "ground_condition_applied", "term_relocated",
               "height_doubled", "square_time_isolated", "landing_time_derived"]
    common.write_json(output / "timeline.json", {"mode": "visual_first_silent", "fps": 30,
        "duration": plan["replace_duration"], "cues": [{"id": "landing_condition", "start": 0,
        "duration": plan["replace_duration"], "spoken_spans": [],
        "anchors": [{"id": name, "meaning": name} for name in anchors]}]})
    config = output / "render.yml"
    with config.open("x", encoding="utf-8") as stream:
        stream.write('camera:\n  background_color: "#101416"\n  fps: 30\ntex:\n  template: "basic_ctex"\n')
    code = write_scene_code(scene.read_text(), output_dir=output, segment_id="formula-motion")
    command = build_manim_render_command(code_path=code, scene_class_name=plan["scene_class"],
        output_dir=output, segment_id="formula-motion", quality="h", config_file=config)
    env = _render_environment()
    env.update(PYTHONPATH=str(pilot.ROOT / "src"), MANIMIND_FREEFORM_OUTPUT=str(output),
               MANIMIND_DISABLE_DOTENV="1", PYTHONDONTWRITEBYTECODE="1")
    print(json.dumps({"status": "rendering", "output": str(output)}), flush=True)
    with (output / "render.log").open("x") as log:
        result = subprocess.run(command, env=env, cwd=pilot.ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=900)
    if result.returncode:
        raise RuntimeError(f"Render failed ({result.returncode}); retain {output / 'render.log'}")
    if before != {str(path): common.sha(path) for path in watched}:
        raise ValueError("Render source changed while running")
    videos = list((output / "manim/media/manimgl").glob("**/formula-motion.mp4"))
    if len(videos) != 1:
        raise ValueError("Expected one replacement video")
    video = videos[0]
    metadata = pilot.probe(video)
    if (len(metadata["streams"]) != 1 or metadata["streams"][0]["codec_type"] != "video"
            or int(metadata["streams"][0]["nb_frames"]) != round(plan["replace_duration"] * 30)):
        raise ValueError("Replacement frame count or stream layout changed")
    events = common.read_json(output / "visual-events.json")
    measured = {row["id"]: row["time"] for row in events["events"]}
    if any(abs(measured[name] - target) > 1 / 30 for name, target in plan["timing_targets"].items()):
        raise ValueError("Refinement drifted from the existing narration anchors")
    common.write_json(output / "render.json", {"video": str(video), "video_sha256": common.sha(video),
        "input_hashes": before, "plan_sha256": common.sha(output / "plan.json"), "command": command,
        "writer": "Formula refinement renderer", "consumers": ["reviewer", "release gate"],
        "lifecycle": "This exact render attempt", "invalidation": "Any source, plan or media change"})
    inspect(output)
    return video


def inspect(output):
    from PIL import Image, ImageDraw

    output = Path(output).resolve()
    rendered = common.read_json(output / "render.json")
    moments = [.7, 2.4, 6.9, 7.9, 8.5, 8.9, 9.3, 9.7, 10.2, 10.6, 11.1, 11.7, 12.1, 12.5, 13.2, 16, 19.5]
    evidence = extract_keyframes(video_path=rendered["video"], output_dir=output / "frames",
                                timestamps=moments, ffmpeg_executable=pilot.FFMPEG)
    if not evidence.success or len(evidence.frame_paths) != len(moments):
        raise ValueError("Incomplete refinement pixels")
    frames = [{"time": time, "path": path, "sha256": common.sha(path)}
              for time, path in zip(moments, evidence.frame_paths, strict=True)]
    sheets = []
    for offset in range(0, len(frames), 6):
        sheet = Image.new("RGB", (1440, 3 * 432), "#202226")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(frames[offset:offset + 6]):
            with Image.open(row["path"]) as original:
                thumb = original.copy()
                thumb.thumbnail((720, 405))
            x, y = index % 2 * 720, index // 2 * 432
            sheet.paste(thumb, (x, y + 26))
            draw.text((x + 8, y + 7), f"{row['time']:.2f}s", fill="white")
        path = output / "frames" / f"contact-{offset // 6 + 1:02d}.jpg"
        sheet.save(path, quality=94)
        sheets.append({"path": str(path), "sha256": common.sha(path)})
    common.write_json(output / "review-input.json", {"render": rendered, "frames": frames, "sheets": sheets,
        "events": common.read_json(output / "visual-events.json"),
        "motion_samples": str(output / "motion-samples.json"),
        "instruction": "Inspect actual token trajectories, math, appearance and unchanged narration anchors; no listening claim"})
    return frames


def bindings(output):
    output = Path(output)
    rendered = common.read_json(output / "render.json")
    plan = common.read_json(output / "plan.json")
    if common.sha(output / "plan.json") != rendered["plan_sha256"]:
        raise ValueError("Plan changed since render")
    for path, expected in rendered["input_hashes"].items():
        if common.sha(path) != expected:
            raise ValueError("Live implementation changed since render")
    if common.sha(rendered["video"]) != rendered["video_sha256"]:
        raise ValueError("Patch video changed")
    evidence = common.read_json(output / "review-input.json")
    if evidence["render"] != rendered:
        raise ValueError("Evidence belongs to a different render")
    for row in [*evidence["frames"], *evidence["sheets"]]:
        if common.sha(row["path"]) != row["sha256"]:
            raise ValueError("Reviewed pixels changed")
    return {"plan_sha256": common.sha(output / "plan.json"),
            "patch_video_sha256": rendered["video_sha256"], "base_video_sha256": plan["base_video_sha256"],
            "evidence_sha256": common.sha(output / "review-input.json"),
            "motion_sha256": common.sha(output / "motion-samples.json"),
            "events_sha256": common.sha(output / "visual-events.json")}


def packet_hash(video, stream):
    return pilot.run([pilot.FFMPEG, "-v", "error", "-i", video, "-map", stream, "-c", "copy",
                      "-f", "hash", "-hash", "sha256", "-"]).strip()


def outside_frames(video, start_frame, end_frame):
    raw = pilot.run([pilot.FFMPEG, "-v", "error", "-i", video, "-map", "0:v:0", "-vf",
        f"select='lt(n,{start_frame})+gte(n,{end_frame})'", "-fps_mode", "passthrough", "-f", "framemd5", "-"], timeout=180)
    return [line.rsplit(",", 1)[-1].strip() for line in raw.splitlines() if line and not line.startswith("#")]


def composition_command(base, patch, master, a, b, count, total):
    filters = (f"[0:v]split=2[prefix][suffix];[prefix]trim=start_frame=0:end_frame={a},setpts=PTS-STARTPTS[pre];"
               f"[suffix]trim=start_frame={b}:end_frame={count},setpts=PTS-STARTPTS[post];"
               "[1:v]setpts=PTS-STARTPTS[patch];[pre][patch][post]concat=n=3:v=1:a=0[complete]")
    return [pilot.FFMPEG, "-v", "error", "-n", "-i", base, "-i", patch,
            "-filter_complex", filters, "-map", "[complete]", "-map", "0:a:0", "-c:v", "libx264", "-crf", "0",
            "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "copy", "-t", str(total),
            "-movflags", "+faststart", master]


def distribution_command(master, full):
    return [pilot.FFMPEG, "-v", "error", "-n", "-i", master, "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "libx264", "-profile:v", "high", "-level:v", "4.0", "-crf", "18", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "copy", "-movflags", "+faststart", full]


def release(output, review_path):
    output, review_path = Path(output).resolve(), Path(review_path).resolve()
    current = bindings(output)
    review = common.read_json(review_path)
    if (review.get("status") != "pass" or review.get("reviewer_role") != "independent"
            or not review.get("reviewer_agent") or review.get("bindings") != current):
        raise ValueError("Current independent formula-motion review required before composition")
    plan = common.read_json(output / "plan.json")
    base, base_info = verify_base(plan)
    patch = common.read_json(output / "render.json")["video"]
    playback = output / "playback"
    playback.mkdir(exist_ok=False)
    start, duration = plan["replace_start"], plan["replace_duration"]
    end, total = start + duration, float(base_info["format"]["duration"])
    a, b, count = round(start * 30), round(end * 30), round(total * 30)
    full = playback / "projectile-vox-v01-formula-motion.mp4"
    master = output / "verification-master.mp4"
    pilot.run(composition_command(base["video"], patch, master, a, b, count, total), timeout=600)
    master_info = next(row for row in pilot.probe(master)["streams"] if row["codec_type"] == "video")
    if int(master_info["nb_frames"]) != count or master_info["avg_frame_rate"] != "30/1":
        raise ValueError("Composition changed the original frame rate or frame count")
    original, exported = outside_frames(base["video"], a, b), outside_frames(master, a, b)
    if original != exported or len(original) != count - (b - a):
        raise ValueError("Decoded pixels outside the refined chapter changed")
    # Lossless x264 can require High 4:4:4 Predictive; export ordinary High for native players.
    pilot.run(distribution_command(master, full), timeout=600)
    info = pilot.probe(full)
    video_info = next(row for row in info["streams"] if row["codec_type"] == "video")
    if sorted(row["codec_type"] for row in info["streams"]) != ["audio", "video"] or int(video_info["nb_frames"]) != count:
        raise ValueError("Refined full video changed duration or stream layout")
    if packet_hash(full, "0:a:0") != packet_hash(base["video"], "0:a:0"):
        raise ValueError("Selected V01 narration packets changed")
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", full, "-f", "null", "-"], timeout=180)
    clip = playback / "formula-motion-20s.mp4"
    pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-i", patch, "-ss", str(start), "-i", base["video"],
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration), "-movflags", "+faststart", clip], timeout=180)
    result = {"video": str(full), "sha256": common.sha(full), "clip": str(clip), "clip_sha256": common.sha(clip),
        "duration": total, "replacement": [start, end], "bindings": current, "review": str(review_path),
        "review_sha256": common.sha(review_path), "audio_packets_unchanged": True,
        "verification_master": str(master), "verification_master_sha256": common.sha(master),
        "outside_master_decoded_frames_identical": len(original), "full_decode_passed": True,
        "distribution_encoding": "Compatible H.264 High yuv420p CRF18; recompressed from the pixel-verified lossless master",
        "authorship": plan["authorship"], "limitations": ["No new full listening or student test", "New visual refinement, not an isolated model benchmark"],
        "writer": "Formula refinement release gate", "consumers": ["user", "auditor"],
        "lifecycle": "This approved derivative", "invalidation": "Any source, media, timing or review change"}
    common.write_json(output / "delivery.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("render")
    command.add_argument("--plan", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("bindings")
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("release")
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "render":
        print(json.dumps({"video": str(render(args.plan, args.output))}))
    elif args.command == "bindings":
        print(json.dumps(bindings(args.output)))
    else:
        print(json.dumps(release(args.output, args.review), ensure_ascii=False))


if __name__ == "__main__":
    main()
