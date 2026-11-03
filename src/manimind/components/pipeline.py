"""Offline component workflow: validate -> render -> inspect -> review -> publish.

No provider imports or network calls. The project owns an immutable plan; each
render owns its own source, telemetry and frames. Reviewer output is separate.
"""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil

from .catalog import catalog, FONT_PATH, NUMBER_FONT_PATH
from .plan import identifier, parse_plan, preflight
from ..postproduce import pilot
from ..render import render_manim_scene, extract_keyframes

ROOT = pilot.ROOT
CONFIG = ROOT / "configs/component-render.yml"


def paths(project):
    identifier(project)
    return (ROOT / "outputs" / project, ROOT / "runtime/projects" / project,
            ROOT / "runtime/sessions" / f"{project}-components")


@contextmanager
def command_lock(project):
    session = paths(project)[2]
    session.mkdir(parents=True, exist_ok=True)
    lock = session / "command.lock"
    with lock.open("x") as stream:
        stream.write("Component CLI command owns this lock; stale locks require operator verification.\n")
    try:
        yield
    finally:
        lock.unlink()


def init(plan_path):
    plan = parse_plan(Path(plan_path).read_text(encoding="utf-8"))
    out, context, session = paths(plan["id"])
    if out.exists() or context.exists():
        raise ValueError("Project already exists; changed input requires a new project ID")
    report = preflight(plan)
    out.mkdir(parents=True)
    pilot.write_json(out / "plan.json", plan)
    pilot.write_json(out / "preflight.json", report)
    pilot.write_json(context / "component-plan.json", {
        "scope": "long_term", "writer_role": "planner", "consumer_roles": ["worker", "reviewer", "assembler"],
        "lifecycle": "This immutable component project",
        "invalidation_rule": "Changed plan requires a new project ID; changed component implementation requires a new render and review.",
        "plan_sha256": pilot.sha256(out / "plan.json"), "provenance": plan["provenance"],
        "production_mode": "silent_component_calibration", "is_model_benchmark": False,
        "pipeline_llm_requests": 0, "upstream_model_usage_verified": False})
    pilot.write_json(session / "events.json", {
        "scope": "short_term", "writer_role": "coordinator", "consumer_roles": ["lead", "reviewer"],
        "lifecycle": "This component production session",
        "invalidation_rule": "Append attempts, never replace failed evidence; input change requires new project.",
        "events": [{"action": "init", "status": "validated"}]})
    return plan["id"]


def frozen_plan(project):
    out, context, _ = paths(project)
    frozen = pilot.read_json(context / "component-plan.json")
    if pilot.sha256(out / "plan.json") != frozen["plan_sha256"]:
        raise ValueError("Frozen plan was modified")
    return parse_plan((out / "plan.json").read_text(encoding="utf-8"))


def input_hashes(project):
    frozen_plan(project)
    out, context, _ = paths(project)
    files = {"plan": out / "plan.json", "project": context / "component-plan.json", "config": CONFIG,
             "render_driver": ROOT / "src/manimind/render/manim_renderer.py",
             "review_helpers": Path(pilot.__file__),
             "layout_guard": ROOT / "src/manimind/experiments/layout_guard.py",
             "font": FONT_PATH, "number_font": NUMBER_FONT_PATH}
    files.update({f"component_{p.stem}": p for p in Path(__file__).parent.glob("*.py")})
    return {name: pilot.sha256(path) for name, path in files.items()}


def event(project, entry):
    path = paths(project)[2] / "events.json"
    value = pilot.read_json(path)
    value["events"].append(entry)
    pilot.write_json(path, value)


def attempt_dir(project, attempt):
    if type(attempt) is not int or attempt < 1:
        raise ValueError("Positive attempt number required")
    return paths(project)[0] / "renders" / f"{attempt:03d}"


def evidence_hashes(project, attempt):
    folder = attempt_dir(project, attempt)
    result = pilot.read_json(folder / "render.json")
    current = input_hashes(project)
    if current != result["inputs"]:
        raise ValueError("Stale component render: input or implementation changed")
    if pilot.sha256(Path(result["code_path"])) != result["wrapper_sha256"]:
        raise ValueError("Changed render wrapper")
    return {**current, "wrapper": result["wrapper_sha256"],
            "video": pilot.sha256(Path(result["video_path"])),
            "frame_audit": pilot.sha256(folder / "frame-audit.json")}


