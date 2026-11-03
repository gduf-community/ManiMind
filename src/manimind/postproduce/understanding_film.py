"""Editorial gates and resumable narration after visual-first production.

Plans/reviews are immutable project/session inputs; each release/alignment lives
in a fresh output directory. Changing visuals invalidates focus and speech plans;
changing narration or gate code needs a fresh corresponding review, not a silent
rebind. This supervised entrypoint does not claim an isolated model benchmark.
"""

from __future__ import annotations

import argparse
import array
import json
from pathlib import Path
import shutil
import sys
import wave

from . import pilot, preset_audition as common, understanding_render as visual
from . import flexible_voxcpm as vox
from .formula_film import check_video
from manimind.review import understanding_quality as quality
from manimind.review import content_regression as regression
from manimind.review.semantic_focus import validate_narration, schedule, audit_coverage


def bindings(attempt, narration=None):
    attempt = Path(attempt).resolve()
    result = visual.bindings(attempt)
    plan = common.read_json(attempt / "plan.json")
    profile = common.read_json(attempt / "workflow-profile.json")
    if profile != common.read_json(pilot.ROOT / plan["workflow_profile"]):
        raise ValueError("Archived workflow differs from the actual profile")
    result.update(publisher_sha256=common.sha(__file__), editorial_contract_sha256=common.sha(quality.__file__))
    if regression.revision_required(plan, profile_version=profile["version"]):
        _, revision_hashes = regression.contract_bindings(pilot.ROOT / plan["revision_contract"], pilot.ROOT)
        result.update(revision_hashes)
    if narration is not None:
        narration = Path(narration).resolve()
        value = common.read_json(narration)
        validate_narration(value, common.read_json(attempt / "timeline.json"), common.read_json(attempt / "focus-events.json"))
        if value.get("visual_bindings") != visual.bindings(attempt):
            raise ValueError("Narration belongs to different visual inputs")
        result["narration_sha256"] = common.sha(narration)
    return result


def require_regression(attempt):
    attempt = Path(attempt).resolve()
    plan = common.read_json(attempt / "plan.json")
    profile = common.read_json(pilot.ROOT / plan.get("workflow_profile", "configs/visual-first-workflow-v2.json"))
    if not regression.revision_required(plan, profile_version=profile["version"]):
        return None
    contract, _ = regression.contract_bindings(pilot.ROOT / plan["revision_contract"], pilot.ROOT)
    path = pilot.ROOT / plan["revision_review"]
    report = common.read_json(path)
    regression.validate_comparison(report, contract, bindings(attempt), common.read_json(attempt / "timeline.json")["duration"])
    if report["status"] != "pass":
        raise ValueError("Content regression must pass independently before publication")
    return path


def require_review(attempt, path, *, narration=None):
    report = common.read_json(path)
    stage = "narration" if narration is not None else "visual"
    if (report.get("reviewer_role") != "independent" or not report.get("reviewer_agent")
            or report.get("stage") != stage or report.get("bindings") != bindings(attempt, narration)):
        raise ValueError("Require a current, independent, stage-bound editorial review")
    quality.validate_editorial_review(report, duration=common.read_json(Path(attempt) / "timeline.json")["duration"], stage=stage)
    if report["status"] != "pass":
        raise ValueError("Editorial revision is required before publication")
    comparison = require_regression(attempt)
    if comparison is not None and common.read_json(comparison)["reviewer_agent"] == report["reviewer_agent"] and stage == "visual":
        raise ValueError("Blind first look and baseline comparison require different reviewer contexts")
    return report


def install_narration(attempt, draft, visual_review, target):
    attempt, draft, target = (Path(path).resolve() for path in (attempt, draft, target))
    require_review(attempt, visual_review)
    value = common.read_json(draft)
    validate_narration(value, common.read_json(attempt / "timeline.json"), common.read_json(attempt / "focus-events.json"))
    result = {**value, "visual_bindings": visual.bindings(attempt), "source_draft": str(draft),
        "source_draft_sha256": common.sha(draft), "audio_status": "not_generated",
        "writer": "Post-visual narration installer", "consumers": ["independent text reviewer", "speech planner"],
        "lifecycle": "This reviewed visual version and narration revision", "invalidation": "Text, visual source, measured focus or profile change"}
    target.parent.mkdir(parents=True, exist_ok=True)
    common.write_json(target, result)
    return result


