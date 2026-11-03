import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import wave

import pytest

from manimind.postproduce import unit_film as subject
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.learning_quality import DIMENSIONS


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    subject.common.write_json(path, value)


def replace(path, value):
    path.unlink()
    write(path, value)


def review(stage, bindings):
    value = {"action": "review", "stage": stage, "status": "pass", "reviewer_role": "independent",
             "reviewer_agent": "independent-" + stage, "bindings": bindings, "blocking_findings": [],
             "reviewer_context": "new-review-context-" + stage,
             "release_authorized": True, "listening_reviewed": False, "student_tested": False}
    if stage in {"visual", "narration"}:
        value.update(viewer_test={"can_explain": "visible reason", "missing_links": [],
            "transfer_question": "new case", "supported_answer": "supported, not student tested"},
            quality={name: {"rating": 4, "evidence": "actual pixels at 1s"} for name in DIMENSIONS},
            editorial_checks={name: {"status": "pass", "evidence": [{"time": 1, "finding": "actual state"}]}
                              for name in subject.quality.CHECKS})
    return value


@pytest.fixture
def project(tmp_path, monkeypatch):
    common = subject.common
    root = tmp_path
    monkeypatch.setattr(subject.pilot, "ROOT", root)
    profile = root / "profile.json"
    write(profile, {"version": "understanding-first-v3", "delivery_contract": subject.units.SOURCE_CONTRACT})
    catalogue = root / "catalogue.csv"
    with catalogue.open("x", newline="") as out:
        fields = sorted(subject.curriculum.CATALOGUE_FIELDS)
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerow({key: "" if key == "requires" else "topic" for key in fields})
    course = root / "unit.json"
    write(course, {"schema_version": 1, "catalogue": "catalogue.csv", "unit_id": "course", "title": "Course",
        "audience": "students", "scope": "one course", "lessons": [{"project_id": "lesson", "catalogue_ids": ["topic"],
        "new_understanding": "new relation", "exit_task": "predict", "handoff": "next case"}]})
    context = root / "runtime/projects/lesson/context-v001.json"
    subject.curriculum.write_context(course, "lesson", context, root)
    scene = root / "scene.py"
    scene.write_text("# hash-only scene fixture\n", encoding="utf-8")
    sources = [context, course, catalogue, Path(subject.curriculum.__file__).resolve()]
    plan = {"title": "fixture", "project_id": "lesson", "scene": "scene.py", "workflow_profile": "profile.json",
        "author_agent": "visual-author", "author_context": "visual-author-context",
        "revision_mode": "fresh", "lesson_context": str(context.relative_to(root)), "sources": [str(p) for p in sources],
        "cues": [{"id": "demo", "duration": 8, "heading": "Demo", "visual": "real scene fixture",
                  "learning_purpose": "relation", "anchors": [{"id": "event", "meaning": "a relation"}]}]}
    narration = {"schema_version": 3, "author_agent": "narration-author", "author_context": "narration-author-context",
        "units": [{"id": "U1", "cue": "demo", "text": "First;second.",
        "references": [{"id": "R1", "focus": "f1", "text": "First;"}, {"id": "R2", "focus": "f2", "text": "second."}]}]}
    probe = {"format": {"duration": "8"}, "streams": [{"codec_type": "video", "duration": "8", "width": 1920,
        "height": 1080, "avg_frame_rate": "30/1", "nb_frames": "240", "codec_name": "h264",
        "pix_fmt": "yuv420p", "profile": "High"}]}
    calls = []
    real_run, real_probe = subject.pilot.run, subject.pilot.probe
    def run(command, timeout=180):
        calls.append(command)
        if "-filters" in command: return " ass V->V Render ASS subtitles\n"
        if "streamhash" in command: return "0,a,SHA256=" + "a" * 64 + "\n"
        if "-movflags" in command: Path(command[-1]).write_bytes(b"mock media output")
        return ""
    def media_probe(path):
        result = copy.deepcopy(probe)
        if Path(path).name in {"voiced-preview.mp4", "candidate.mp4", "captioned.mp4"}:
            result["streams"].append({"codec_type": "audio", "duration": "8"})
        return result
    monkeypatch.setattr(subject.pilot, "run", run)
    monkeypatch.setattr(subject.pilot, "probe", media_probe)

    def attempt(name, *, second_start=2, video_source=None):
        folder = root / name
        folder.mkdir()
        write(folder / "plan.json", plan)
        write(folder / "workflow-profile.json", common.read_json(profile))
        write(folder / "timeline.json", visual_timeline(plan))
        write(folder / "visual-events.json", {"duration": 8, "events": [{"id": "event", "time": 1}]})
        write(folder / "focus-events.json", {"duration": 8, "windows": [
            {"id": "f1", "start": 1, "end": 3}, {"id": "f2", "start": second_start, "end": 4}]})
        video = folder / "silent.mp4"
        if video_source is None:
            video.write_bytes(b"hash-only silent visual fixture " + name.encode())
        else:
            shutil.copyfile(video_source, video)
        frame = folder / "frame.png"
        from PIL import Image
        Image.new("RGB", (1920, 1080), "#101416").save(frame)
        record = {"video": str(video), "video_sha256": common.sha(video), "duration": 8,
            "plan_sha256": common.sha(folder / "plan.json"),
            "input_hashes": {str(path): common.sha(path) for path in [profile, scene, *sources]}}
        write(folder / "render.json", record)
        write(folder / "review-input.json", {"render": record, "frames": [
            {"time": t / 10, "path": str(frame), "sha256": common.sha(frame)} for t in range(80)], "sheets": []})
        visual_review = root / f"{name}-visual-review.json"
        write(visual_review, review("visual", subject.bindings(folder)))
        draft = root / f"{name}-draft.json"
        write(draft, narration)
        installed = root / f"{name}-narration.json"
        subject.install_narration(folder, draft, visual_review, installed)
        text_review = root / f"{name}-text-review.json"
        write(text_review, review("narration", subject.bindings(folder, installed)))
        output = root / f"{name}-delivery"
        subject.release_silent(folder, installed, visual_review, text_review, output)
        return output / "delivery.json"
    original = attempt("original")
    reference = root / "reference.wav"
    reference.write_bytes(b"synthetic V01 hash fixture")
    monkeypatch.setattr(subject.vox, "REFERENCE_SHA256", common.sha(reference))
    write(reference.with_suffix(".receipt.json"), {"wav_sha256": common.sha(reference)})
    tts_plan = root / "tts-plan.json"
    subject.speech_plan(original, reference, tts_plan)
    speech = root / "speech"
    speech.mkdir()
    shutil.copyfile(tts_plan, speech / "plan.json")
    shutil.copyfile(reference, speech / "reference.wav")
    (speech / "source").mkdir()
    for path in (subject.vox.__file__, subject.vox.audition.__file__):
        shutil.copyfile(path, speech / "source" / Path(path).name)
    setup = {"model_id": subject.vox.audition.MODEL, "revision": subject.vox.audition.REVISION,
             "files": [{"file": "mock-checkpoint", "sha256": "a" * 64}]}
    monkeypatch.setattr(subject.vox, "MODEL_FILES_SHA256", subject.vox.model_files_sha256(setup))
    write(speech / "setup-receipt.json", setup)
    state = {"status": subject.vox.ACCEPTANCE, "attempted": ["U1"], "done": ["U1"], "call_count": 1,
             "model_load_count": 1, "plan_sha256": common.sha(tts_plan), "reference_path": "C:\\speech\\reference.wav"}
    write(speech / "state.json", state)
    engine = {"model": subject.vox.audition.MODEL, "revision": subject.vox.audition.REVISION, "model_files": setup["files"],
              "model_files_sha256": subject.vox.MODEL_FILES_SHA256, "load_options": subject.vox.audition.LOAD_OPTIONS,
              "packages": {"voxcpm": "2.0.3"}, "model_load_count": 1, "plan_sha256": common.sha(tts_plan),
              "setup_sha256": common.sha(speech / "setup-receipt.json"), "worker_sha256": common.sha(subject.vox.__file__),
              "helper_sha256": subject.vox.HELPER_SHA256, "reference_sha256": common.sha(reference), "seed_method": subject.vox.SEED_METHOD}
    write(speech / "engine.json", engine)
    wav = speech / "U1.wav"
    with wave.open(str(wav), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(48000)
        out.writeframes(b"\x10\x00\xf0\xff" * 48000)
    segment = common.read_json(tts_plan)["segments"][0]
    request = subject.vox.generate_kwargs(segment, state["reference_path"], subject.vox.audition.TEXT)
    receipt = {"schema_version": 2, "id": "U1", "segment": segment, "request": request, "generate_kwargs": request,
        "plan_sha256": common.sha(tts_plan), "wav_sha256": common.sha(wav), "reference_sha256": common.sha(reference),
        "first_take": True, "segment_call_count": 1, "acceptance": subject.vox.ACCEPTANCE,
        "worker_sha256": common.sha(subject.vox.__file__), "helper_sha256": subject.vox.HELPER_SHA256,
        "engine": engine, "seed": subject.vox.GENERATION["seed"], "seed_method": subject.vox.SEED_METHOD,
        "model_load_count": 1, "call_count": 1, **subject.forced._wav_info(wav)}
    write(speech / "U1.receipt.json", receipt)
    timings = root / "timings.json"
    write(timings, {"schema_version": 1, "method": subject.units.TIMING_METHOD, "timing_scope": subject.units.TIMING_SCOPE,
        "plan_sha256": common.sha(tts_plan), "writer": "model aligner", "consumers": ["scheduler"],
        "smoke_only": False, "test_only": False, "listening_reviewed": False,
        "acceptance": "estimated_not_listening_or_publication_approved", "plan": str(tts_plan),
        "attempt": str(root / "test-only-attempt"), "software": {"backend": "test-fixture-never-production"},
        "sources": [{"path": str(tts_plan), "sha256": common.sha(tts_plan)}],
        "lifecycle": "attempt", "invalidation": "text/WAV/model changes", "units": [{"id": "U1",
        "wav_sha256": common.sha(wav), "duration_seconds": 2, "phrases": [
            {"id": "R1", "text": "First;", "start": .1, "end": .9},
            {"id": "R2", "text": "second.", "start": 1.1, "end": 1.9}]}]})
    # Trust-boundary stub for publisher tests ONLY, never a production backend.
    # Separate integration negatives below restore the real Fermat verifier.
    real_verifier = getattr(subject.forced, "verify_production_timings", None)
    raw = root / "test-only-raw.json"
    write(raw, {"test_fixture": True})
    verifier_calls = []
    def verifier(path, *, plan_path, speech):
        verifier_calls.append((path, plan_path, speech))
        value = common.read_json(path)
        for item in value["sources"]:
            if common.sha(item["path"]) != item["sha256"]:
                raise ValueError("Test source drift")
        files = [{"path": str(raw), "sha256": common.sha(raw)}]
        return {"schema_version": 1, "files": files,
                "evidence_sha256": hashlib.sha256(common.canonical(files)).hexdigest()}
    monkeypatch.setattr(subject.forced, "verify_production_timings", verifier, raising=False)
    return dict(root=root, attempt=attempt, original=original, plan=tts_plan, speech=speech, timings=timings,
                calls=calls, course=course, context=context, narration=narration, real_probe=real_probe, real_run=real_run,
                real_verifier=real_verifier, verifier_calls=verifier_calls, raw=raw)


def aligned(project, delivery=None, name="aligned"):
    output = project["root"] / name
    subject.align(delivery or project["original"], project["plan"], project["speech"], project["timings"], output,
                  producer_agent="alignment-producer", producer_context="alignment-producer-context")
    return output / "alignment.json"


def voiced(project, alignment):
    path = project["root"] / "audio-review.json"
    write(path, audio_review(alignment))
    output = project["root"] / "voiced"
    subject.release_voiced(alignment, path, output)
    return output / "delivery.json"


def audio_review(alignment):
    common = subject.common
    value = common.read_json(alignment)
    result = review("audio_alignment", subject.audio_bindings(alignment))
    silent = common.read_json(value["source"]["delivery"])
    frames = common.read_json(Path(silent["attempt"]) / "review-input.json")["frames"]
    result["units"] = []
    for unit, source in zip(value["units"], value["inputs"], strict=True):
        row = {"id": unit["id"], "wav_sha256": source["sha256"], "duration_seconds": unit["duration_seconds"],
               "status": "pass", "references": []}
        for phrase in unit["phrases"]:
            frame = next(frame for frame in frames if phrase["visual_start"] <= frame["time"] < phrase["visual_end"])
            detail = {key: phrase[key] for key in ("id", "focus", "text", "visual_start", "visual_end")}
            detail.update(status="pass", evidence=[{**frame, "video_sha256": value["source"]["video_sha256"],
                                                   "finding": "Test-only static frame at the actual phrase time"}])
            row["references"].append(detail)
        result["units"].append(row)
    return result


def test_new_contract_uses_one_segment_per_unit_and_legacy_cannot_approve(project):
    plan = subject.common.read_json(project["plan"])
    subject.vox.validate_plan(plan)
    assert len(plan["segments"]) == 1 and len(plan["segments"][0]["references"]) == 2
    assert plan["segments"][0]["focus"] == "U1" and plan["source_contract"] == subject.units.SOURCE_CONTRACT
    with pytest.raises(ValueError): subject.legacy.verify_speech_source(plan)
    old = subject.common.read_json(project["original"])
    with pytest.raises(ValueError): subject.legacy.bindings(old["attempt"], old["narration"])


def test_visual_only_revision_reuses_original_plan_and_receipts_but_current_reviews(project):
    before = {p.name: subject.common.sha(p) for p in project["speech"].glob("*") if p.is_file()}
    newer = project["attempt"]("newer", second_start=2.2)
    alignment = aligned(project, newer)
    value = subject.common.read_json(alignment)
    assert value["source"]["delivery"] == str(newer)
    assert value["reuse"]["original_visual_approval_is_current"] is False
    assert value["reuse"]["receipts_rewritten"] is False
    assert subject.audio_bindings(alignment)["current_delivery_sha256"] == subject.common.sha(newer)
    assert before == {p.name: subject.common.sha(p) for p in project["speech"].glob("*") if p.is_file()}


@pytest.mark.parametrize("mutation", ["text", "id", "ref_text", "ref_id", "focus"])
def test_text_or_reference_changes_never_automatically_reuse_tts(project, mutation):
    unit = project["narration"]["units"][0]
    if mutation == "text":
        unit["text"] = "Changed;second."
        unit["references"][0]["text"] = "Changed;"
    if mutation == "id": unit["id"] = "Other"
    if mutation == "ref_text":
        unit["references"][0]["text"] = "First"
        unit["references"][1]["text"] = ";second."
    if mutation == "ref_id": unit["references"][0]["id"] = "Other"
    if mutation == "focus": unit["references"][0]["focus"] = "f2"
    newer = project["attempt"]("changed")
    with pytest.raises(ValueError, match="identical ordered"):
        aligned(project, newer)
    assert not (project["root"] / "aligned").exists()


@pytest.mark.parametrize("mutation", ["plan", "worker", "voice", "model", "settings", "request_voice", "count", "wav", "snapshot", "timing_text", "smoke", "timing_source"])
def test_alignment_revalidates_original_assets_and_estimates(project, mutation):
    common = subject.common
    receipt_path = project["speech"] / "U1.receipt.json"
    receipt = common.read_json(receipt_path)
    if mutation == "plan": receipt["plan_sha256"] = "b" * 64
    if mutation == "worker": receipt["worker_sha256"] = "b" * 64
    if mutation == "voice": receipt["reference_sha256"] = "b" * 64
    if mutation == "model": receipt["engine"]["revision"] = "other"
    if mutation == "settings": receipt["request"]["cfg_value"] = 3
    if mutation == "request_voice": receipt["request"]["reference_wav_path"] = "C:\\wrong.wav"
    if mutation == "count": receipt["segment_call_count"] = 2
    if mutation in {"plan", "worker", "voice", "model", "settings", "request_voice", "count"}:
        replace(receipt_path, receipt)
    if mutation == "wav": (project["speech"] / "U1.wav").write_bytes(b"changed")
    if mutation == "snapshot":
        plan = common.read_json(project["plan"])
        plan["source_snapshot"]["narration"]["text"] += " "
        replace(project["plan"], plan)
    if mutation in {"timing_text", "smoke", "timing_source"}:
        timing = common.read_json(project["timings"])
        if mutation == "timing_text": timing["units"][0]["phrases"][0]["text"] = "wrong"
        if mutation == "smoke": timing["smoke_only"] = True
        if mutation == "timing_source": timing["sources"] = [{"path": str(project["course"]), "sha256": "b" * 64}]
        replace(project["timings"], timing)
    with pytest.raises((ValueError, wave.Error)):
        aligned(project)
    assert not (project["root"] / "aligned").exists()


@pytest.mark.parametrize("what", ["context", "course", "visual_review", "focus", "source_snapshot"])
def test_current_course_and_review_source_drift_invalidates_alignment(project, what):
    alignment = aligned(project)
    silent = subject.common.read_json(project["original"])
    if what in {"context", "course"}: path = project[what]
    elif what == "visual_review": path = Path(silent["visual_review"])
    elif what == "focus": path = Path(silent["attempt"]) / "focus-events.json"
    else: path = Path(silent["narration"])
    path.write_text(path.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError): subject.audio_bindings(alignment)


@pytest.mark.parametrize("stage", ["visual", "narration", "audio_alignment"])
@pytest.mark.parametrize("mutation", ["role", "agent", "binding", "stage", "listening", "blocker", "authorization"])
def test_all_review_stages_are_current_independent_and_honest(project, stage, mutation):
    silent = subject.common.read_json(project["original"])
    if stage == "audio_alignment":
        alignment = aligned(project)
        value = review(stage, subject.audio_bindings(alignment))
    else:
        path = Path(silent["visual_review" if stage == "visual" else "narration_review"])
        value = subject.common.read_json(path)
    if mutation == "role": value["reviewer_role"] = "author"
    if mutation == "agent": value["reviewer_agent"] = " "
    if mutation == "binding": value["bindings"] = {}
    if mutation == "stage": value["stage"] = "another"
    if mutation == "listening": value["listening_reviewed"] = True
    if mutation == "blocker": value["blocking_findings"] = ["not readable"]
    if mutation == "authorization": value["release_authorized"] = False
    path = project["root"] / "invalid-review.json"
    write(path, value)
    with pytest.raises(ValueError):
        if stage == "audio_alignment": subject.release_voiced(alignment, path, project["root"] / "denied")
        else: subject.require_review(silent["attempt"], path, narration=silent["narration"] if stage == "narration" else None)
    assert not (project["root"] / "denied").exists()


def test_final_gate_recomputes_phrase_schedule_and_preserves_wav_bytes(project):
    alignment = aligned(project)
    original_wav = (project["speech"] / "U1.wav").read_bytes()
    result = subject.common.read_json(voiced(project, alignment))
    assert result["listening_reviewed"] is False and result["caption_status"] == "none"
    with wave.open(str(project["root"] / "voiced/voice-mix.wav"), "rb") as mix:
        pcm = mix.readframes(mix.getnframes())
    with wave.open(str(project["speech"] / "U1.wav"), "rb") as audio:
        source_pcm = audio.readframes(audio.getnframes())
    start = round(subject.common.read_json(alignment)["units"][0]["start"] * 48000)
    assert pcm[start * 2:start * 2 + len(source_pcm)] == source_pcm
    assert original_wav == (project["speech"] / "U1.wav").read_bytes()
    value = subject.common.read_json(alignment)
    value["units"][0]["start"] += .1
    replace(alignment, value)
    with pytest.raises(ValueError, match="per-phrase"):
        subject.audio_bindings(alignment)


def captioned_candidate(project):
    alignment = aligned(project)
    delivery = voiced(project, alignment)
    candidate = project["root"] / "candidate"
    subject.caption_candidate(alignment, delivery, candidate, {"max_width": 8},
        producer_agent="caption-author", producer_context="caption-author-context")
    frame = project["root"] / "caption-frame.png"
    frame.write_bytes(b"mock independent pixel evidence")
    value = review("captions", subject.caption_bindings(candidate))
    value["checks"] = {name: {"status": "pass", "evidence": [{"finding": "actual candidate"}]}
                       for name in ("layout", "text_consistency", "frame_evidence")}
    value["checks"]["frame_evidence"]["evidence"][0].update(time=1, path=str(frame), sha256=subject.common.sha(frame))
    return candidate, value


def test_single_burned_caption_set_copies_audio_no_restarts_no_sidecars(project):
    candidate, value = captioned_candidate(project)
    path = project["root"] / "caption-review.json"
    write(path, value)
    output = project["root"] / "captioned"
    result = subject.release_captioned(candidate, path, output)
    assert {p.name for p in output.iterdir()} == {"captioned.mp4", "delivery.json"}
    assert result["caption_status"] == "single_burned_set" and result["listening_reviewed"] is False
    command = next(command for command in project["calls"] if "-vf" in command)
    assert "-sn" in command and "-dn" in command and "-af" not in command and "-t" not in command
    assert command[command.index("-c:a") + 1] == "copy"
    data = subject.common.read_json(candidate / "captions.json")
    rows = subject.common.read_json(project["root"] / "aligned/alignment.json")["units"]
    assert "".join(event["text"] for event in data["events"]) == rows[0]["text"]
    for phrase in rows[0]["phrases"]:
        events = [event for event in data["events"] if event["reference_id"] == phrase["id"]]
        assert "".join(event["text"] for event in events) == phrase["text"]
        assert all(event["start_cs"] / 100 >= phrase["visual_start"] - 1e-8
                   and event["end_cs"] / 100 <= phrase["visual_end"] + 1e-8 for event in events)
    with pytest.raises(FileExistsError): subject.release_captioned(candidate, path, output)
    with pytest.raises(ValueError, match="uncaptioned"):
        subject.caption_candidate(project["root"] / "aligned/alignment.json", output / "delivery.json", project["root"] / "twice",
                                  producer_agent="caption-author", producer_context="caption-author-context")


def test_caption_line_approximations_are_local_to_actual_phrase_not_unit():
    first, second = "甲乙丙丁戊己庚辛壬癸" * 3, "尾句"
    value = {"duration": 20, "units": [{"id": "unit", "text": first + second,
        "start": 0, "end": 18, "duration_seconds": 18, "phrases": [
            {"id": "a", "text": first, "visual_start": 2.123, "visual_end": 4.567},
            {"id": "b", "text": second, "visual_start": 15.123, "visual_end": 16.567}]}]}
    result = subject._caption_data(value, {"max_width": 8})
    first_events = [event for event in result["events"] if event["reference_id"] == "a"]
    assert len(first_events) > 1 and "".join(event["text"] for event in first_events) == first
    assert first_events[0]["start_cs"] == 213 and first_events[-1]["end_cs"] == 456
    assert all(event["timing"] == "character_ratio_within_forced_aligned_phrase" for event in first_events)
    assert result["events"][-1]["start_cs"] == 1513 and result["events"][-1]["end_cs"] == 1656
    assert result["events"][-1]["timing"] == "model_estimated_forced_alignment_phrase"
    assert "".join(event["text"] for event in result["events"]) == first + second
    assert all(a["end_cs"] <= b["start_cs"] for a, b in zip(result["events"], result["events"][1:]))


@pytest.mark.parametrize("mutation", ["author", "listening", "binding", "frame", "sidecar", "ass", "double_track"])
def test_caption_gate_keeps_independent_pixel_review_and_single_subtitle_set(project, monkeypatch, mutation):
    candidate, value = captioned_candidate(project)
    if mutation == "author": value["reviewer_agent"] = "caption-author"
    if mutation == "listening": value["listening_reviewed"] = True
    if mutation == "binding": value["bindings"] = {}
    if mutation == "frame": value["checks"]["frame_evidence"]["evidence"][0]["sha256"] = "b" * 64
    if mutation == "sidecar": (candidate / "candidate.zh.srt").write_text("duplicate captions")
    if mutation == "ass": (candidate / "support/captions.ass").write_text("changed")
    if mutation == "double_track":
        original = subject.pilot.probe
        def probe(path):
            info = original(path)
            info["streams"].append({"codec_type": "subtitle"})
            return info
        monkeypatch.setattr(subject.pilot, "probe", probe)
    path = project["root"] / "bad-caption-review.json"
    write(path, value)
    with pytest.raises(ValueError): subject.release_captioned(candidate, path, project["root"] / "denied")
    assert not (project["root"] / "denied").exists()


def test_all_outputs_create_only(project):
    alignment = aligned(project)
    before = alignment.read_bytes()
    with pytest.raises(FileExistsError): aligned(project)
    assert alignment.read_bytes() == before
    plan = subject.common.read_json(project["plan"])
    with pytest.raises(FileExistsError): subject.speech_plan(project["original"], plan["reference_source"], project["plan"])
    silent = subject.common.read_json(project["original"])
    with pytest.raises(FileExistsError): subject.install_narration(silent["attempt"], project["root"] / "original-draft.json",
        silent["visual_review"], silent["narration"])


def test_dangling_output_symlink_is_not_an_empty_output(project):
    path = project["root"] / "existing-link"
    path.symlink_to(project["root"] / "missing")
    with pytest.raises(FileExistsError):
        subject.align(project["original"], project["plan"], project["speech"], project["timings"], path,
                      producer_agent="alignment-producer", producer_context="alignment-producer-context")
    assert path.is_symlink() and not (project["root"] / "missing").exists()


@pytest.mark.parametrize("mutation", ["pass", "lost", "terminal_only", "stale", "same_reviewer"])
def test_new_publisher_retains_actual_independent_content_regression_gate(project, monkeypatch, mutation):
    common = subject.common
    silent = common.read_json(project["original"])
    attempt = Path(silent["attempt"])
    baseline = project["root"] / "baseline.mp4"
    baseline.write_bytes(b"hash-only baseline fixture")
    contract = project["root"] / "regression-contract.json"
    write(contract, {"schema_version": 1, "assets": {"old": {"path": str(baseline), "sha256": common.sha(baseline), "duration": 8}},
        "units": [{"id": "reason", "asset": "old", "function": "preserve reasoning", "baseline_interval": [1, 4],
                   "features": [{"id": "motion", "kind": "process", "claim": "variable continuity"}]}]})
    current = {"fixture": "current-new-publisher"}
    comparison_path = project["root"] / "regression-review.json"
    comparison = review("content_regression", current)
    comparison["units"] = [{"id": "reason", "features": [{"id": "motion", "outcome": "retained", "evidence": [
        {"phase": phase, "time": time, "finding": "fixture observation"}
        for phase, time in (("before", 1), ("during", 2), ("after", 3))]}]}]
    if mutation == "lost": comparison["units"][0]["features"][0]["outcome"] = "lost"
    if mutation == "terminal_only": comparison["units"][0]["features"][0]["evidence"] = comparison["units"][0]["features"][0]["evidence"][-1:]
    if mutation == "stale": comparison["bindings"] = {}
    if mutation == "same_reviewer": comparison["reviewer_agent"] = "independent-visual"
    write(comparison_path, comparison)
    plan = common.read_json(attempt / "plan.json")
    plan.update(revision_mode="revision", revision_contract=str(contract), revision_review=str(comparison_path))
    replace(attempt / "plan.json", plan)
    monkeypatch.setattr(subject, "bindings", lambda *a, **kw: current)
    path = project["root"] / "new-visual-review.json"
    write(path, review("visual", current))
    if mutation == "pass":
        assert subject.require_review(attempt, path)["status"] == "pass"
    else:
        with pytest.raises(ValueError): subject.require_review(attempt, path)


def test_actual_ffmpeg_mix_burn_copy_decode_and_visible_caption_pixels(project, monkeypatch):
    from PIL import Image, ImageChops

    run = project["real_run"]
    filters = run([subject.pilot.FFMPEG, "-hide_banner", "-filters"])
    if " ass " not in filters:
        pytest.skip("Local FFmpeg has no libass")
    source = project["root"] / "native.mp4"
    run([subject.pilot.FFMPEG, "-v", "error", "-n", "-f", "lavfi", "-i",
         "color=c=0x101416:s=1920x1080:r=30:d=8", "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-an", source], timeout=120)
    monkeypatch.setattr(subject.pilot, "run", run)
    monkeypatch.setattr(subject.pilot, "probe", project["real_probe"])
    delivery = project["attempt"]("real", video_source=source)
    alignment = aligned(project, delivery)
    voiced_delivery = voiced(project, alignment)
    candidate = project["root"] / "real-candidate"
    subject.caption_candidate(alignment, voiced_delivery, candidate,
                              producer_agent="caption-author", producer_context="caption-author-context")
    voiced_video = subject.common.read_json(voiced_delivery)["video"]
    frames = []
    for name, video in (("bare", voiced_video), ("caption", candidate / "candidate.mp4")):
        frame = project["root"] / f"{name}-actual.png"
        run([subject.pilot.FFMPEG, "-v", "error", "-n", "-ss", "1.3", "-i", video,
             "-frames:v", "1", "-update", "1", frame], timeout=60)
        frames.append(frame)
    with Image.open(frames[0]) as bare, Image.open(frames[1]) as caption:
        assert ImageChops.difference(bare, caption).crop((0, 900, 1920, 1080)).getbbox() is not None
    assert subject.captions._audio_hash(voiced_video) == subject.captions._audio_hash(candidate / "candidate.mp4")
    current = subject.caption_bindings(candidate)
    value = review("captions", current)
    value["checks"] = {name: {"status": "pass", "evidence": [{"finding": "Test fixture pixels, not a lesson review"}]}
                       for name in ("layout", "text_consistency", "frame_evidence")}
    value["checks"]["frame_evidence"]["evidence"][0].update(
        time=1.3, path=str(frames[1]), sha256=subject.common.sha(frames[1]))
    path = project["root"] / "real-caption-review.json"
    write(path, value)
    result = subject.release_captioned(candidate, path, project["root"] / "real-playback")
    assert result["full_decode_passed"] is True and result["listening_reviewed"] is False


def test_opt_in_word_caption_manifest_binds_helper_and_rejects_drift(project):
    estimates = subject.common.read_json(project["timings"])
    for phrase in estimates["units"][0]["phrases"]:
        phrase["words"] = [{"word": phrase["text"], "start": phrase["start"], "end": phrase["end"]}]
    replace(project["timings"], estimates)
    alignment = aligned(project)
    delivery = voiced(project, alignment)
    candidate = project["root"] / "word-caption-candidate"
    subject.caption_candidate(alignment, delivery, candidate, producer_agent="caption-author",
                              producer_context="caption-author-context", timing_mode="word_estimates")
    current = subject.caption_bindings(candidate)
    assert current["word_caption_tools_sha256"] == subject.common.sha(subject.word_captions.__file__)
    data = subject.common.read_json(candidate / "captions.json")
    assert all(event["timing"] == "model_estimated_word_group" for event in data["events"])
    manifest = subject.common.read_json(candidate / "candidate.json")
    manifest["word_caption_tools_sha256"] = "0" * 64
    replace(candidate / "candidate.json", manifest)
    with pytest.raises(ValueError, match="Word-caption timing tools changed"):
        subject.caption_bindings(candidate)


def test_cli_accepts_every_required_command_and_flag(monkeypatch, capsys):
    examples = {"bindings": ["--attempt", "a", "--narration", "n"],
        "install-narration": ["--attempt", "a", "--draft", "d", "--visual-review", "v", "--output", "o"],
        "release-silent": ["--attempt", "a", "--narration", "n", "--visual-review", "v", "--narration-review", "r", "--output", "o"],
        "speech-plan": ["--delivery", "d", "--reference", "r", "--output", "o"],
        "align": ["--delivery", "d", "--plan", "p", "--speech", "s", "--timings", "t", "--output", "o",
                  "--producer-agent", "author", "--producer-context", "context"],
        "audio-bindings": ["--alignment", "a"], "release-voiced": ["--alignment", "a", "--review", "r", "--output", "o"],
        "caption-candidate": ["--alignment", "a", "--delivery", "d", "--output", "o",
                              "--producer-agent", "author", "--producer-context", "context"],
        "caption-bindings": ["--candidate", "c"], "release-captioned": ["--candidate", "c", "--review", "r", "--output", "o"]}
    for command, flags in examples.items():
        monkeypatch.setattr(subject, command.replace("-", "_"), lambda *a, **kw: {"called": True})
        subject.main([command, *flags])
        assert json.loads(capsys.readouterr().out) == {"called": True}


def test_publisher_must_call_producer_verifier_with_explicit_original_inputs(project):
    alignment = aligned(project)
    calls = len(project["verifier_calls"])
    subject.audio_bindings(alignment)
    assert len(project["verifier_calls"]) > calls
    assert all(Path(p) == project["timings"] and Path(plan) == project["plan"] and Path(speech) == project["speech"]
               for p, plan, speech in project["verifier_calls"])


@pytest.mark.parametrize("stage", ["alignment", "voiced", "captions"])
def test_every_publication_stage_rejects_drift_in_aligner_returned_raw_evidence(project, stage):
    alignment = aligned(project)
    if stage == "voiced":
        path = project["root"] / "full-audio-review.json"
        write(path, audio_review(alignment))
    if stage == "captions":
        delivery = voiced(project, alignment)
    replace(project["raw"], {"test_fixture": True, "modified": True})
    with pytest.raises(ValueError, match="provenance"):
        if stage == "alignment": subject.audio_bindings(alignment)
        if stage == "voiced": subject.release_voiced(alignment, path, project["root"] / "denied")
        if stage == "captions": subject.caption_candidate(alignment, delivery, project["root"] / "denied",
            producer_agent="caption-author", producer_context="caption-author-context")
    assert not (project["root"] / "denied").exists()


def test_real_producer_verifier_refuses_handwritten_or_incomplete_timing_labels(project, monkeypatch):
    assert callable(project["real_verifier"]), "Fermat's production verifier must be present before freeze"
    monkeypatch.setattr(subject.forced, "verify_production_timings", project["real_verifier"])
    with pytest.raises(ValueError): aligned(project)
    assert not (project["root"] / "aligned").exists()


def test_real_injected_backend_output_never_becomes_production_input(project, monkeypatch):
    assert callable(project["real_verifier"])
    monkeypatch.setattr(subject.forced, "verify_production_timings", project["real_verifier"])
    plan = subject.common.read_json(project["plan"])
    calls = []
    class FakeBackend:
        def __init__(self, **kwargs):
            self.identity = {"backend": "FAKE-NO-MODEL", "model": kwargs}

        def align(self, **request):
            calls.append(request)
            return {"segments": [{"text": ref["text"], "start": start, "end": end}
                for ref, start, end in zip(plan["segments"][0]["references"], (.1, 1.1), (.9, 1.9), strict=True)]}

    output = project["root"] / "fake-test-timings.json"
    result = subject.forced.align_plan(project["plan"], project["speech"], output, backend_factory=FakeBackend)
    assert len(calls) == 1 and result["test_only"] is True
    project["timings"] = output
    with pytest.raises(ValueError): aligned(project)
    # Even relabeling the outer flag must not hide fake software/raw provenance.
    result["test_only"] = False
    replace(output, result)
    with pytest.raises(ValueError): aligned(project)
    assert not (project["root"] / "aligned").exists()


@pytest.mark.parametrize("stage", ["visual", "narration", "audio_alignment", "captions"])
@pytest.mark.parametrize("conflict", ["author_agent", "author_context", "missing_context", "prior_context"])
def test_declared_independence_cannot_hide_authorship_or_reused_context(project, stage, conflict):
    silent = subject.common.read_json(project["original"])
    if stage in {"visual", "narration"}:
        current = subject.bindings(silent["attempt"], silent["narration"] if stage == "narration" else None)
        value = review(stage, current)
        author = ("visual-author", "visual-author-context") if stage == "visual" else ("narration-author", "narration-author-context")
    elif stage == "audio_alignment":
        alignment = aligned(project)
        value = audio_review(alignment)
        author = ("alignment-producer", "alignment-producer-context")
    else:
        candidate, value = captioned_candidate(project)
        author = ("caption-author", "caption-author-context")
    if conflict == "author_agent": value["reviewer_agent"] = author[0]
    if conflict == "author_context": value["reviewer_context"] = author[1]
    if conflict == "missing_context": value.pop("reviewer_context")
    if conflict == "prior_context":
        value["reviewer_context"] = "visual-author-context" if stage == "visual" else "new-review-context-visual"
    path = project["root"] / "self-or-reused-review.json"
    write(path, value)
    with pytest.raises(ValueError):
        if stage in {"visual", "narration"}:
            subject.require_review(silent["attempt"], path, narration=silent["narration"] if stage == "narration" else None)
        if stage == "audio_alignment": subject.release_voiced(alignment, path, project["root"] / "denied")
        if stage == "captions": subject.release_captioned(candidate, path, project["root"] / "denied")
    assert not (project["root"] / "denied").exists()


def test_narrator_cannot_be_the_visual_first_look_reviewer(project):
    project["narration"]["author_agent"] = "independent-visual"
    with pytest.raises(ValueError, match="first-look"):
        project["attempt"]("self-authored")
    assert not (project["root"] / "self-authored-narration.json").exists()


@pytest.mark.parametrize("mutation", ["missing_author", "missing_context", "relabel_author"])
def test_narration_identity_is_required_and_kept_with_original_draft(project, mutation):
    silent = subject.common.read_json(project["original"])
    path = Path(silent["narration"])
    narration = subject.common.read_json(path)
    if mutation == "missing_author": narration.pop("author_agent")
    if mutation == "missing_context": narration.pop("author_context")
    if mutation == "relabel_author": narration["author_agent"] = "someone-else"
    replace(path, narration)
    with pytest.raises(ValueError): subject.bindings(silent["attempt"], path)


@pytest.mark.parametrize("field", ["author_agent", "author_context"])
def test_missing_visual_author_identity_cannot_be_approved(project, field):
    silent = subject.common.read_json(project["original"])
    path = Path(silent["attempt"]) / "plan.json"
    plan = subject.common.read_json(path)
    plan.pop(field)
    replace(path, plan)
    with pytest.raises(ValueError, match="author"):
        subject.require_review(silent["attempt"], silent["visual_review"])


@pytest.mark.parametrize("stage", ["alignment", "caption"])
def test_producer_identity_is_required_instead_of_a_fabricated_default(project, stage):
    output = project["root"] / "missing-producer"
    with pytest.raises(ValueError, match="producer"):
        if stage == "alignment":
            subject.align(project["original"], project["plan"], project["speech"], project["timings"], output)
        else:
            subject.caption_candidate(project["root"] / "irrelevant-alignment", project["root"] / "irrelevant-delivery", output)
    assert not output.exists()


def test_same_reviewer_agent_may_review_later_stage_only_in_a_fresh_context(project):
    alignment = aligned(project)
    value = audio_review(alignment)
    value["reviewer_agent"] = "independent-visual"
    path = project["root"] / "same-agent-fresh-context.json"
    write(path, value)
    assert subject.require_audio_review(alignment, path)["review_sha256"] == subject.common.sha(path)


@pytest.mark.parametrize("mutation", ["bare", "missing_reference", "extra_reference", "wrong_wav", "wrong_focus", "wrong_text",
    "wrong_interval", "out_of_phrase", "no_frames", "stale_frame", "wrong_video", "nonimage", "wrong_size", "unrelated_pixels",
    "student_certification", "naturalness_certification", "pronunciation_certification", "asr_certification"])
def test_audio_review_requires_every_actual_reference_and_current_pixel_evidence(project, monkeypatch, mutation):
    alignment = aligned(project)
    value = audio_review(alignment)
    row = value["units"][0]
    detail = row["references"][0]
    frame = detail["evidence"][0]
    if mutation == "bare": value.pop("units")
    if mutation == "missing_reference": row["references"].pop()
    if mutation == "extra_reference": row["references"].append(copy.deepcopy(detail))
    if mutation == "wrong_wav": row["wav_sha256"] = "c" * 64
    if mutation == "wrong_focus": detail["focus"] = "other"
    if mutation == "wrong_text": detail["text"] = "other"
    if mutation == "wrong_interval": detail["visual_end"] += 1
    if mutation == "out_of_phrase": frame["time"] = 7
    if mutation == "no_frames": detail["evidence"] = []
    if mutation == "stale_frame": frame["sha256"] = "c" * 64
    if mutation == "wrong_video": frame["video_sha256"] = "c" * 64
    if mutation in {"nonimage", "wrong_size", "unrelated_pixels"}:
        from PIL import Image
        file = project["root"] / "unrelated.png"
        if mutation == "nonimage": file.write_bytes(b"not a frame")
        else: Image.new("RGB", (8, 8) if mutation == "wrong_size" else (1920, 1080), "red").save(file)
        frame.update(path=str(file), sha256=subject.common.sha(file))
        if mutation == "unrelated_pixels":
            monkeypatch.setattr(subject, "_frame_pixels", lambda path, time=None: "c" * 64 if time is None else "d" * 64)
    if mutation == "student_certification": value["student_tested"] = True
    if mutation == "naturalness_certification": value["naturalness_approved"] = True
    if mutation == "pronunciation_certification": value["pronunciation_approved"] = True
    if mutation == "asr_certification": value["asr_accuracy_certified"] = True
    value["quality_total"] = 1000  # A score never replaces a missing observation.
    path = project["root"] / "bare-or-false-audio-review.json"
    write(path, value)
    with pytest.raises(ValueError): subject.release_voiced(alignment, path, project["root"] / "denied")
    assert not (project["root"] / "denied").exists()


def test_verified_extra_png_frame_can_cover_a_phrase_not_sampled_at_render_time(project, monkeypatch):
    alignment = aligned(project)
    value = audio_review(alignment)
    frame = value["units"][0]["references"][0]["evidence"][0]
    copied = project["root"] / "extra-lossless-frame.png"
    shutil.copyfile(frame["path"], copied)
    frame.update(path=str(copied), sha256=subject.common.sha(copied))
    calls = []
    monkeypatch.setattr(subject, "_frame_pixels", lambda path, time=None: calls.append((path, time)) or "a" * 64)
    path = project["root"] / "extra-frame-review.json"
    write(path, value)
    assert subject.require_audio_review(alignment, path)["frame_sha256"][str(copied)] == subject.common.sha(copied)
    assert len(calls) == 2 and calls[1][1] == frame["time"]


def test_approved_audio_frame_drift_invalidates_subsequent_captions(project):
    alignment = aligned(project)
    delivery = voiced(project, alignment)
    report = subject.common.read_json(subject.common.read_json(delivery)["review"])
    frame = report["units"][0]["references"][0]["evidence"][0]
    Path(frame["path"]).write_bytes(b"changed pixels after audio approval")
    with pytest.raises(ValueError): subject.caption_candidate(alignment, delivery, project["root"] / "denied",
        producer_agent="caption-author", producer_context="caption-author-context")
    assert not (project["root"] / "denied").exists()


def test_first_look_cannot_be_swapped_after_narration_to_reuse_a_review_context(project):
    silent = subject.common.read_json(project["original"])
    substitute = project["root"] / "substitute-first-look.json"
    write(substitute, subject.common.read_json(silent["visual_review"]))
    with pytest.raises(ValueError, match="exact independent first look"):
        subject.release_silent(silent["attempt"], silent["narration"], substitute, silent["narration_review"], project["root"] / "denied")
    changed = project["root"] / "substituted-delivery.json"
    write(changed, {**silent, "visual_review": str(substitute), "visual_review_sha256": subject.common.sha(substitute)})
    with pytest.raises(ValueError): subject.verify_delivery(changed)
    assert not (project["root"] / "denied").exists()


def test_relabeling_reviewer_agent_cannot_disagree_with_declared_agent_id(project):
    alignment = aligned(project)
    value = audio_review(alignment)
    value["agentID"] = "alignment-producer"
    path = project["root"] / "relabeled-agent-review.json"
    write(path, value)
    with pytest.raises(ValueError, match="identity aliases"):
        subject.release_voiced(alignment, path, project["root"] / "denied")
