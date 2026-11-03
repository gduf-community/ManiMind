"""Add selected local speech to an approved visual master without retiming it.

Plans are long-lived project inputs. Alignment is immutable per speech attempt;
an independent, hash-bound timing review is required before mixing or muxing.
This gate is not listening approval or classroom certification.
"""

from __future__ import annotations

import argparse
import array
import json
import math
from pathlib import Path
import sys
import wave

from . import pilot, preset_audition as common, voxcpm_audition as vox


def approved_source(config):
    from manimind.experiments.sol_visual_first import SolVisualFirst

    production = SolVisualFirst(Path(config))
    production.team = pilot.read_json(production.team_path)
    production.verify()
    production.approval("visual")
    production.approval("narration")
    delivery_path = production.out / "delivery.json"
    delivery = pilot.read_json(delivery_path)
    video = Path(delivery["video"])
    narration = production.out / "narration-plan.json"
    if pilot.sha256(video) != delivery["sha256"] or pilot.sha256(narration) != delivery["narration_sha256"]:
        raise ValueError("Approved visual master or narration has changed")
    if [stream["codec_type"] for stream in pilot.probe(video)["streams"]] != ["video"]:
        raise ValueError("Expected a silent, subtitle-free visual master")
    source = {"config": str(Path(config).resolve()), "delivery": str(delivery_path),
              "delivery_sha256": pilot.sha256(delivery_path), "video": str(video),
              "video_sha256": delivery["sha256"], "narration_sha256": delivery["narration_sha256"]}
    return source, pilot.read_json(narration), pilot.read_json(production.out / "timeline.json")


def prepare(config, reference, output):
    reference, output = Path(reference).resolve(), Path(output).resolve()
    source, narration, _ = approved_source(config)
    receipt = common.read_json(reference.with_suffix(".receipt.json"))
    measured, _ = common.pcm_info(reference)
    if (receipt.get("wav_sha256") != common.sha(reference)
            or receipt.get("engine", {}).get("model") != vox.MODEL
            or receipt.get("request", {}).get("text") != vox.TEXT or measured["sample_rate"] != 48000):
        raise ValueError("Reference must be the selected, traceable synthetic VoxCPM audition")
    plan = {"schema_version": 1, "reference_sha256": common.sha(reference), "reference_text": vox.TEXT,
            "reference_source": str(reference), "source": source,
            "generation": {"seed": 42, "cfg_value": 2.0, "inference_timesteps": 10,
                           "normalize": False, "denoise": False, "retry_badcase": False},
            "segments": [{"id": f"N{index:02d}", **row} for index, row in enumerate(narration["segments"], 1)],
            "writer": "Approved visual narration adapter", "consumers": ["speech worker", "aligner", "reviewer"],
            "lifecycle": "Selected voice for this approved visual/text version",
            "invalidation": "Voice selection, reference, model, text or visual source changes",
            "authorization": "User selected audition 1 and requested a complete voiced viewing preview"}
    output.parent.mkdir(parents=True, exist_ok=True)
    common.write_json(output, plan)
    return plan


def schedule(timeline, segments, durations, gap=.25):
    if not math.isfinite(gap) or gap < .15:
        raise ValueError("A finite, audible inter-sentence gap is required")
    cues = {cue["id"]: cue for cue in timeline["cues"]}
    if len(segments) != len(durations):
        raise ValueError("Every approved sentence needs exactly one measured audio duration")
    previous, rows = 0.0, []
    for segment, duration in zip(segments, durations, strict=True):
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Invalid actual speech duration")
        cue = cues[segment["cue"]]
        anchor = segment["anchor_time"]
        if not math.isfinite(anchor) or not cue["start"] <= anchor < cue["start"] + cue["duration"]:
            raise ValueError("Speech anchor is outside its visual cue")
        earliest = max(cue["start"] + .12, previous + gap)
        relation = segment["relation"]
        if relation == "after":
            start = max(earliest, anchor + .04)
        elif relation == "before":
            start = earliest
        elif relation == "during":
            start = max(earliest, anchor - duration / 2)
        else:
            raise ValueError("Unknown semantic relation")
        start = math.ceil(start * 48000) / 48000
        end = start + duration
        if (end > cue["start"] + cue["duration"] + 1 / 48000
                or relation == "before" and end > anchor - .04
                or relation == "during" and not start <= anchor <= end):
            raise ValueError(f"{segment['id']} cannot fit its unchanged visual event; no automatic speedup or trimming")
        rows.append({**segment, "start": start, "end": end, "duration_seconds": duration})
        previous = end
    return rows