def release_silent(attempt, narration, visual_review, narration_review, output):
    attempt, narration, output = (Path(path).resolve() for path in (attempt, narration, output))
    require_review(attempt, visual_review)
    require_review(attempt, narration_review, narration=narration)
    record = common.read_json(attempt / "render.json")
    video = Path(record["video"])
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", video, "-f", "null", "-"], timeout=300)
    require_review(attempt, visual_review)
    require_review(attempt, narration_review, narration=narration)
    output.mkdir(parents=True, exist_ok=False)
    target = output / "visual-master.mp4"
    shutil.copyfile(video, target)
    if common.sha(target) != record["video_sha256"]:
        raise ValueError("Silent viewing copy changed")
    result = {"video": str(target), "sha256": common.sha(target), "duration": record["duration"],
        "scope": "Independently reviewed silent visual master and post-visual narration",
        "audio_status": "pending_local_gpu_generation", "attempt": str(attempt), "narration": str(narration),
        "visual_review": str(Path(visual_review).resolve()), "narration_review": str(Path(narration_review).resolve()),
        "visual_review_sha256": common.sha(visual_review), "narration_review_sha256": common.sha(narration_review),
        "bindings": bindings(attempt, narration), "full_decode_passed": True,
        "limitations": ["Silent, not a complete voiced film", "No listening or student comprehension test", "Supervised workflow fixture, not an autonomous model benchmark"],
        "writer": "Understanding-first silent release gate", "consumers": ["user", "future speech stage", "auditor"],
        "lifecycle": "This approved silent release", "invalidation": "Media, text, focus, workflow or review change"}
    comparison = require_regression(attempt)
    if comparison is not None:
        result.update(revision_review=str(comparison.resolve()), revision_review_sha256=common.sha(comparison))
    common.write_json(output / "delivery.json", result)
    return result


def verify_delivery(path):
    value = common.read_json(path)
    if common.sha(value["video"]) != value["sha256"] or value["bindings"] != bindings(value["attempt"], value["narration"]):
        raise ValueError("Approved visual/text delivery changed")
    for key in ("visual_review", "narration_review"):
        if common.sha(value[key]) != value[key + "_sha256"]:
            raise ValueError("Independent editorial review changed")
    comparison = require_regression(value["attempt"])
    if comparison is not None and (value.get("revision_review") != str(comparison.resolve())
                                   or value.get("revision_review_sha256") != common.sha(comparison)):
        raise ValueError("Approved content comparison changed")
    require_review(value["attempt"], value["visual_review"])
    require_review(value["attempt"], value["narration_review"], narration=value["narration"])
    return value


def speech_plan(delivery_path, reference, target):
    delivery_path, reference, target = (Path(path).resolve() for path in (delivery_path, reference, target))
    delivery = verify_delivery(delivery_path)
    receipt_path = reference.with_suffix(".receipt.json")
    receipt = common.read_json(receipt_path)
    if receipt.get("wav_sha256") != common.sha(reference) or common.sha(reference) != vox.REFERENCE_SHA256:
        raise ValueError("Require the selected synthetic V01 reference and its original receipt")
    attempt = Path(delivery["attempt"])
    result = {"schema_version": 2, "reference_kind": "selected_synthetic_reference", "synthetic_reference": True,
        "reference_sha256": common.sha(reference), "reference_source": str(reference),
        "reference_receipt": str(receipt_path), "reference_receipt_sha256": common.sha(receipt_path),
        "reference_text": vox.audition.TEXT, "generation": vox.GENERATION,
        "segments": common.read_json(delivery["narration"])["segments"],
        "source": {"delivery": str(delivery_path), "delivery_sha256": common.sha(delivery_path),
                   "video": delivery["video"], "video_sha256": delivery["sha256"],
                   "focuses": str(attempt / "focus-events.json"), "focuses_sha256": common.sha(attempt / "focus-events.json")},
        "writer": "Approved post-visual speech planner", "consumers": ["offline V01 worker", "focus scheduler", "reviewer"],
        "lifecycle": "This visual/text approval and selected voice", "invalidation": "Reference, model, source, focus or text change",
        "execution_status": "prepared_not_generated", "authorization": "User-selected synthetic V01; new text follows approved visuals"}
    vox.validate_plan(result)
    target.parent.mkdir(parents=True, exist_ok=True)
    common.write_json(target, result)
    return result


def verify_speech_source(plan):
    vox.validate_plan(plan)
    source = plan["source"]
    if common.sha(source["delivery"]) != source["delivery_sha256"]:
        raise ValueError("Source delivery changed")
    delivery = verify_delivery(source["delivery"])
    approved_focus = Path(delivery["attempt"]) / "focus-events.json"
    if (Path(source["focuses"]).resolve() != approved_focus.resolve()
            or source["focuses_sha256"] != delivery["bindings"]["focuses_sha256"]
            or common.sha(approved_focus) != delivery["bindings"]["focuses_sha256"]
            or Path(source["video"]).resolve() != Path(delivery["video"]).resolve()
            or common.sha(source["video"]) != delivery["sha256"] or source["video_sha256"] != delivery["sha256"]
            or plan["segments"] != common.read_json(delivery["narration"])["segments"]):
        raise ValueError("Speech plan no longer matches reviewed visuals/text/focus")
    return delivery


