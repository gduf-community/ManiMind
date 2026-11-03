"""Supervised free-form scenes with measured speech and independent release review.

This path does not impose a shot layout, a subject template, or an animation
count. It executes inspected local scene code, not untrusted remote code in a
sandbox. Existing comparison protocols and their frozen helpers are untouched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from pathlib import Path
import re
import shutil
import wave

from . import pilot
from ..components.catalog import FONT_PATH, NUMBER_FONT_PATH
from ..render import manim_renderer
from ..render.manim_renderer import extract_keyframes, render_manim_scene

ROOT = pilot.ROOT
read_json, write_json, sha256 = pilot.read_json, pilot.write_json, pilot.sha256


def validate_spec(spec: dict) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", spec.get("project_id", "")):
        raise ValueError("Invalid project_id")
    if type(spec.get("fps")) is not int or spec["fps"] <= 0:
        raise ValueError("fps must be a positive integer")
    cues = spec.get("cues")
    if not isinstance(cues, list) or not cues:
        raise ValueError("At least one narration cue is required")
    ids = []
    for cue in cues:
        if not isinstance(cue, dict):
            raise ValueError("Cue must be an object")
        name = cue.get("id", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError("Cue id must be a safe asset name")
        ids.append(name)
        if not isinstance(cue.get("spoken"), str) or not cue["spoken"].strip():
            raise ValueError("Narration text is required")
        if (not isinstance(cue.get("subtitle_lines"), list)
                or not all(isinstance(s, str) for s in cue["subtitle_lines"])):
            raise ValueError("subtitle_lines must be a list of strings")
        for key, default in (("min_duration", 0), ("lead_in", .3), ("tail", .65)):
            value = cue.get(key, default)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid cue timing: {key}")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate cue ids")
    for key in ("video_name", "subtitle_name"):
        value = spec.get(key)
        if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
            raise ValueError(f"{key} must be a plain file name")


def cue_seconds(cue: dict, speech_seconds: float, fps: int) -> float:
    if (type(speech_seconds) not in (int, float) or not math.isfinite(speech_seconds)
            or speech_seconds <= 0 or type(fps) is not int or fps <= 0):
        raise ValueError("Positive finite speech duration and integer fps are required")
    return math.ceil(max(cue.get("min_duration", 0),
                         speech_seconds + cue.get("lead_in", .3)
                         + cue.get("tail", .65)) * fps) / fps


def require_coverage(review: dict, evidence: dict) -> None:
    inspected = set(review["inspected_frames"])
    covered = {frame["cue"] for frame in evidence["frames"] if frame["path"] in inspected}
    if covered != set(evidence["cue_ids"]):
        raise ValueError("Every cue requires independent inspection of actual pixels")
    if review.get("approval_scope") != "supervised_preview":
        raise ValueError("Explicit preview approval scope is required")
    if not isinstance(review.get("limitations"), list):
        raise ValueError("Review must explicitly record its evidence limits")


def subtitle_segments(cue: dict) -> list[dict]:
    """Hold only the current spoken sentence, never the whole cue's conclusion."""
    end = cue["start"] + cue["duration"]
    spans = cue.get("spoken_spans")
    if not spans:
        return [{"start": cue["speech_start"], "end": end,
                 "text": "\n".join(cue["subtitle_lines"])}]
    segments = []
    for i, span in enumerate(spans):
        start = span["start"]
        stop = spans[i + 1]["start"] if i + 1 < len(spans) else end
        if not cue["start"] <= start < stop <= end + .001:
            raise ValueError("Subtitle sentence boundaries must be ordered inside the cue")
        segments.append({"start": start, "end": stop, "text": span["text"]})
    return segments