def validate_audit(report, expected_frames, shot_ids):
    records = report.get("frames", [])
    if (report.get("complete") is not True or report.get("frames_checked") != expected_frames
            or not isinstance(records, list) or not records or report.get("issues")):
        raise ValueError("Rendered component audit missing or blocked")
    if any(r.get("issues") or r.get("shot") not in shot_ids for r in records):
        raise ValueError("Component frame audit blocked")
    frames = [r.get("frame") for r in records]
    if any(type(f) is not int for f in frames) or len(set(frames)) != len(frames):
        raise ValueError("Invalid frame index")
    if frames != list(range(1, expected_frames + 1)):
        raise ValueError("Incomplete per-frame audit")
    if any(type(r.get("fraction")) not in (float, int) or not 0 <= r["fraction"] <= 1 for r in records):
        raise ValueError("Invalid frame fraction")
    for shot in shot_ids:
        if not any(r["shot"] == shot and r["fraction"] >= .99 for r in records):
            raise ValueError("Missing final state for a shot")


def render(project, quality="h"):
    out, _, session = paths(project)
    plan = frozen_plan(project)
    checked = preflight(plan)
    parent = out / "renders"
    parent.mkdir(exist_ok=True)
    attempt = max([int(p.name) for p in parent.iterdir() if p.is_dir() and p.name.isdecimal()] + [0]) + 1
    folder = attempt_dir(project, attempt)
    folder.mkdir()
    before = input_hashes(project)
    wrapper = ("from pathlib import Path\nfrom manimind.components.renderer import ComponentScene\n\n"
               "class ComponentDemo(ComponentScene):\n"
               f"    plan_path = Path({str(out / 'plan.json')!r})\n"
               f"    asset_dir = Path({str(folder)!r})\n")
    event(project, {"action": "render", "attempt": attempt, "status": "started", "inputs": before})
    try:
        result = render_manim_scene(segment_id="components", scene_code=wrapper,
                    scene_class_name="ComponentDemo", output_dir=folder, quality=quality,
                    config_file=CONFIG, timeout_seconds=1800)
        pilot.write_json(session / f"render-{attempt:03d}.json", result.to_dict())
        if not result.success:
            raise ValueError(f"Render failed: {result.error}; see session log")
        if input_hashes(project) != before:
            raise ValueError("Inputs changed during render")
        pilot.write_json(folder / "render.json", {**result.to_dict(), "inputs": before,
                         "wrapper_sha256": pilot.sha256(Path(result.code_path)), "preflight": checked})
        validate_audit(pilot.read_json(folder / "frame-audit.json"), checked["total_frames"],
                       [s["id"] for s in plan["shots"]])
        event(project, {"action": "render", "attempt": attempt, "status": "rendered_and_mechanically_checked"})
    except Exception as error:
        event(project, {"action": "render", "attempt": attempt, "status": "failed", "error": str(error)[:2000]})
        raise
    return attempt


def inspect(project, attempt):
    from PIL import Image, ImageDraw
    folder = attempt_dir(project, attempt)
    result = pilot.read_json(folder / "render.json")
    hashes = evidence_hashes(project, attempt)
    plan = frozen_plan(project)
    validate_audit(pilot.read_json(folder / "frame-audit.json"), result["preflight"]["total_frames"],
                   [s["id"] for s in plan["shots"]])
    video = Path(result["video_path"])
    stream = next(s for s in pilot.probe(video)["streams"] if s["codec_type"] == "video")
    if abs(float(stream["duration"]) - result["preflight"]["duration"]) > .05:
        raise ValueError("Rendered timing drift")
    requests = [(s["shot"], round((s["start_frame"] + (s["end_frame"] - s["start_frame"]) * f) / 30, 3))
                for s in result["preflight"]["shots"] for f in (.1, .45, .8, .95)]
    extraction = extract_keyframes(video_path=video, output_dir=folder / "frames",
                 timestamps=[t for _, t in requests], ffmpeg_executable=pilot.FFMPEG)
    if not extraction.success or extraction.missing_timestamps or len(extraction.frame_paths) != len(requests):
        raise ValueError("Missing pixel evidence")
    if evidence_hashes(project, attempt) != hashes:
        raise ValueError("Inputs changed during frame extraction")
    frames = [{"shot": shot, "time": stamp, "path": str(Path(path).resolve()), "sha256": pilot.sha256(Path(path))}
              for (shot, stamp), path in zip(requests, extraction.frame_paths)]
    sheets = []
    for batch in range(0, len(frames), 12):
        sheet = Image.new("RGB", (1600, 1008), "#202226")
        draw = ImageDraw.Draw(sheet)
        for i, frame in enumerate(frames[batch:batch + 12]):
            with Image.open(frame["path"]) as im:
                thumb = im.copy()
                thumb.thumbnail((533, 225))
            x, y = i % 3 * 533, i // 3 * 252
            sheet.paste(thumb, (x, y + 24))
            draw.text((x + 5, y + 5), f"{frame['shot']} / {frame['time']}s", fill="white")
        path = folder / "frames" / f"contact-{batch // 12 + 1:02d}.jpg"
        sheet.save(path, quality=94)
        sheets.append(str(path))
    pilot.write_json(folder / "review-input.json", {
        "project_id": project, "attempt": attempt, "hashes": hashes,
        "video_path": str(video), "plan_path": str(paths(project)[0] / "plan.json"),
        "frames": frames, "contact_sheets": sheets, "required_shots": [s["id"] for s in plan["shots"]],
        "resolution": [stream["width"], stream["height"]], "duration": float(stream["duration"]),
        "review_checks": ["mathematics", "visual_layout", "narrative", "cue_timing"],
        "scope": "Silent engineering component calibration, not a finished narrated lesson or LLM benchmark.",
        "instruction": "Independent reviewer must inspect actual original frames from every shot and verify semantics against plan/source. Mechanical telemetry is not aesthetic approval."})
    event(project, {"action": "inspect", "attempt": attempt, "status": "awaiting_independent_review"})