def speech_inputs(plan, plan_path, inputs):
    """Revalidate downloaded takes at alignment and again at final publication."""
    if len(inputs) != len(plan["segments"]):
        raise ValueError("Every utterance requires its own speech input")
    durations, checked = [], []
    for segment, item in zip(plan["segments"], inputs, strict=True):
        path, receipt_path = Path(item["wav"]), Path(item["receipt"])
        wav_sha, receipt_sha = common.sha(path), common.sha(receipt_path)
        if (("sha256" in item and item["sha256"] != wav_sha)
                or ("receipt_sha256" in item and item["receipt_sha256"] != receipt_sha)):
            raise ValueError("Measured speech or receipt changed")
        receipt = common.read_json(receipt_path)
        info, _ = common.pcm_info(path)
        if (receipt.get("plan_sha256") != common.sha(plan_path) or receipt.get("wav_sha256") != wav_sha
                or receipt.get("reference_sha256") != plan["reference_sha256"] or receipt.get("id") != segment["id"]
                or receipt.get("segment") != segment or receipt.get("request", {}).get("text") != segment["text"]
                or receipt.get("first_take") is not True or receipt.get("segment_call_count") != 1
                or receipt.get("acceptance") != vox.ACCEPTANCE
                or receipt.get("worker_sha256") != common.sha(vox.__file__)
                or receipt.get("helper_sha256") != vox.HELPER_SHA256
                or info["sample_rate"] != 48000 or info["clipped_samples"]):
            raise ValueError("Speech receipt, text, voice or PCM differs from the approved input")
        durations.append(info["duration_seconds"])
        checked.append({"wav": str(path), "sha256": wav_sha, "receipt": str(receipt_path), "receipt_sha256": receipt_sha})
    return durations, checked


def align(plan_path, speech, output):
    plan_path, speech, output = (Path(path).resolve() for path in (plan_path, speech, output))
    plan = common.read_json(plan_path)
    vox.validate_plan(plan)
    delivery = verify_speech_source(plan)
    state = common.read_json(speech / "state.json")
    ids = [row["id"] for row in plan["segments"]]
    if state.get("status") != vox.ACCEPTANCE or state.get("attempted") != ids or state.get("done") != ids:
        raise ValueError("Every planned first take must be generated exactly once")
    durations, inputs = speech_inputs(plan, plan_path, [
        {"wav": str(speech / f"{segment['id']}.wav"), "receipt": str(speech / f"{segment['id']}.receipt.json")}
        for segment in plan["segments"]])
    timeline = common.read_json(Path(delivery["attempt"]) / "timeline.json")
    focuses = common.read_json(plan["source"]["focuses"])
    rows = schedule(timeline, {"segments": plan["segments"]}, focuses, durations)
    result = {"plan": str(plan_path), "plan_sha256": common.sha(plan_path), "duration": timeline["duration"],
        "source": plan["source"], "segments": rows, "inputs": inputs,
        "coverage": audit_coverage(rows, focuses, timeline["duration"]),
        "writer": "Whole-utterance focus scheduler", "consumers": ["independent timing reviewer", "audio publisher"],
        "lifecycle": "This actual speech take and exact visual version", "invalidation": "Speech, text, visual focus or media change",
        "processing": "Intact measured WAVs; no speedup, trim or global video retiming"}
    output.mkdir(parents=True, exist_ok=False)
    common.write_json(output / "alignment.json", result)
    return result


def audio_bindings(alignment_path):
    value = common.read_json(alignment_path)
    if common.sha(value["plan"]) != value["plan_sha256"]:
        raise ValueError("TTS plan changed")
    plan = common.read_json(value["plan"])
    delivery = verify_speech_source(plan)
    if (value.get("source") != plan["source"] or value.get("duration") != delivery["duration"]
            or len(value.get("segments", [])) != len(plan["segments"])
            or len(value.get("inputs", [])) != len(plan["segments"])):
        raise ValueError("Alignment must retain every current planned utterance and source")
    vox.validate_plan(plan)
    durations, _ = speech_inputs(plan, value["plan"], value["inputs"])
    focus = common.read_json(value["source"]["focuses"])
    timeline = common.read_json(Path(delivery["attempt"]) / "timeline.json")
    if value["segments"] != schedule(timeline, {"segments": plan["segments"]}, focus, durations):
        raise ValueError("Stored alignment differs from actual full-utterance schedule")
    if not audit_coverage(value["segments"], focus, value["duration"])["passed"]:
        raise ValueError("Whole-utterance semantic coverage failed")
    return {"alignment_sha256": common.sha(alignment_path), "plan_sha256": value["plan_sha256"],
            "video_sha256": value["source"]["video_sha256"], "focuses_sha256": value["source"]["focuses_sha256"],
            "publisher_sha256": common.sha(__file__)}


