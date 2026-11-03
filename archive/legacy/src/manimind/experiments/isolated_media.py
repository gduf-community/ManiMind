"""匿名比较实验的媒体基础设施，不生成、修复内容或写审批。

prepare 写 plan.json、audio/、media-preparation.json；reviewer/assembler 消费。
两个入口先委托 isolated_comparison.verify_selected_run 校验预注册来源链。
这些派生媒体属于一次 run，任何输入、实现或音轨变化均使准备记录及审核失效；
失败记录保留，换 run/project 重试。长期计划仍由 pipeline.init 冻结。
assemble 写不可覆盖的 lesson.mp4/delivery.json，供 lead/用户消费。

独立 reviewer 写 run_dir/media-review.json，字段为 project_id、attempt、
reviewer_role="reviewer"、reviewer_id、status="approved"、blockers=[]、hashes。
hashes 必须精确包含 answer、plan、preparation、audio、subtitles、video：
分别绑定 answer.json、plan.json、media-preparation.json、audio/narration.wav、
audio/narration.srt 和该 attempt 的 render.json.video_path 的原始文件 SHA256。
角色标识沿用仓库的可信操作者约定，不是文件作者的密码学认证。
assemble 内部调用不可重复发布的 pipeline.publish，请勿提前单独 publish。
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import time
import wave

from ..components import pipeline
from ..components.plan import exact, identifier, validate_plan
from ..postproduce import pilot

SHOT_SECONDS = 18
SHOT_COUNT = 6
DURATION = SHOT_SECONDS * SHOT_COUNT
SAMPLE_RATE = pilot.SAMPLE_RATE
LEAD_FRAMES = round(.3 * SAMPLE_RATE)
TAIL_FRAMES = round(.5 * SAMPLE_RATE)
SHOT_FRAMES = SHOT_SECONDS * SAMPLE_RATE
VOICE = "Tingting"
RATE = 240
WRITER = "isolated_media"
SCHEMA = "isolated-media-1"


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError(f"Nonfinite JSON value: {value}")


def _answer(run_dir, project_id):
    identifier(project_id)
    raw = (run_dir / "answer.json").read_bytes()
    answer = json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
    exact(answer, {"plan", "narration"}, "answer")
    plan = validate_plan(answer["plan"])
    if plan["id"] != "lesson" or plan["provenance"]["author"] != "candidate":
        raise ValueError("Expected anonymous lesson plan by candidate")
    if len(plan["shots"]) != SHOT_COUNT or any(s["duration"] != SHOT_SECONDS for s in plan["shots"]):
        raise ValueError("Expected six shots of exactly 18 seconds")
    narration = answer["narration"]
    if not isinstance(narration, list) or len(narration) != SHOT_COUNT:
        raise ValueError("Expected one narration entry per shot")
    by_id = {}
    for entry in narration:
        exact(entry, {"shot_id", "text"}, "narration")
        identifier(entry["shot_id"])
        text = entry["text"]
        if (not isinstance(text, str) or not text.strip() or any(ord(c) < 32 for c in text)
                or "[[" in text or "]]" in text):
            raise ValueError("Plain narration text required; say commands are forbidden")
        if entry["shot_id"] in by_id:
            raise ValueError("Duplicate narration shot")
        by_id[entry["shot_id"]] = text
    if set(by_id) != {s["id"] for s in plan["shots"]}:
        raise ValueError("Narration must cover exactly the plan shots")
    plan["id"] = project_id
    return plan, by_id, hashlib.sha256(raw).hexdigest()


def _sentences(text):
    # 只在句末分行，保留原字符；不按字数截断，也不把小数点当句末。
    ends = list(re.finditer(r'[。！？!?]+[”’」』"]*|[.](?=\s|$)', text))
    parts, start = [], 0
    for match in ends:
        parts.append(text[start:match.end()])
        start = match.end()
    if start < len(text):
        tail = text[start:]
        if parts and not tail.strip():
            parts[-1] += tail
        else:
            parts.append(tail)
    return parts or [text]


def _plan_bytes(plan):
    return (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _freeze(run_dir, project_id, plan):
    path = run_dir / "plan.json"
    expected = _plan_bytes(plan)
    if path.exists():
        if path.read_bytes() != expected:
            raise ValueError("Derived plan changed; use a new run/project")
    else:
        path.write_bytes(expected)
    out, context, _ = pipeline.paths(project_id)
    if out.exists() or context.exists():
        if pipeline.frozen_plan(project_id) != plan:
            raise ValueError("Frozen project differs from candidate plan")
    else:
        pipeline.init(path)
    if (out / "plan.json").read_bytes() != expected:
        raise ValueError("Frozen project plan bytes differ")


def _pcm(path):
    with wave.open(str(path), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (
                1, 2, SAMPLE_RATE, "NONE"):
            raise ValueError("Expected mono 48kHz PCM16 audio")
        frames = source.getnframes()
        data = source.readframes(frames)
    if frames <= 0 or len(data) != frames * 2:
        raise ValueError("Empty or incomplete audio")
    return frames, data


def _write_pcm(path, data):
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        output.writeframes(data)


def _artifact(run_dir, relative):
    path = (run_dir / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(run_dir / "audio"):
        raise ValueError("Media artifact must remain inside run_dir/audio")
    return path


def _remember(report, run_dir, path):
    digest = pilot.sha256(path)
    report["artifacts"][str(path.relative_to(run_dir))] = digest
    return digest


def _srt(shots):
    return "\n\n".join(
        f"{index}\n{pilot.srt_time(shot['speech_start'])} --> {pilot.srt_time(shot['speech_end'])}\n"
        + "\n".join(sentence["text"] for sentence in shot["sentences"])
        for index, shot in enumerate(shots, 1)) + "\n"


def _prepared(run_dir, project_id):
    plan, narration, answer_hash = _answer(run_dir, project_id)
    report = pilot.read_json(run_dir / "media-preparation.json")
    if report.get("status") != "prepared":
        raise ValueError("Incomplete preparation; preserve evidence and use a new run/project")
    expected = {"schema_version": SCHEMA, "project_id": project_id, "answer_sha256": answer_hash,
                "plan_sha256": hashlib.sha256(_plan_bytes(plan)).hexdigest(),
                "implementation_sha256": pilot.sha256(Path(__file__)),
                "voice": VOICE, "speech_rate": RATE, "sample_rate": SAMPLE_RATE, "duration": DURATION,
                "lead_in": .3, "minimum_tail": .5, "writer_role": "media_preparer", "writer_id": WRITER,
                "audio_path": "audio/narration.wav", "subtitles_path": "audio/narration.srt"}
    if any(report.get(key) != value for key, value in expected.items()):
        raise ValueError("Stale media preparation")
    if ((run_dir / "plan.json").read_bytes() != _plan_bytes(plan) or pipeline.frozen_plan(project_id) != plan
            or (pipeline.paths(project_id)[0] / "plan.json").read_bytes() != _plan_bytes(plan)):
        raise ValueError("Prepared or frozen plan changed")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("Missing audio artifact hashes")
    for relative, digest in artifacts.items():
        if pilot.sha256(_artifact(run_dir, relative)) != digest:
            raise ValueError(f"Changed media artifact: {relative}")
    for key in ("audio", "subtitles"):
        if artifacts.get(report[f"{key}_path"]) != report.get(f"{key}_sha256"):
            raise ValueError(f"Missing {key} hash binding")
    shots = report.get("shots", [])
    if len(shots) != SHOT_COUNT:
        raise ValueError("Missing prepared shots")
    required = {"audio/narration.wav", "audio/narration.srt"}
    lesson_parts, total_tts = [], 0.0
    for index, (source, shot) in enumerate(zip(plan["shots"], shots)):
        if (shot["shot_id"] != source["id"] or shot["text"] != narration[source["id"]]
                or [s["text"] for s in shot["sentences"]] != _sentences(shot["text"])):
            raise ValueError("Prepared narration changed")
        frames, parts = 0, []
        for number, sentence in enumerate(shot["sentences"], 1):
            name = f"audio/{index + 1:02d}-{source['id']}-{number:02d}"
            for key, extension in (("text", "txt"), ("source", "aiff"), ("audio", "wav")):
                relative = f"{name}.{extension}"
                required.add(relative)
                if sentence.get(f"{key}_path") != relative:
                    raise ValueError("Prepared sentence path changed")
            count, data = _pcm(run_dir / sentence["audio_path"])
            if (sentence.get("frames") != count or sentence.get("duration") != count / SAMPLE_RATE
                    or sentence.get("start") != index * SHOT_SECONDS + .3 + frames / SAMPLE_RATE
                    or (run_dir / sentence["text_path"]).read_text(encoding="utf-8") != sentence["text"]
                    or sentence.get("audio_sha256") != artifacts.get(sentence["audio_path"])
                    or sentence.get("source_sha256") != artifacts.get(sentence["source_path"])):
                raise ValueError("Prepared sentence timing or binding changed")
            elapsed = sentence.get("tts_seconds")
            if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError("Invalid recorded TTS cost")
            total_tts += elapsed
            frames += count
            parts.append(data)
        relative = f"audio/{index + 1:02d}-{source['id']}.wav"
        required.add(relative)
        tail = SHOT_FRAMES - LEAD_FRAMES - frames
        expected_shot = {"start": index * SHOT_SECONDS, "duration": SHOT_SECONDS, "audio_path": relative,
                         "audio_sha256": artifacts.get(relative), "audio_duration": frames / SAMPLE_RATE,
                         "speech_start": index * SHOT_SECONDS + .3,
                         "speech_end": index * SHOT_SECONDS + .3 + frames / SAMPLE_RATE,
                         "tail_silence": tail / SAMPLE_RATE}
        data = b"\0" * (LEAD_FRAMES * 2) + b"".join(parts) + b"\0" * (max(tail, 0) * 2)
        if (tail < TAIL_FRAMES or any(shot.get(k) != v for k, v in expected_shot.items())
                or _pcm(run_dir / relative) != (SHOT_FRAMES, data)):
            raise ValueError("Prepared shot timing or audio changed")
        lesson_parts.append(data)
    if set(artifacts) != required or report.get("tts_seconds") != total_tts:
        raise ValueError("Incomplete preparation artifact or TTS ledger")
    if _pcm(run_dir / "audio/narration.wav") != (DURATION * SAMPLE_RATE, b"".join(lesson_parts)):
        raise ValueError("Prepared audio must be exactly 108 seconds")
    if (run_dir / "audio/narration.srt").read_text(encoding="utf-8") != _srt(shots):
        raise ValueError("Prepared subtitles changed")
    return report


def prepare(run_dir: Path, project_id: str) -> dict:
    """冻结原样计划的改名副本，逐句测时并拼成六条镜头音轨；不生成视频。"""
    from .isolated_comparison import verify_selected_run

    run_dir = Path(run_dir).resolve()
    verify_selected_run(run_dir, project_id)
    plan, narration, answer_hash = _answer(run_dir, project_id)
    with pipeline.command_lock(project_id):
        if (run_dir / "media-preparation.json").exists():
            return _prepared(run_dir, project_id)
        if (run_dir / "audio").exists():
            raise ValueError("Unrecorded audio exists; use a new run/project")
        _freeze(run_dir, project_id, plan)
        audio_dir = run_dir / "audio"
        audio_dir.mkdir()
        report = {
            "schema_version": SCHEMA, "project_id": project_id, "status": "preparing",
            "writer_role": "media_preparer", "writer_id": WRITER, "consumer_roles": ["reviewer", "assembler", "lead"],
            "lifecycle": "One isolated run; preserve failures and reuse only identical prepared media.",
            "invalidation_rule": "Changed answer, plan, implementation or media invalidates preparation and review.",
            "answer_sha256": answer_hash, "plan_sha256": pilot.sha256(run_dir / "plan.json"),
            "implementation_sha256": pilot.sha256(Path(__file__)),
            "voice": VOICE, "speech_rate": RATE, "sample_rate": SAMPLE_RATE, "duration": DURATION,
            "lead_in": .3, "minimum_tail": .5, "tts_seconds": 0.0, "shots": [], "artifacts": {},
            "audio_path": "audio/narration.wav", "subtitles_path": "audio/narration.srt",
        }
        report_path = run_dir / "media-preparation.json"
        pilot.write_json(report_path, report)
        try:
            lesson_parts = []
            for index, source in enumerate(plan["shots"]):
                shot = {"shot_id": source["id"], "text": narration[source["id"]], "start": index * SHOT_SECONDS,
                        "duration": SHOT_SECONDS, "speech_start": index * SHOT_SECONDS + .3, "sentences": []}
                report["shots"].append(shot)
                spoken_frames, parts = 0, []
                for number, text in enumerate(_sentences(shot["text"]), 1):
                    name = f"{index + 1:02d}-{source['id']}-{number:02d}"
                    text_path, aiff, raw = [audio_dir / f"{name}.{ext}" for ext in ("txt", "aiff", "wav")]
                    text_path.write_text(text, encoding="utf-8")
                    _remember(report, run_dir, text_path)
                    sentence = {"text": text, "start": shot["speech_start"] + spoken_frames / SAMPLE_RATE,
                                "text_path": str(text_path.relative_to(run_dir)),
                                "source_path": str(aiff.relative_to(run_dir)), "audio_path": str(raw.relative_to(run_dir))}
                    shot["sentences"].append(sentence)
                    started = time.perf_counter()
                    try:
                        pilot.run(["say", "-v", VOICE, "-r", str(RATE), "-o", aiff, "-f", text_path], timeout=180)
                    finally:
                        sentence["tts_seconds"] = time.perf_counter() - started
                        report["tts_seconds"] += sentence["tts_seconds"]
                        pilot.write_json(report_path, report)
                    sentence["source_sha256"] = _remember(report, run_dir, aiff)
                    pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-i", aiff, "-ac", "1",
                               "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", raw])
                    frames, data = _pcm(raw)
                    sentence.update(frames=frames, duration=frames / SAMPLE_RATE,
                                    audio_sha256=_remember(report, run_dir, raw))
                    spoken_frames += frames
                    if spoken_frames + LEAD_FRAMES + TAIL_FRAMES > SHOT_FRAMES:
                        raise ValueError(f"Narration exceeds 17.2 seconds in shot {source['id']}; no truncation or speedup")
                    parts.append(data)
                tail = SHOT_FRAMES - LEAD_FRAMES - spoken_frames
                data = b"\0" * (LEAD_FRAMES * 2) + b"".join(parts) + b"\0" * (tail * 2)
                path = audio_dir / f"{index + 1:02d}-{source['id']}.wav"
                _write_pcm(path, data)
                shot.update(audio_duration=spoken_frames / SAMPLE_RATE, tail_silence=tail / SAMPLE_RATE,
                            speech_end=shot["speech_start"] + spoken_frames / SAMPLE_RATE,
                            audio_path=str(path.relative_to(run_dir)), audio_sha256=_remember(report, run_dir, path))
                lesson_parts.append(data)
                pilot.write_json(report_path, report)
            _write_pcm(run_dir / report["audio_path"], b"".join(lesson_parts))
            (run_dir / report["subtitles_path"]).write_text(_srt(report["shots"]), encoding="utf-8")
            for key in ("audio", "subtitles"):
                report[f"{key}_sha256"] = _remember(report, run_dir, run_dir / report[f"{key}_path"])
            if _answer(run_dir, project_id)[2] != answer_hash:
                raise ValueError("Answer changed during preparation")
            verify_selected_run(run_dir, project_id)
            report["status"] = "prepared"
            pilot.write_json(report_path, report)
            return _prepared(run_dir, project_id)
        except Exception as error:
            report.update(status="failed", error=str(error)[:2000])
            pilot.write_json(report_path, report)
            raise


def _review_hashes(run_dir, video):
    return {key: pilot.sha256(path) for key, path in {
        "answer": run_dir / "answer.json", "plan": run_dir / "plan.json",
        "preparation": run_dir / "media-preparation.json", "audio": run_dir / "audio/narration.wav",
        "subtitles": run_dir / "audio/narration.srt", "video": video,
    }.items()}


def _media_review(run_dir, project_id, attempt, hashes):
    path = run_dir / "media-review.json"
    digest = pilot.sha256(path)
    review = pilot.read_json(path)
    reviewer = review.get("reviewer_id")
    if (review.get("reviewer_role") != "reviewer" or not isinstance(reviewer, str) or not reviewer.strip()
            or reviewer.strip().casefold() in {"candidate", WRITER}):
        raise ValueError("Independent media reviewer required")
    if review.get("project_id") != project_id or type(review.get("attempt")) is not int or review["attempt"] != attempt:
        raise ValueError("Media review belongs to another render")
    if review.get("status") != "approved" or review.get("blockers") != []:
        raise ValueError("Media review has not passed")
    if review.get("hashes") != hashes:
        raise ValueError("Stale media review")
    if pilot.sha256(path) != digest:
        raise ValueError("Media approval changed while being read")
    return review, digest


def _duration(stream):
    duration = float(stream.get("duration", "nan"))
    start = float(stream.get("start_time", "nan"))
    if not math.isfinite(duration) or abs(duration - DURATION) > .05 or not math.isfinite(start) or abs(start) > .05:
        raise ValueError("Expected 108-second media starting at zero")
    return duration


def _streams(path, final=False, original=None):
    metadata = pilot.probe(path)
    streams = metadata["streams"]
    expected = ["audio", "subtitle", "video"] if final else ["video"]
    if sorted(s["codec_type"] for s in streams) != expected:
        raise ValueError("Unexpected media streams")
    video = next(s for s in streams if s["codec_type"] == "video")
    video_duration = _duration(video)
    _duration(metadata["format"])
    if final:
        audio = next(s for s in streams if s["codec_type"] == "audio")
        subtitle = next(s for s in streams if s["codec_type"] == "subtitle")
        if (audio["codec_name"] != "aac" or int(audio["sample_rate"]) != SAMPLE_RATE or audio["channels"] != 1
                or subtitle["codec_name"] != "mov_text" or abs(_duration(audio) - video_duration) > .05):
            raise ValueError("Invalid final audio/subtitle streams")
        if any(video.get(key) != original.get(key) for key in ("codec_name", "width", "height", "avg_frame_rate")):
            raise ValueError("Copied video stream changed")
    return video


def assemble(run_dir: Path, project_id: str, attempt: int) -> Path:
    """先过组件发布及独立媒体审核，再无变速封装；校验通过才交付。"""
    from .isolated_comparison import verify_selected_run

    run_dir = Path(run_dir).resolve()
    verify_selected_run(run_dir, project_id)
    folder = pipeline.attempt_dir(project_id, attempt)
    with pipeline.command_lock(project_id):
        destination, pending = run_dir / "lesson.mp4", run_dir / "lesson-pending.mp4"
        if any(p.exists() for p in (destination, pending, run_dir / "delivery.json")):
            raise ValueError("Media delivery is immutable; existing output will not be overwritten")
        _prepared(run_dir, project_id)
        rendered = pilot.read_json(folder / "render.json")
        video = Path(rendered["video_path"])
        hashes = _review_hashes(run_dir, video)
        review, review_digest = _media_review(run_dir, project_id, attempt, hashes)
        component_review = pipeline.paths(project_id)[1] / f"review-{attempt:03d}.json"
        sources = [component_review, folder / "review-input.json", folder / "render.json"]
        approvals = {str(path): pilot.sha256(path) for path in sources}
        approvals[str(run_dir / "media-review.json")] = review_digest
        evidence = pipeline.evidence_hashes(project_id, attempt)
        original = _streams(video)
        published = Path(pipeline.publish(project_id, attempt))
        component_delivery = pipeline.paths(project_id)[0] / f"delivery-{attempt:03d}.json"
        approvals[str(component_delivery)] = pilot.sha256(component_delivery)

        def unchanged():
            verify_selected_run(run_dir, project_id)
            _prepared(run_dir, project_id)
            if (_review_hashes(run_dir, video) != hashes or pilot.sha256(published) != hashes["video"]
                    or pipeline.evidence_hashes(project_id, attempt) != evidence
                    or any(pilot.sha256(Path(path)) != digest for path, digest in approvals.items())):
                raise ValueError("Media inputs or approvals changed during assembly")

        unchanged()
        try:
            pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-i", published,
                       "-i", run_dir / "audio/narration.wav", "-i", run_dir / "audio/narration.srt",
                       "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0", "-c:v", "copy",
                       "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE), "-c:s", "mov_text",
                       "-metadata:s:s:0", "language=zho", "-disposition:s:0", "default",
                       "-movflags", "+faststart", pending], timeout=300)
            stream = _streams(pending, final=True, original=original)
            pilot.run([pilot.FFMPEG, "-v", "error", "-i", pending, "-map", "0:v:0", "-map", "0:a:0",
                       "-f", "null", "-"], timeout=300)
            unchanged()
            pending.replace(destination)
            pilot.write_json(run_dir / "delivery.json", {
                "project_id": project_id, "attempt": attempt, "writer_role": "assembler",
                "consumer_roles": ["lead", "user"], "lifecycle": "Immutable delivery of this run",
                "invalidation_rule": "Changed sources or approvals invalidate delivery provenance.",
                "video": str(destination), "sha256": pilot.sha256(destination), "duration": float(stream["duration"]),
                "resolution": [stream["width"], stream["height"]], "hashes": hashes, "approval_sources": approvals,
                "media_review": str(run_dir / "media-review.json"),
                "media_review_sha256": approvals[str(run_dir / "media-review.json")],
                "component_review": str(component_review), "component_review_sha256": approvals[str(component_review)],
                "reviewer_id": review["reviewer_id"], "voice": VOICE, "speech_rate": RATE, "pipeline_llm_requests": 0,
            })
        except Exception:
            pending.unlink(missing_ok=True)
            raise
        return destination