def align(plan_path, speech, output):
    plan_path, speech, output = (Path(path).resolve() for path in (plan_path, speech, output))
    plan = common.read_json(plan_path)
    source, original, timeline = approved_source(plan["source"]["config"])
    if (source != plan["source"] or plan["segments"] != [
            {"id": f"N{index:02d}", **row} for index, row in enumerate(original["segments"], 1)]):
        raise ValueError("Frozen approved source/text differs from the TTS plan")
    ids = [row["id"] for row in plan["segments"]]
    state = common.read_json(speech / "state.json")
    if (state.get("done") != ids or state.get("attempted") != ids
            or state.get("status") != "generated_not_listening_or_alignment_approved"):
        raise ValueError("Require every original speech segment completed once")
    durations, inputs = [], []
    for segment in plan["segments"]:
        wav = speech / f"{segment['id']}.wav"
        receipt_path = wav.with_suffix(".receipt.json")
        record = common.read_json(receipt_path)
        info, _ = common.pcm_info(wav)
        if (record.get("id") != segment["id"] or record.get("request", {}).get("text") != segment["text"]
                or record.get("reference_sha256") != plan["reference_sha256"]
                or record.get("plan_sha256") != common.sha(plan_path)
                or record.get("wav_sha256") != common.sha(wav)
                or info["sample_rate"] != 48000 or info["clipped_samples"]):
            raise ValueError("Speech media, selected voice or approved text differs from its receipt")
        durations.append(info["duration_seconds"])
        inputs.append({"wav": str(wav), "sha256": common.sha(wav),
                       "receipt": str(receipt_path), "receipt_sha256": common.sha(receipt_path)})
    rows = schedule(timeline, plan["segments"], durations)
    result = {"schema_version": 1, "source": source, "plan": str(plan_path), "plan_sha256": common.sha(plan_path),
              "duration": timeline["duration"], "segments": rows, "inputs": inputs,
              "processing": "No trims, speed changes, visual retiming or text changes; measured full clips plus silence",
              "writer": "Visual narration timing adapter", "consumers": ["independent reviewer", "mixer"],
              "lifecycle": "This speech attempt and unchanged visual master",
              "invalidation": "Any speech, receipt, plan, source or timing change"}
    output.mkdir(parents=True, exist_ok=False)
    common.write_json(output / "alignment.json", result)
    return result


