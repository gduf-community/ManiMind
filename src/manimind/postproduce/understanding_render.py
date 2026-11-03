"""Versioned visual rendering and actual focus evidence, without publication."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

from . import pilot, preset_audition as common
from .formula_film import check_video
from manimind.experiments.visual_first_data import visual_timeline, validate_events
from manimind.review.semantic_focus import focus_windows
from manimind.review.content_regression import revision_required
from manimind.render.manim_renderer import (
    _render_environment, build_manim_render_command, extract_keyframes, write_scene_code,
)


def sources(plan):
    names = [plan["scene"], plan["workflow_profile"], "src/manimind/postproduce/understanding_render.py",
             "src/manimind/postproduce/formula_film.py", "src/manimind/render/manim_renderer.py",
             "src/manimind/experiments/understanding_support.py", "src/manimind/experiments/visual_first_support.py",
             "src/manimind/experiments/visual_first_data.py", "src/manimind/experiments/freeform_support.py",
             "src/manimind/components/typography.py", "src/manimind/components/formula_motion.py",
             "src/manimind/review/semantic_focus.py", *plan.get("sources", [])]
    if revision_required(plan):
        names += [plan["revision_contract"], "src/manimind/review/content_regression.py"]
    return list(dict.fromkeys(pilot.ROOT / name for name in names))


def render(plan_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    plan = common.read_json(plan_path)
    plan.setdefault("workflow_profile", "configs/visual-first-workflow-v2.json")
    profile = common.read_json(pilot.ROOT / plan["workflow_profile"])
    if profile["version"] not in {"understanding-first-v2", "understanding-first-v3"}:
        raise ValueError("Use the declared understanding-first profile, not an implicit legacy workflow")
    revision_required(plan, profile_version=profile["version"])
    timeline = visual_timeline(plan)
    watched = sources(plan)
    before = {str(path): common.sha(path) for path in watched}
    output.mkdir(parents=True, exist_ok=False)
    common.write_json(output / "plan.json", plan)
    common.write_json(output / "timeline.json", timeline)
    common.write_json(output / "workflow-profile.json", profile)
    for path in watched:
        target = output / "source" / path.relative_to(pilot.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    config = output / "render.yml"
    with config.open("x", encoding="utf-8") as stream:
        stream.write('camera:\n  background_color: "#101416"\n  fps: 30\ntex:\n  template: "basic_ctex"\n')
    code = write_scene_code((pilot.ROOT / plan["scene"]).read_text(), output_dir=output, segment_id="understanding")
    command = build_manim_render_command(code_path=code, scene_class_name=plan["scene_class"],
        output_dir=output, segment_id="understanding", quality="h", config_file=config)
    env = _render_environment()
    env.update(PYTHONPATH=os.pathsep.join(str(pilot.ROOT / name) for name in ("src", "examples")),
               MANIMIND_FREEFORM_OUTPUT=str(output), MANIMIND_DISABLE_DOTENV="1", PYTHONDONTWRITEBYTECODE="1")
    print(json.dumps({"status": "rendering", "output": str(output)}), flush=True)
    with (output / "render.log").open("x") as log:
        result = subprocess.run(command, env=env, cwd=pilot.ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
    if result.returncode:
        raise RuntimeError(f"Visual render failed; retain {output / 'render.log'}")
    if before != {str(path): common.sha(path) for path in watched}:
        raise ValueError("Visual implementation changed during render")
    videos = list((output / "manim/media/manimgl").glob("**/understanding.mp4"))
    if len(videos) != 1:
        raise ValueError("Expected one unambiguous silent visual master")
    video = videos[0]
    check_video(pilot.probe(video), timeline["duration"], silent=True)
    validate_events(timeline, common.read_json(output / "visual-events.json"))
    focus_windows(common.read_json(output / "focus-events.json"), timeline["duration"])
    record = {"video": str(video), "video_sha256": common.sha(video), "duration": timeline["duration"],
              "plan_sha256": common.sha(output / "plan.json"), "input_hashes": before, "command": command,
              "writer": "Understanding visual renderer", "consumers": ["independent reviewer", "narrator", "release gate"],
              "lifecycle": "This exact render attempt", "invalidation": "Visual source, plan, profile, runtime or media change"}
    common.write_json(output / "render.json", record)
    inspect(output)
    return record


def inspect(output):
    from PIL import Image, ImageDraw

    output = Path(output)
    record, plan = common.read_json(output / "render.json"), common.read_json(output / "plan.json")
    timeline, focus = common.read_json(output / "timeline.json"), common.read_json(output / "focus-events.json")
    moments = list(plan.get("review_times", []))
    for cue in timeline["cues"]:
        moments += [cue["start"] + cue["duration"] * fraction for fraction in (.2, .5, .8)]
    for row in focus["windows"]:
        moments += [row["start"] + (row["end"] - row["start"]) * fraction for fraction in (.08, .5, .92)]
    moments = sorted({round(t, 3) for t in moments if 0 <= t < timeline["duration"]})
    evidence = extract_keyframes(video_path=record["video"], output_dir=output / "frames",
                                timestamps=moments, ffmpeg_executable=pilot.FFMPEG)
    if not evidence.success or len(evidence.frame_paths) != len(moments):
        raise ValueError("Incomplete actual pixel evidence")
    frames = [{"time": t, "path": path, "sha256": common.sha(path)}
              for t, path in zip(moments, evidence.frame_paths, strict=True)]
    sheets = []
    for offset in range(0, len(frames), 9):
        sheet = Image.new("RGB", (1920, 1152), "#202226")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(frames[offset:offset + 9]):
            with Image.open(row["path"]) as original:
                thumb = original.copy()
                thumb.thumbnail((640, 360))
            x, y = index % 3 * 640, index // 3 * 384
            sheet.paste(thumb, (x, y + 24))
            draw.text((x + 7, y + 6), f"{row['time']:.3f}s", fill="white")
        path = output / "frames" / f"contact-{offset // 9 + 1:02d}.jpg"
        sheet.save(path, quality=94)
        sheets.append({"path": str(path), "sha256": common.sha(path)})
    common.write_json(output / "review-input.json", {"render": record, "frames": frames, "sheets": sheets,
        "cue_boundaries": [{key: row[key] for key in ("id", "start", "duration")} for row in timeline["cues"]],
        "writer": "Actual visual evidence extractor", "consumers": ["independent reviewer"],
        "lifecycle": "This exact render", "invalidation": "Any video, frame or measured event change"})


def bindings(output):
    output = Path(output)
    rendered = common.read_json(output / "render.json")
    if common.sha(output / "plan.json") != rendered["plan_sha256"]:
        raise ValueError("Visual plan changed since render")
    for path, expected in rendered["input_hashes"].items():
        if common.sha(path) != expected:
            raise ValueError("Visual source/profile/runtime changed since render")
    if common.sha(rendered["video"]) != rendered["video_sha256"]:
        raise ValueError("Visual master changed")
    evidence = common.read_json(output / "review-input.json")
    if evidence["render"] != rendered:
        raise ValueError("Pixels belong to a different render")
    for row in [*evidence["frames"], *evidence["sheets"]]:
        if common.sha(row["path"]) != row["sha256"]:
            raise ValueError("Reviewed pixels changed")
    timeline, focuses = common.read_json(output / "timeline.json"), common.read_json(output / "focus-events.json")
    if timeline != visual_timeline(common.read_json(output / "plan.json")):
        raise ValueError("Measured timeline differs from current visual plan")
    validate_events(timeline, common.read_json(output / "visual-events.json"))
    focus_windows(focuses, timeline["duration"])
    return {"plan_sha256": common.sha(output / "plan.json"), "render_sha256": common.sha(output / "render.json"),
            "profile_sha256": common.sha(output / "workflow-profile.json"), "visual_sha256": rendered["video_sha256"],
            "evidence_sha256": common.sha(output / "review-input.json"),
            "focuses_sha256": common.sha(output / "focus-events.json"),
            "events_sha256": common.sha(output / "visual-events.json")}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("render", "bindings"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    if args.command == "render" and args.plan is None:
        parser.error("render requires --plan")
    value = render(args.plan, args.output) if args.command == "render" else bindings(args.output)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
