"""A complete, bounded lesson using model copy and trusted visual components.

The immutable project freezes the candidate answer and a component snapshot.
Audio/timeline/media are rebuildable outputs; request history remains in the
separate model_dialogue case. Only an independent hash-bound review can mux.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import math
from pathlib import Path
import re
import shutil
import wave

from . import pilot
from ..render.manim_renderer import extract_keyframes, render_manim_scene

ROOT = pilot.ROOT
DEFAULT_ID = "velocity-full-deepseek-20261018"
CUE_IDS = ("hook", "model", "average", "graph", "half", "tenth", "approach",
           "zero", "algebra", "zoom", "result", "recap")
read_json, write_json, sha256 = pilot.read_json, pilot.write_json, pilot.sha256


def validate_script(data: dict) -> None:
    if not isinstance(data, dict) or set(data) != {"title", "cues"}:
        raise ValueError("Unexpected script fields")
    if not isinstance(data["title"], str) or not 1 <= len(data["title"]) <= 20:
        raise ValueError("Invalid title")
    cues = data["cues"]
    if not isinstance(cues, list) or not all(isinstance(c, dict) for c in cues):
        raise ValueError("Expected cue objects")
    if [c.get("id") for c in cues] != list(CUE_IDS):
        raise ValueError("Cue order is frozen")
    for cue in cues:
        if set(cue) != {"id", "heading", "subtitle_lines", "spoken", "min_duration"}:
            raise ValueError(f"Unexpected cue fields: {cue['id']}")
        if not isinstance(cue["heading"], str) or not 1 <= len(cue["heading"]) <= 18:
            raise ValueError("Invalid heading")
        lines = cue["subtitle_lines"]
        if (not isinstance(lines, list) or len(lines) != 2
                or not all(isinstance(s, str) and 8 <= len(s) <= 36 for s in lines)
                or sum(map(len, lines)) > 68):
            raise ValueError(f"Invalid subtitles: {cue['id']}")
        if not isinstance(cue["spoken"], str) or not 16 <= len(cue["spoken"]) <= 150:
            raise ValueError("Invalid spoken copy")
        duration = cue["min_duration"]
        if (type(duration) not in (int, float) or not math.isfinite(duration)
                or not 8 <= duration <= 16 or duration * 2 != round(duration * 2)):
            raise ValueError("Invalid cue duration")
        if cue["id"] == "algebra" and duration < 14:
            raise ValueError("Algebra needs reading time")


@dataclass(frozen=True)
class Lesson:
    project_id: str = DEFAULT_ID

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", self.project_id):
            raise ValueError("Invalid project id")

    @property
    def out(self) -> Path:
        return ROOT / "outputs" / self.project_id

    @property
    def context(self) -> Path:
        return ROOT / "runtime/projects" / self.project_id

    @property
    def session(self) -> Path:
        return ROOT / "runtime/sessions" / f"{self.project_id}-production"

    def init(self, answer: Path) -> None:
        data = read_json(answer)
        validate_script(data)
        if self.out.exists() or self.context.exists():
            raise ValueError("Existing lesson must not be overwritten")
        base = read_json(pilot.SPEC)
        spec = {**base, "project_id": self.project_id, "title": data["title"], "speech_rate": "+0%",
                "cues": [{**old, **new} for old, new in zip(base["cues"], data["cues"])]}
        # Freeze the engineer-owned component, never execute candidate code.
        source = pilot.SCENE.read_text(encoding="utf-8")
        source += ("\n\nclass FullVelocity(InstantaneousVelocity):\n"
                   f"    timeline_path = Path({str(self.out / 'timeline.json')!r})\n")
        self.out.mkdir(parents=True)
        (self.out / "scene.py").write_text(source, encoding="utf-8")
        shutil.copy2(pilot.CONFIG, self.out / "manimgl.yml")
        shutil.copy2(answer, self.out / "model-script.json")
        write_json(self.out / "spec.json", spec)
        write_json(self.context / "production.json", {
            "scope": "long_term", "writer_role": "coordinator",
            "consumer_roles": ["manim_worker", "reviewer", "lead"], "lifecycle": "This complete lesson",
            "invalidation_rule": "Any change to script, component, timeline, audio or render invalidates approval.",
            "candidate_answer": str(answer.resolve()), "candidate_sha256": sha256(answer),
            "component_origin": str(pilot.SCENE), "component_origin_sha256": sha256(pilot.SCENE),
            "spec_sha256": sha256(self.out / "spec.json"), "facts": spec["facts"],
            "ownership": {"candidate": "Narration, headings, minimum cue durations",
                          "engineer": "Frozen mathematics, visual composition, animation components and production"},
            "is_unattended_benchmark": False,
        })

    async def prepare(self, provider: str) -> None:
        if provider not in {"edge", "say"}:
            raise ValueError("Explicit supported TTS provider required")
        spec = read_json(self.out / "spec.json")
        audio_dir = self.out / "audio"
        audio_dir.mkdir(exist_ok=True)
        cues, cursor = [], 0.0
        for index, cue in enumerate(spec["cues"], 1):
            stem = f"{index:02d}-{cue['id']}"
            source = audio_dir / f"{stem}.{'mp3' if provider == 'edge' else 'aiff'}"
            stamp = audio_dir / f"{stem}.json"
            cache = {"provider": provider, "spoken": cue["spoken"],
                     "voice": spec["voice"] if provider == "edge" else "Tingting",
                     "rate": spec["speech_rate"] if provider == "edge" else "240"}
            if not (source.exists() and stamp.exists() and read_json(stamp) == cache):
                if provider == "edge":
                    import edge_tts
                    await asyncio.wait_for(edge_tts.Communicate(
                        cue["spoken"], spec["voice"], rate=spec["speech_rate"]).save(str(source)), 90)
                else:
                    pilot.run(["say", "-v", "Tingting", "-r", "240", "-o", source, cue["spoken"]])
                write_json(stamp, cache)
            raw = audio_dir / f"{stem}-raw.wav"
            pilot.run([pilot.FFMPEG, "-v", "error", "-y", "-i", source,
                       "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", raw])
            with wave.open(str(raw), "rb") as wav:
                seconds = wav.getnframes() / wav.getframerate()
            duration = pilot.cue_duration(seconds, cue["min_duration"], spec["fps"])
            padded = audio_dir / f"{stem}.wav"
            pilot.run([pilot.FFMPEG, "-v", "error", "-y", "-i", raw, "-af", "adelay=300,apad",
                       "-t", f"{duration:.9f}", "-c:a", "pcm_s16le", padded])
            cues.append({**cue, "text": "".join(cue["subtitle_lines"]), "start": round(cursor, 9),
                         "speech_start": round(cursor + .3, 9), "duration": duration,
                         "audio_duration": seconds, "audio_path": str(padded)})
            cursor += duration
            print(f"{stem}: speech={seconds:.2f}s cue={duration:.2f}s", flush=True)
        write_json(self.out / "timeline.json", {"project_id": self.project_id, "fps": spec["fps"],
                   "spec_sha256": sha256(self.out / "spec.json"), "duration": round(cursor, 9),
                   "provider": provider, "voice": cache["voice"], "cues": cues})
        with wave.open(str(audio_dir / "narration.wav"), "wb") as output:
            output.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            for cue in cues:
                with wave.open(cue["audio_path"], "rb") as source_wav:
                    output.writeframes(source_wav.readframes(source_wav.getnframes()))
        write_json(self.session / "state.json", {
            "scope": "short_term", "writer_role": "coordinator", "consumer_roles": ["lead", "reviewer"],
            "lifecycle": "Current production attempt", "invalidation_rule": "Rebuild after any input change",
            "phase": "audio_prepared", "duration": cursor})

    def hashes(self, video: Path | None = None) -> dict:
        timeline = read_json(self.out / "timeline.json")
        if timeline["spec_sha256"] != sha256(self.out / "spec.json"):
            raise ValueError("Stale narration")
        paths = {"source": self.out / "scene.py", "spec": self.out / "spec.json",
                 "timeline": self.out / "timeline.json", "config": self.out / "manimgl.yml",
                 "audio": self.out / "audio/narration.wav", "model_script": self.out / "model-script.json",
                 "producer": Path(__file__), "pilot_helpers": Path(pilot.__file__)}
        if video is not None:
            paths["video"] = video
        return {k: sha256(v) for k, v in paths.items()}

    def render(self, quality: str) -> None:
        before = self.hashes()
        version = len(list(self.session.glob("render-*.json"))) + 1
        result = render_manim_scene(
            segment_id=f"full-v{version:02d}-{quality}",
            scene_code=(self.out / "scene.py").read_text(encoding="utf-8"),
            scene_class_name="FullVelocity", output_dir=self.out, quality=quality,
            config_file=self.out / "manimgl.yml", timeout_seconds=2400)
        write_json(self.session / f"render-{version:02d}.json", result.to_dict())
        if not result.success:
            raise RuntimeError(result.to_dict())
        if before != self.hashes() or sha256(Path(result.code_path)) != before["source"]:
            raise ValueError("Inputs changed during render")
        write_json(self.out / "render.json", {**result.to_dict(), "hashes": self.hashes(Path(result.video_path))})
        print(result.video_path, flush=True)

    def inspect(self) -> None:
        from PIL import Image, ImageDraw, ImageStat
        rendered = read_json(self.out / "render.json")
        video = Path(rendered["video_path"])
        if rendered["hashes"] != self.hashes(video):
            raise ValueError("Stale render")
        timeline = read_json(self.out / "timeline.json")
        stream = next(s for s in pilot.probe(video)["streams"] if s["codec_type"] == "video")
        if abs(float(stream["duration"]) - timeline["duration"]) > .15:
            raise ValueError("Render duration drift")
        fractions = {"algebra": (.18, .29, .42, .55, .68, .90), "zoom": (.32, .40, .65, .94)}
        requests = [(c["id"], round(c["start"] + c["duration"] * f, 3))
                    for c in timeline["cues"] for f in fractions.get(c["id"], (.25, .60, .94))]
        evidence = extract_keyframes(video_path=video, output_dir=self.out / "frames",
                    timestamps=[t for _, t in requests], ffmpeg_executable=pilot.FFMPEG)
        if not evidence.success or evidence.missing_timestamps or len(evidence.frame_paths) != len(requests):
            raise ValueError("Incomplete frames")
        frames, sheets = [], []
        for batch in range(0, len(requests), 12):
            sheet = Image.new("RGB", (1600, 1008), "#202226")
            draw = ImageDraw.Draw(sheet)
            for i, ((cue, time), name) in enumerate(zip(requests[batch:batch + 12], evidence.frame_paths[batch:batch + 12])):
                with Image.open(name) as frame:
                    if ImageStat.Stat(frame.convert("L")).stddev[0] < 8:
                        raise ValueError("Blank frame")
                    thumb = frame.copy()
                    thumb.thumbnail((533, 225))
                x, y = i % 3 * 533, i // 3 * 252
                sheet.paste(thumb, (x, y + 24))
                draw.text((x + 6, y + 5), f"{cue} / {time:.2f}s", fill="white")
                frames.append({"cue": cue, "time": time, "path": name, "sha256": sha256(Path(name))})
            path = self.out / "frames" / f"contact-{batch // 12 + 1:02d}.jpg"
            sheet.save(path, quality=94)
            sheets.append(str(path))
        write_json(self.out / "review-input.json", {
            "project_id": self.project_id, "hashes": self.hashes(video), "video_path": str(video),
            "source_path": str(self.out / "scene.py"), "timeline_path": str(self.out / "timeline.json"),
            "duration": float(stream["duration"]), "resolution": [stream["width"], stream["height"]],
            "frames": frames, "contact_sheets": sheets,
            "required_checks": ["mathematics", "visual_layout", "narrative", "cue_timing", "actual_zoom"],
            "instruction": "Independent review of actual pixels in every cue, source and timeline; no self approval."})
        print(f"Extracted {len(frames)} frames for independent review", flush=True)

    def assemble(self) -> None:
        evidence = read_json(self.out / "review-input.json")
        review_path = self.context / "review.json"
        review = read_json(review_path)
        video = Path(evidence["video_path"])
        current = self.hashes(video)
        if evidence["hashes"] != current:
            raise ValueError("Stale evidence")
        pilot.validate_review(review, current, evidence["frames"])
        inspected = set(review["inspected_frames"])
        covered = {f["cue"] for f in evidence["frames"] if f["path"] in inspected}
        if covered != set(CUE_IDS):
            raise ValueError("Every cue requires actual frame review")
        timeline = read_json(self.out / "timeline.json")
        final = self.out / "instantaneous-velocity-full.mp4"
        pilot.run([pilot.FFMPEG, "-v", "error", "-y", "-i", video, "-i", self.out / "audio/narration.wav",
                   "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                   "-af", "loudnorm=I=-18:TP=-1.5:LRA=7", "-t", str(timeline["duration"]),
                   "-movflags", "+faststart", final])
        streams = pilot.probe(final)["streams"]
        vs = next(s for s in streams if s["codec_type"] == "video")
        audio = next(s for s in streams if s["codec_type"] == "audio")
        if abs(float(vs["duration"]) - float(audio["duration"])) > .15:
            raise ValueError("Final A/V duration mismatch")
        pilot.run([pilot.FFMPEG, "-v", "error", "-i", final, "-f", "null", "-"], timeout=300)
        subtitles = [f"{i}\n{pilot.srt_time(c['start'])} --> {pilot.srt_time(c['start'] + c['duration'])}\n"
                     + "\n".join(c["subtitle_lines"]) for i, c in enumerate(timeline["cues"], 1)]
        (self.out / "instantaneous-velocity-full.srt").write_text("\n\n".join(subtitles) + "\n", encoding="utf-8")
        write_json(self.out / "delivery.json", {
            "video": str(final), "sha256": sha256(final), "duration": float(vs["duration"]),
            "resolution": [vs["width"], vs["height"]], "fps": vs["avg_frame_rate"],
            "voice": timeline["voice"], "review": str(review_path), "review_sha256": sha256(review_path),
            "hashes": current, "full_decode_passed": True,
            "limitations": ["Model-authored copy with engineer-owned fixed-topic components, not autonomous general video creation.",
                            "Synthetic narration; no student comprehension study.", *review.get("limitations", [])]})
        print(f"Delivered {final} ({vs['duration']}s)", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "prepare", "render", "inspect", "assemble"])
    parser.add_argument("--project-id", default=DEFAULT_ID)
    parser.add_argument("--answer", type=Path)
    parser.add_argument("--provider", choices=["edge", "say"], default="edge")
    parser.add_argument("--quality", choices=["l", "m", "h"], default="h")
    args = parser.parse_args()
    lesson = Lesson(args.project_id)
    from ..experiments.model_benchmark import exclusive_run
    with exclusive_run(args.project_id):
        if args.action == "init":
            if args.answer is None:
                parser.error("--answer is required for init")
            lesson.init(args.answer)
        elif args.action == "prepare":
            asyncio.run(lesson.prepare(args.provider))
        elif args.action == "render":
            lesson.render(args.quality)
        else:
            getattr(lesson, args.action)()


if __name__ == "__main__":
    main()