def release(alignment_path, review_path):
    alignment_path, review_path = Path(alignment_path).resolve(), Path(review_path).resolve()
    value, review = common.read_json(alignment_path), common.read_json(review_path)
    expected = {"alignment_sha256": common.sha(alignment_path), "plan_sha256": value["plan_sha256"],
                "video_sha256": value["source"]["video_sha256"]}
    if (review.get("status") != "pass" or review.get("bindings") != expected
            or review.get("reviewer_role") != "independent" or not review.get("reviewer_agent")
            or review.get("listening_reviewed") is not False):
        raise ValueError("A current independent timing review with honest listening limits is required")
    source, _, _ = approved_source(value["source"]["config"])
    if source != value["source"] or common.sha(value["plan"]) != value["plan_sha256"]:
        raise ValueError("Visual or narration source changed after timing review")
    if (len(value["segments"]) != len(value["inputs"]) or not value["segments"]):
        raise ValueError("Incomplete speech alignment")
    directory = alignment_path.parent
    playback = directory / "playback"
    if playback.exists():
        raise FileExistsError("Existing voiced export is never overwritten")
    rate = 48000
    samples = array.array("h", [0]) * round(value["duration"] * rate)
    for segment, item in zip(value["segments"], value["inputs"], strict=True):
        path, receipt = Path(item["wav"]), Path(item["receipt"])
        if common.sha(path) != item["sha256"] or common.sha(receipt) != item["receipt_sha256"]:
            raise ValueError("Reviewed speech changed")
        info, pcm = common.pcm_info(path)
        if abs(info["duration_seconds"] - segment["duration_seconds"]) > 1 / rate:
            raise ValueError("Reviewed speech duration changed")
        start = round(segment["start"] * rate)
        stop = start + len(pcm)
        if start < 0 or stop > len(samples) or any(samples[start:stop]):
            raise ValueError("Overlapping or truncated voice samples")
        samples[start:stop] = pcm
    raw_mix = directory / "voice-mix-raw.wav"
    if sys.byteorder != "little":
        samples.byteswap()
    with raw_mix.open("xb") as stream, wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(samples.tobytes())
    gain_payload, gain = common.level_payload(raw_mix)
    mix = directory / "voice-mix.wav"
    with mix.open("xb") as stream:
        stream.write(gain_payload)
    support = directory / "support"
    support.mkdir()
    subtitles = support / "narration.srt"
    with subtitles.open("x", encoding="utf-8") as stream:
        stream.write("\n\n".join(f"{index}\n{pilot.srt_time(row['start'])} --> {pilot.srt_time(row['end'])}\n{row['text']}"
                                 for index, row in enumerate(value["segments"], 1)) + "\n")
    playback.mkdir()
    video = playback / "projectile-vox-v01.mp4"
    command = [pilot.FFMPEG, "-v", "error", "-n", "-i", source["video"], "-i", mix,
               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-t", str(value["duration"]), "-movflags", "+faststart", video]
    pilot.run(command, timeout=180)
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", video, "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], timeout=180)
    original_hash = pilot.run([pilot.FFMPEG, "-v", "error", "-i", source["video"], "-map", "0:v:0", "-c", "copy", "-f", "hash", "-hash", "sha256", "-"])
    export_hash = pilot.run([pilot.FFMPEG, "-v", "error", "-i", video, "-map", "0:v:0", "-c", "copy", "-f", "hash", "-hash", "sha256", "-"])
    metadata = pilot.probe(video)
    if original_hash != export_hash or sorted(row["codec_type"] for row in metadata["streams"]) != ["audio", "video"]:
        raise ValueError("Voiced export changed visual packets or stream layout")
    if abs(float(metadata["format"]["duration"]) - value["duration"]) > .1:
        raise ValueError("Voiced export duration changed")
    result = {"video": str(video), "sha256": common.sha(video), "duration": value["duration"], "streams": metadata["streams"],
              "review": str(review_path), "review_sha256": common.sha(review_path), "bindings": expected,
              "video_packets_unchanged": True, "full_decode_passed": True, "voice_gain": gain,
              "subtitle_policy": "No embedded, burned or auto-loaded captions; optional SRT in separate support directory",
              "scope": "Complete voiced viewing preview, not classroom or listening certification",
              "limitations": ["No human listening review or student comprehension test", "Selected synthetic reference conditions voice; not a guaranteed timbre identity score"],
              "writer": "Reviewed visual narration release adapter", "consumers": ["user", "auditor"],
              "lifecycle": "This exact preview and review", "invalidation": "Any bound media, text, model or review changes"}
    common.write_json(directory / "delivery.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_command = sub.add_parser("prepare")
    prepare_command.add_argument("--config", type=Path, required=True)
    prepare_command.add_argument("--reference", type=Path, required=True)
    prepare_command.add_argument("--output", type=Path, required=True)
    align_command = sub.add_parser("align")
    align_command.add_argument("--plan", type=Path, required=True)
    align_command.add_argument("--speech", type=Path, required=True)
    align_command.add_argument("--output", type=Path, required=True)
    release_command = sub.add_parser("release")
    release_command.add_argument("--alignment", type=Path, required=True)
    release_command.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        value = prepare(args.config, args.reference, args.output)
        print(json.dumps({"segments": len(value["segments"]), "plan": str(args.output)}))
    elif args.command == "align":
        value = align(args.plan, args.speech, args.output)
        print(json.dumps({"segments": len(value["segments"]), "duration": value["duration"]}))
    else:
        print(json.dumps(release(args.alignment, args.review), ensure_ascii=False))


if __name__ == "__main__":
    main()