def release_voiced(alignment_path, review_path, output):
    alignment_path, review_path, output = (Path(path).resolve() for path in (alignment_path, review_path, output))
    current = audio_bindings(alignment_path)
    review = common.read_json(review_path)
    if (review.get("status") != "pass" or review.get("stage") != "audio_alignment" or review.get("bindings") != current
            or review.get("reviewer_role") != "independent" or not review.get("reviewer_agent")
            or review.get("release_authorized") is not True or review.get("blocking_findings") != []
            or review.get("listening_reviewed") is not False):
        raise ValueError("Require current independent full-utterance timing review with honest listening limits")
    value = common.read_json(alignment_path)
    samples = array.array("h", [0]) * round(value["duration"] * 48000)
    for segment, item in zip(value["segments"], value["inputs"], strict=True):
        info, pcm = common.pcm_info(item["wav"])
        if abs(info["duration_seconds"] - segment["duration_seconds"]) > 1 / 48000:
            raise ValueError("Actual speech length changed")
        start = round(segment["start"] * 48000)
        if start < 0 or start + len(pcm) > len(samples):
            raise ValueError("Speech cannot be truncated into the visual master")
        samples[start:start + len(pcm)] = pcm
    output.mkdir(parents=True, exist_ok=False)
    raw = output / "voice-mix-raw.wav"
    if sys.byteorder != "little":
        samples.byteswap()
    with raw.open("xb") as stream, wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(samples.tobytes())
    payload, gain = common.level_payload(raw)
    mix = output / "voice-mix.wav"
    with mix.open("xb") as stream:
        stream.write(payload)
    target = output / "voiced-preview.mp4"
    pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-i", value["source"]["video"], "-i", mix,
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", str(value["duration"]), "-movflags", "+faststart", target], timeout=300)
    check_video(pilot.probe(target), value["duration"])
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", target, "-f", "null", "-"], timeout=300)
    result = {"video": str(target), "sha256": common.sha(target), "duration": value["duration"], "gain": gain,
        "bindings": current, "review": str(review_path), "review_sha256": common.sha(review_path), "full_decode_passed": True,
        "scope": "Whole-utterance-aligned voiced preview; not listening or student approval",
        "writer": "Understanding audio publisher", "consumers": ["user", "listener", "auditor"],
        "lifecycle": "This exact aligned release", "invalidation": "Media, plan, source or review change"}
    common.write_json(output / "delivery.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("bindings", "install-narration", "release-silent"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--attempt", type=Path, required=True)
        cmd.add_argument("--narration", type=Path)
        if name != "bindings":
            cmd.add_argument("--visual-review", type=Path, required=True)
            cmd.add_argument("--output", type=Path, required=True)
        if name == "install-narration":
            cmd.add_argument("--draft", type=Path, required=True)
        if name == "release-silent":
            cmd.add_argument("--narration-review", type=Path, required=True)
    cmd = commands.add_parser("speech-plan")
    for key in ("delivery", "reference", "output"):
        cmd.add_argument(f"--{key}", type=Path, required=True)
    cmd = commands.add_parser("align")
    for key in ("plan", "speech", "output"):
        cmd.add_argument(f"--{key}", type=Path, required=True)
    cmd = commands.add_parser("audio-bindings")
    cmd.add_argument("--alignment", type=Path, required=True)
    cmd = commands.add_parser("release-voiced")
    for key in ("alignment", "review", "output"):
        cmd.add_argument(f"--{key}", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "bindings":
        result = bindings(args.attempt, args.narration)
    elif args.command == "install-narration":
        result = install_narration(args.attempt, args.draft, args.visual_review, args.output)
    elif args.command == "release-silent":
        if args.narration is None:
            parser.error("release-silent requires --narration")
        result = release_silent(args.attempt, args.narration, args.visual_review, args.narration_review, args.output)
    elif args.command == "speech-plan":
        result = speech_plan(args.delivery, args.reference, args.output)
    elif args.command == "align":
        result = align(args.plan, args.speech, args.output)
    elif args.command == "audio-bindings":
        result = audio_bindings(args.alignment)
    else:
        result = release_voiced(args.alignment, args.review, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
