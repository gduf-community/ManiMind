"""Assemble only an independently approved, hash-bound comparison edit."""

import argparse
from pathlib import Path

from manimind.postproduce import pilot


def validate(plan_path, review_path):
    plan = pilot.read_json(plan_path)
    review = pilot.read_json(review_path)
    if (review.get("status") != "approved" or review.get("blockers") != []
            or review.get("reviewer_role") != "reviewer"
            or not review.get("reviewer_id")
            or review.get("scope") != plan.get("scope", "experimental_comparison_edit")
            or review.get("scope") not in {"experimental_comparison_edit", "experimental_diagnostic_edit"}
            or review.get("plan_sha256") != pilot.sha256(plan_path)):
        raise ValueError("Independent comparison-edit approval required")
    if review.get("implementation_sha256") != pilot.sha256(Path(__file__)):
        raise ValueError("Comparison assembler changed after review")
    for part in plan["parts"]:
        source = Path(part["source"])
        if pilot.sha256(source) != part["sha256"]:
            raise ValueError("Reviewed comparison source changed")
        if part["kind"] not in {"card", "lesson", "diagnostic"} or part["seconds"] <= 0:
            raise ValueError("Invalid comparison part")
        if part["kind"] == "diagnostic":
            if review["scope"] != "experimental_diagnostic_edit":
                raise ValueError("Diagnostic samples require separate diagnostic-edit approval")
            for key in ("audio", "warning", "media_review", "component_review", "score"):
                if pilot.sha256(Path(part[key])) != part[f"{key}_sha256"]:
                    raise ValueError("Diagnostic source, warning or rejected verdict changed")
            verdict = pilot.read_json(Path(part["media_review"]))
            if (verdict["status"] != part["candidate_quality_status"]
                    or verdict["hashes"]["video"] != part["sha256"]
                    or verdict["hashes"]["audio"] != part["audio_sha256"]
                    or not part["disclaimer"]):
                raise ValueError("Diagnostic edit must retain the original candidate verdict")
            source_info = pilot.probe(source)
            video = next(s for s in source_info["streams"] if s["codec_type"] == "video")
            audio_info = pilot.probe(Path(part["audio"]))
            if (abs(float(video["duration"]) - part["seconds"]) > .05
                    or abs(float(audio_info["format"]["duration"]) - part["seconds"]) > .05
                    or [video["width"], video["height"]] != [1920, 1080]
                    or video["avg_frame_rate"] != "30/1"):
                raise ValueError("Diagnostic source must be the full native 1080p30 sample")
        if part["kind"] == "lesson":
            delivery_path = source.with_name("delivery.json")
            if pilot.sha256(delivery_path) != part["delivery_sha256"]:
                raise ValueError("Source delivery approval changed")
            delivery = pilot.read_json(delivery_path)
            if delivery["sha256"] != part["sha256"]:
                raise ValueError("Comparison source is not the approved lesson")
            for path, sha in delivery["approval_sources"].items():
                if pilot.sha256(Path(path)) != sha:
                    raise ValueError("Source lesson approval evidence changed")
            metadata = pilot.probe(source)
            video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
            if (abs(float(video["duration"]) - part["seconds"]) > .05
                    or [video["width"], video["height"]] != [1920, 1080]
                    or video["avg_frame_rate"] != "30/1"):
                raise ValueError("Source lesson timing or dimensions differ")
    return plan


def assemble(plan_path, review_path):
    plan = validate(plan_path, review_path)
    out = plan_path.parent
    diagnostic = plan.get("scope") == "experimental_diagnostic_edit"
    name = "diagnostic-comparison" if diagnostic else "comparison"
    destination = out / f"{name}.mp4"
    pending = out / f"{name}-pending.mp4"
    if destination.exists() or pending.exists():
        raise ValueError("Comparison delivery is immutable")
    inputs = []
    streams = []
    input_index = 0
    for index, part in enumerate(plan["parts"]):
        warning_index = None
        video_index = input_index
        if part["kind"] == "card":
            inputs += ["-loop", "1", "-framerate", "30", "-t", str(part["seconds"]),
                       "-i", part["source"]]
            inputs += ["-f", "lavfi", "-t", str(part["seconds"]),
                       "-i", "anullsrc=r=48000:cl=mono"]
            audio_index = input_index + 1
            input_index += 2
        elif part["kind"] == "diagnostic":
            inputs += ["-i", part["source"], "-i", part["audio"],
                       "-loop", "1", "-framerate", "30", "-t", str(part["seconds"]),
                       "-i", part["warning"]]
            audio_index, warning_index = input_index + 1, input_index + 2
            input_index += 3
        else:
            inputs += ["-i", part["source"]]
            audio_index = input_index
            input_index += 1
        streams.append((video_index, audio_index, warning_index))
    filters = []
    for index, (video, audio, warning) in enumerate(streams):
        if warning is None:
            filters.append(f"[{video}:v:0]setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{index}]")
        else:
            filters += [
                f"[{video}:v:0]setpts=PTS-STARTPTS,setsar=1[raw{index}]",
                f"[raw{index}][{warning}:v:0]overlay=0:0:shortest=1,format=yuv420p[v{index}]"]
        filters.append(f"[{audio}:a:0]asetpts=PTS-STARTPTS,aresample=48000[a{index}]")
    chain = "".join(f"[v{i}][a{i}]" for i in range(len(streams)))
    filters.append(f"{chain}concat=n={len(streams)}:v=1:a=1[v][a]")
    pilot.run([pilot.FFMPEG, "-v", "error", "-n", *inputs,
               "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", "30",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
               "-movflags", "+faststart", pending], timeout=900)
    metadata = pilot.probe(pending)
    expected = sum(part["seconds"] for part in plan["parts"])
    if abs(float(metadata["format"]["duration"]) - expected) > .1:
        raise ValueError("Comparison duration differs; preserve pending evidence")
    pilot.run([pilot.FFMPEG, "-v", "error", "-i", pending, "-f", "null", "-"], timeout=300)
    validate(plan_path, review_path)
    pending.rename(destination)
    pilot.write_json(out / "delivery.json", {
        "scope": plan.get("scope", "experimental_comparison_edit"), "video": str(destination),
        "sha256": pilot.sha256(destination), "seconds": expected,
        "plan_sha256": pilot.sha256(plan_path), "review_sha256": pilot.sha256(review_path),
        "implementation_sha256": pilot.sha256(Path(__file__)),
        "limitations": ["Full sources are re-encoded without trimming, scaling or speed changes.",
                        "Diagnostic samples retain rejected quality verdicts and have persistent warning overlays.",
                        "Narration subtitles remain separate evidence files; the montage has no soft-subtitle track.",
                        "No claim of a completed video for failed candidates or school readiness."]})
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    args = parser.parse_args()
    print(assemble(args.plan, args.review))


if __name__ == "__main__":
    main()