def publish(project, attempt):
    out, context, _ = paths(project)
    folder = attempt_dir(project, attempt)
    evidence = pilot.read_json(folder / "review-input.json")
    current = evidence_hashes(project, attempt)
    if current != evidence["hashes"]:
        raise ValueError("Stale reviewed evidence")
    plan = frozen_plan(project)
    result = pilot.read_json(folder / "render.json")
    validate_audit(pilot.read_json(folder / "frame-audit.json"), result["preflight"]["total_frames"],
                   [s["id"] for s in plan["shots"]])
    review_path = context / f"review-{attempt:03d}.json"
    review = pilot.read_json(review_path)
    review_digest = pilot.sha256(review_path)
    validate_review_input(folder, review)
    if review.get("reviewer_id") == plan["provenance"]["author"]:
        raise ValueError("Producer cannot approve own output")
    pilot.validate_review(review, current, evidence["frames"], require_zoom=False)
    covered = {f["shot"] for f in evidence["frames"] if f["path"] in review["inspected_frames"]}
    if covered != {s["id"] for s in plan["shots"]}:
        raise ValueError("Every shot needs independent original-frame review")
    destination = out / f"component-demo-v{attempt:03d}.mp4"
    if destination.exists():
        raise ValueError("Published delivery is immutable")
    video = Path(result["video_path"])
    pilot.run([pilot.FFMPEG, "-v", "error", "-i", str(video), "-f", "null", "-"], timeout=300)
    if evidence_hashes(project, attempt) != current:
        raise ValueError("Inputs changed before publication")
    validate_review_input(folder, review)
    if pilot.sha256(review_path) != review_digest:
        raise ValueError("Review changed before publication")
    shutil.copy2(video, destination)
    pilot.write_json(out / f"delivery-{attempt:03d}.json", {
        "video": str(destination), "sha256": pilot.sha256(destination), "hashes": current,
        "review": str(review_path), "review_sha256": pilot.sha256(review_path),
        "duration": evidence["duration"], "resolution": evidence["resolution"],
        "provenance": plan["provenance"], "pipeline_llm_requests": 0, "upstream_model_usage_verified": False, "audio": False,
        "limitations": ["Engineering fixture, not LLM generation or a complete lesson.",
                        "Only the declared 2D component capabilities are supported.",
                        *review.get("limitations", [])]})
    event(project, {"action": "publish", "attempt": attempt, "status": "published"})
    return str(destination)


def validate_review_input(folder, review):
    path = folder / "review-input.json"
    if review.get("reviewed_input_sha256") != pilot.sha256(path):
        raise ValueError("Review input changed or was not bound to approval")
    evidence = pilot.read_json(path)
    for frame in evidence["frames"]:
        if not Path(frame["path"]).is_file() or pilot.sha256(Path(frame["path"])) != frame["sha256"]:
            raise ValueError("Reviewed frame changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["catalog", "check", "init", "render", "inspect", "publish"])
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--project-id")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--quality", choices=["l", "m", "h"], default="h")
    args = parser.parse_args()
    if args.action == "catalog":
        print(json.dumps(catalog(), ensure_ascii=False, indent=2))
        return
    if args.action in {"check", "init"}:
        if args.plan is None:
            parser.error("--plan is required")
        plan = parse_plan(args.plan.read_text(encoding="utf-8"))
        if args.action == "check":
            report = preflight(plan)
            summary = {key: report[key] for key in ("status", "duration", "fps", "total_frames", "limitations")}
            summary["shots"] = [{k: s[k] for k in ("shot", "frames_checked", "start_frame", "end_frame")} for s in report["shots"]]
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return
        args.project_id = plan["id"]
    if not args.project_id:
        parser.error("--project-id is required")
    with command_lock(args.project_id):
        if args.action == "init":
            result = init(args.plan)
        elif args.action == "render":
            result = render(args.project_id, args.quality)
        else:
            result = globals()[args.action](args.project_id, args.attempt)
    print(json.dumps({"action": args.action, "result": result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