class Production:
    def __init__(self, spec_path: Path):
        self.spec_path = spec_path.resolve()
        self.spec = read_json(self.spec_path)
        validate_spec(self.spec)
        self.id = self.spec["project_id"]
        self.out = ROOT / "outputs" / self.id
        self.context = ROOT / "runtime/projects" / self.id
        self.session = ROOT / "runtime/sessions" / f"{self.id}-production"
        self.source = self.local_path(self.spec["scene"])
        self.config = self.local_path(self.spec["render_config"])

    @staticmethod
    def local_path(value: str) -> Path:
        path = (ROOT / value).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("Production source must be inside the repository")
        return path

    def event(self, phase: str, **data) -> None:
        self.session.mkdir(parents=True, exist_ok=True)
        with (self.session / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"phase": phase, **data}, ensure_ascii=False) + "\n")

    async def prepare(self, provider: str) -> None:
        if provider not in {"edge", "say"}:
            raise ValueError("Explicit TTS provider is required")
        audio_dir = self.out / "audio"
        if (self.out / "render.json").is_file() and audio_dir.is_dir():
            number = len(list(self.session.glob("before-prepare-*"))) + 1
            archive = self.session / f"before-prepare-{number:03d}"
            shutil.copytree(audio_dir, archive / "audio")
            for name in ("timeline.json", "render.json", "review-input.json"):
                path = self.out / name
                if path.exists():
                    shutil.copy2(path, archive / name)
            self.event("prior_audio_archived", archive=str(archive))
        audio_dir.mkdir(parents=True, exist_ok=True)
        cues, cursor = [], 0.0
        for index, cue in enumerate(self.spec["cues"], 1):
            stem = f"{index:02d}-{cue['id']}"
            audio_source = audio_dir / f"{stem}.{'mp3' if provider == 'edge' else 'aiff'}"
            metadata = audio_dir / f"{stem}-sentences.jsonl"
            stamp = audio_dir / f"{stem}.json"
            cache = {"provider": provider, "spoken": cue["spoken"],
                     "voice": self.spec["voice"] if provider == "edge" else "Tingting",
                     "rate": self.spec.get("speech_rate", "+0%") if provider == "edge" else "230",
                     "boundary": "SentenceBoundary" if provider == "edge" else None}
            if not (audio_source.is_file() and stamp.is_file() and read_json(stamp) == cache
                    and (provider != "edge" or metadata.is_file())):
                if provider == "edge":
                    import edge_tts
                    await asyncio.wait_for(edge_tts.Communicate(
                        cache["spoken"], cache["voice"], rate=cache["rate"]
                    ).save(str(audio_source), str(metadata)), timeout=90)
                else:
                    pilot.run(["say", "-v", cache["voice"], "-r", cache["rate"],
                               "-o", audio_source, cache["spoken"]])
                write_json(stamp, cache)
            raw = audio_dir / f"{stem}-raw.wav"
            pilot.run([pilot.FFMPEG, "-v", "error", "-y", "-i", audio_source,
                       "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", raw])
            with wave.open(str(raw), "rb") as wav:
                seconds = wav.getnframes() / wav.getframerate()
            duration = cue_seconds(cue, seconds, self.spec["fps"])
            padded = audio_dir / f"{stem}.wav"
            lead = cue.get("lead_in", .3)
            pilot.run([pilot.FFMPEG, "-v", "error", "-y", "-i", raw, "-af",
                       f"adelay={round(1000 * lead)},apad", "-t", f"{duration:.9f}",
                       "-c:a", "pcm_s16le", padded])
            spans = []
            if provider == "edge":
                for line in metadata.read_text(encoding="utf-8").splitlines():
                    part = json.loads(line)
                    if part["type"] == "SentenceBoundary":
                        start = cursor + lead + part["offset"] / 10_000_000
                        spans.append({"text": part["text"], "start": round(start, 6),
                                      "end": round(start + part["duration"] / 10_000_000, 6)})
            cues.append({**cue, "start": round(cursor, 9), "duration": duration,
                         "speech_start": round(cursor + lead, 9), "audio_duration": seconds,
                         "text": "".join(cue["subtitle_lines"]), "audio_path": str(padded),
                         "spoken_spans": spans})
            cursor += duration
            print(f"{stem}: speech={seconds:.2f}s, cue={duration:.2f}s", flush=True)
        write_json(self.out / "timeline.json", {
            "project_id": self.id, "fps": self.spec["fps"], "provider": provider,
            "voice": cache["voice"], "spec_sha256": sha256(self.spec_path),
            "duration": round(cursor, 9), "cues": cues})
        with wave.open(str(audio_dir / "narration.wav"), "wb") as output:
            output.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            for cue in cues:
                with wave.open(cue["audio_path"], "rb") as wav:
                    output.writeframes(wav.readframes(wav.getnframes()))
        write_json(self.context / "production-context.json", {
            "scope": "long_term", "writer_role": "coordinator",
            "consumer_roles": ["manim_worker", "reviewer", "lead"],
            "lifecycle": "This supervised pilot project",
            "invalidation_rule": "Any source, facts, narration, dependency, timeline or media change invalidates approval.",
            "spec": self.spec, "spec_sha256": sha256(self.spec_path),
            "paper_summary": {"type": "textbook model and animation case study",
                              "research": "docs/research/learning-video-20261020/07-animation-vs-knowledge.md",
                              "facts": self.spec["facts"]},
            "ownership": {"visuals": "separate Manim worker", "production": "lead/coordinator",
                          "approval": "independent reviewer"},
            "html_segments": [], "manim_segments": [self.spec["scene_class"]],
            "script": str(self.spec_path), "storyboard": self.spec["cues"],
            "tasks": [{"owner": "manim_worker", "output": str(self.source)},
                      {"owner": "reviewer", "output": str(self.context / "review.json")}],
            "benchmark": False})
        write_json(self.session / "session.json", {
            "scope": "short_term", "writer_role": "coordinator",
            "consumer_roles": ["lead", "reviewer"],
            "lifecycle": "This production session",
            "invalidation_rule": "Events remain historical; a new render supersedes current evidence.",
            "project": self.id})
        self.event("audio_prepared", duration=cursor, provider=provider)

    def input_hashes(self) -> dict:
        timeline = read_json(self.out / "timeline.json")
        if timeline["spec_sha256"] != sha256(self.spec_path):
            raise ValueError("Narration is stale; prepare again")
        paths = {"source": self.source, "spec": self.spec_path,
                 "timeline": self.out / "timeline.json", "config": self.config,
                 "narration": self.out / "audio/narration.wav",
                 "producer": Path(__file__), "pilot_helpers": Path(pilot.__file__),
                 "render_helpers": Path(manim_renderer.__file__),
                 "font": FONT_PATH, "number_font": NUMBER_FONT_PATH}
        for i, path in enumerate(self.spec.get("dependencies", [])):
            paths[f"dependency_{i}"] = self.local_path(path)
        return {name: sha256(path) for name, path in paths.items()}

    def hashes(self, video: Path) -> dict:
        paths = {"video": video, "audio": self.out / "audio/mix.wav",
                 "audio_report": self.out / "audio/report.json"}
        for name in ("sound-events", "science-samples"):
            path = self.out / f"{name}.json"
            if path.exists():
                paths[name] = path
        return {**self.input_hashes(), **{name: sha256(path) for name, path in paths.items()}}

    def render(self, quality: str, allow_local_code: bool) -> None:
        if not allow_local_code:
            raise ValueError("Read the local scene first; render requires --allow-local-code")
        before = self.input_hashes()
        version = len(list(self.session.glob("render-*.json"))) + 1
        for name in ("sound-events.json", "science-samples.json"):
            path = self.out / name
            if path.exists():
                shutil.copy2(path, self.session / f"before-render-{version:03d}-{name}")
                path.unlink()
        result = render_manim_scene(
            segment_id=f"story-v{version:03d}-{quality}",
            scene_code=self.source.read_text(encoding="utf-8"),
            scene_class_name=self.spec["scene_class"], output_dir=self.out,
            config_file=self.config, quality=quality, timeout_seconds=2400)
        self.session.mkdir(parents=True, exist_ok=True)
        write_json(self.session / f"render-{version:03d}.json", result.to_dict())
        if not result.success:
            raise RuntimeError(result.to_dict())
        if before != self.input_hashes() or sha256(Path(result.code_path)) != before["source"]:
            raise ValueError("Inputs changed during render")
        write_json(self.out / "render.json", {**result.to_dict(), "input_hashes": before,
                                             "version": version})
        self.event("rendered", version=version, video=result.video_path)
        print(result.video_path, flush=True)

    def prepare_mix(self) -> None:
        import numpy as np
        with wave.open(str(self.out / "audio/narration.wav"), "rb") as wav:
            narration = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(float) / 32768
        signal = narration.copy()
        events_path = self.out / "sound-events.json"
        events = read_json(events_path)["events"] if events_path.exists() else []
        for event in events:
            time, kind = event["time"], event["kind"]
            if type(time) not in (float, int) or not 0 <= time < len(signal) / 48000:
                raise ValueError("Invalid sound event time")
            frequencies = {"launch": 420, "land": 110, "success": 660, "fail": 155, "reveal": 520}
            if kind not in frequencies:
                raise ValueError(f"Unsupported sound event: {kind}")
            duration = .32 if kind == "success" else .18
            t = np.arange(round(duration * 48000)) / 48000
            frequency = frequencies[kind]
            phase = 2 * np.pi * (frequency * t + (600 * t * t if kind == "launch" else 0))
            tone = np.sin(phase)
            if kind in {"success", "reveal"}:
                tone = .65 * tone + .35 * np.sin(2 * np.pi * frequency * 1.5 * t)
            envelope = np.minimum(t / .015, 1) * np.exp(-t * 16)
            pulse = .045 * tone * envelope
            start = round(time * 48000)
            end = min(start + len(pulse), len(signal))
            signal[start:end] += pulse[:end - start]
        peak = float(np.max(np.abs(signal)))
        if peak >= .98:
            signal *= .95 / peak
        with wave.open(str(self.out / "audio/mix.wav"), "wb") as wav:
            wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            wav.writeframes((signal * 32767).astype("<i2").tobytes())
        timeline = read_json(self.out / "timeline.json")
        levels = []
        for cue in timeline["cues"]:
            a = round(cue["speech_start"] * 48000)
            b = round((cue["speech_start"] + cue["audio_duration"]) * 48000)
            rms = float(np.sqrt(np.mean(narration[a:b] ** 2)))
            if rms <= .0001:
                raise ValueError(f"Silent narration cue: {cue['id']}")
            levels.append({"cue": cue["id"], "rms": rms, "seconds": cue["audio_duration"]})
        write_json(self.out / "audio/report.json", {
            "duration": len(signal) / 48000, "peak": float(np.max(np.abs(signal))),
            "events": events, "cue_levels": levels,
            "sound_origin": "Original deterministic short synthesized event tones; no borrowed music.",
            "limitations": ["Technical signal checks do not replace listening or student comprehension testing."]})

    def inspect(self) -> None:
        from PIL import Image, ImageDraw
        rendered = read_json(self.out / "render.json")
        if rendered["input_hashes"] != self.input_hashes():
            raise ValueError("Render is stale")
        video = Path(rendered["video_path"])
        timeline = read_json(self.out / "timeline.json")
        stream = next(s for s in pilot.probe(video)["streams"] if s["codec_type"] == "video")
        duration = float(stream["duration"])
        if abs(duration - timeline["duration"]) > .15:
            raise ValueError(f"Timeline drift: {duration} vs {timeline['duration']}")
        self.prepare_mix()
        requests = [(cue["id"], round(cue["start"] + cue["duration"] * f, 3))
                    for cue in timeline["cues"] for f in (.18, .43, .70, .94)]
        frame_dir = self.out / f"frames-v{rendered['version']:03d}"
        extracted = extract_keyframes(video_path=video, output_dir=frame_dir,
                                     timestamps=[t for _, t in requests], ffmpeg_executable=pilot.FFMPEG)
        if not extracted.success or len(extracted.frame_paths) != len(requests):
            raise ValueError("Incomplete frame extraction")
        frames = [{"cue": cue, "time": time, "path": name, "sha256": sha256(Path(name))}
                  for (cue, time), name in zip(requests, extracted.frame_paths)]
        sheets = []
        for start in range(0, len(frames), 8):
            sheet = Image.new("RGB", (1920, 4 * 568), "#202226")
            draw = ImageDraw.Draw(sheet)
            for i, record in enumerate(frames[start:start + 8]):
                with Image.open(record["path"]) as frame:
                    frame.thumbnail((960, 540))
                    x, y = i % 2 * 960, i // 2 * 568
                    sheet.paste(frame, (x, y + 25))
                    draw.text((x + 8, y + 6), f"{record['cue']} / {record['time']:.2f}s", fill="white")
            path = frame_dir / f"contact-{start // 8 + 1:02d}.jpg"
            sheet.save(path, quality=95)
            sheets.append(str(path))
        evidence = {"project_id": self.id, "hashes": self.hashes(video),
                    "video_path": str(video), "audio_path": str(self.out / "audio/mix.wav"),
                    "source_path": str(self.source), "timeline_path": str(self.out / "timeline.json"),
                    "duration": duration, "resolution": [stream["width"], stream["height"]],
                    "frames": frames, "contact_sheets": sheets,
                    "cue_ids": [c["id"] for c in timeline["cues"]],
                    "required_checks": ["mathematics", "visual_layout", "narrative", "cue_timing"],
                    "instruction": "Independent pixel inspection for every cue plus facts/source/time/audio evidence. Record evidence limits; no self-approval or classroom-effect claim."}
        write_json(self.out / "review-input.json", evidence)
        self.event("evidence_ready", version=rendered["version"], frames=len(frames))
        print(json.dumps({"duration": duration, "resolution": evidence["resolution"],
                          "contact_sheets": sheets}, ensure_ascii=False), flush=True)

    def assemble(self) -> None:
        evidence = read_json(self.out / "review-input.json")
        review_path = self.context / "review.json"
        review = read_json(review_path)
        video = Path(evidence["video_path"])
        current = self.hashes(video)
        if current != evidence["hashes"]:
            raise ValueError("Review evidence is stale")
        pilot.validate_review(review, current, evidence["frames"], require_zoom=False)
        require_coverage(review, evidence)
        timeline = read_json(self.out / "timeline.json")
        final = self.out / self.spec.get("video_name", "projectile-story.mp4")
        pilot.run([pilot.FFMPEG, "-v", "error", "-y", "-i", video, "-i", self.out / "audio/mix.wav",
                   "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                   "-af", "loudnorm=I=-18:TP=-1.5:LRA=7", "-t", str(timeline["duration"]),
                   "-movflags", "+faststart", final])
        streams = pilot.probe(final)["streams"]
        vs = next(s for s in streams if s["codec_type"] == "video")
        audio = next(s for s in streams if s["codec_type"] == "audio")
        if abs(float(vs["duration"]) - float(audio["duration"])) > .15:
            raise ValueError("Final audio/video durations disagree")
        pilot.run([pilot.FFMPEG, "-v", "error", "-i", final, "-f", "null", "-"], timeout=300)
        segments = [s for cue in timeline["cues"] for s in subtitle_segments(cue)]
        subtitles = [f"{i}\n{pilot.srt_time(s['start'])} --> {pilot.srt_time(s['end'])}\n{s['text']}"
                     for i, s in enumerate(segments, 1)]
        (self.out / self.spec.get("subtitle_name", "projectile-story.srt")).write_text(
            "\n\n".join(subtitles) + "\n", encoding="utf-8")
        write_json(self.out / "delivery.json", {
            "video": str(final), "sha256": sha256(final), "duration": float(vs["duration"]),
            "resolution": [vs["width"], vs["height"]], "fps": vs["avg_frame_rate"],
            "voice": timeline["voice"], "review": str(review_path), "review_sha256": sha256(review_path),
            "hashes": current, "full_decode_passed": True,
            "assets": {"scene": str(self.source), "script": str(self.spec_path),
                       "storyboard": str(self.spec_path), "timeline": str(self.out / "timeline.json"),
                       "sound": str(self.out / "audio/mix.wav")},
            "limitations": ["Supervised original pilot, not an isolated model benchmark.",
                           "No student learning study has been performed.", *review["limitations"]]})
        self.event("published_preview", video=str(final), sha256=sha256(final))
        print(json.dumps(read_json(self.out / "delivery.json"), ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "render", "inspect", "assemble"])
    parser.add_argument("--spec", type=Path, default=ROOT / "configs/projectile-story.json")
    parser.add_argument("--provider", choices=["edge", "say"], default="edge")
    parser.add_argument("--quality", choices=["l", "m", "h"], default="m")
    parser.add_argument("--allow-local-code", action="store_true")
    args = parser.parse_args()
    production = Production(args.spec)
    if args.action == "prepare":
        asyncio.run(production.prepare(args.provider))
    elif args.action == "render":
        production.render(args.quality, args.allow_local_code)
    elif args.action == "inspect":
        production.inspect()
    else:
        production.assemble()


if __name__ == "__main__":
    main()
