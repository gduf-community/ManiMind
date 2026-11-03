"""Protocol-only fixtures. No FFmpeg/GL/TTS and no actual media approval."""

import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest

from manimind.postproduce import chapter_package as subject


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def uid():
    return str(uuid4())


def native(duration):
    return {"streams": [
        {"codec_type": "video", "codec_name": "h264", "profile": "High", "width": 1920,
         "height": 1080, "avg_frame_rate": "30/1", "pix_fmt": "yuv420p", "duration": str(duration),
         "start_time": "0", "nb_frames": str(round(duration * 30))},
        {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 1,
         "duration": str(duration), "start_time": "0"}]}


@pytest.fixture
def chapter(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject.pilot, "ROOT", root)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Desktop").mkdir()
    catalogue = root / "catalogue.csv"
    catalogue.write_text("id,module,title,role,requires,new_understanding,reuse,exit_check,split_hint\n"
                         "M01,math,change,core,,new,old,explain,none\n")
    lessons = [{"project_id": f"lesson-{i}", "title": f"Lesson {i}", "catalogue_ids": ["M01"],
                "new_understanding": f"New {i}", "exit_task": f"Explain {i}", "handoff": f"Bridge {i}"}
               for i in range(1, 9)]
    unit = root / "runtime/projects/chapter/unit-v001.json"
    base = {"schema_version": 1, "unit_id": "chapter", "title": "Chapter", "catalogue": "catalogue.csv",
            "audience": "beginner", "scope": "all eight", "lessons": lessons}
    old = root / "runtime/projects/old/unit.json"
    write(old, {**base, "unit_id": "old", "lessons": lessons[:1]})
    write(unit, base)
    deliveries, science, candidates = [], [], {}
    source_author, prior_reviewer = uid(), uid()
    for i, lesson in enumerate(lessons, 1):
        project = root / "runtime/projects" / lesson["project_id"]
        context = project / "context.json"
        subject.curriculum.write_context(old if i == 1 else unit, lesson["project_id"], context, root)
        brief = project / "science.json"
        write(brief, {"conditions": [f"domain-{i}"]})
        scene = root / "examples" / f"scene{i}.py"
        scene.parent.mkdir(exist_ok=True)
        scene.write_text("VALUE = 1\n")
        attempt = root / "outputs" / lesson["project_id"] / "visual"
        write(attempt / "plan.json", {"project_id": lesson["project_id"], "scene": str(scene.relative_to(root)),
              "lesson_context": str(context.relative_to(root)), "author_agent": source_author,
              "author_context": source_author})
        write(attempt / "render.json", {"input_hashes": {str(p): subject.common.sha(p) for p in (scene, brief)}})
        narration = project / "narration.json"
        review = project / "visual-review.json"
        write(narration, {"units": ["test-only"]})
        write(review, {"status": "pass", "reviewer_agent": prior_reviewer, "reviewer_context": prior_reviewer})
        silent = attempt.parent / "silent/delivery.json"
        write(silent, {"attempt": str(attempt), "narration": str(narration),
                       "visual_review": str(review), "narration_review": str(review)})
        alignment = attempt.parent / "alignment/alignment.json"
        write(alignment, {"source": {"delivery": str(silent)}})
        voiced = attempt.parent / "voiced/delivery.json"
        write(voiced, {"review": str(review)})
        candidate = attempt.parent / "caption-candidate"
        write(candidate / "candidate.json", {"alignment": str(alignment), "voiced_delivery": str(voiced)})
        (candidate / "candidate.mp4").write_bytes(f"TEST-ONLY lesson media {i}".encode())
        for name in subject.unit.captions.ARTIFACTS:
            asset = candidate / name
            if not asset.exists():
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(b"TEST-ONLY caption artifact")
        bindings = {"candidate": str(candidate), "files": {"candidate.mp4": subject.common.sha(candidate / "candidate.mp4")}}
        candidates[str(candidate)] = bindings
        target = attempt.parent / ("captioned-v007" if i == 1 else "captioned-v001")
        target.mkdir()
        (target / "captioned.mp4").write_bytes((candidate / "candidate.mp4").read_bytes())
        delivery = {"video": str(target / "captioned.mp4"), "sha256": bindings["files"]["candidate.mp4"],
                    "bindings": bindings, "duration": i, "review": str(review), "review_sha256": subject.common.sha(review),
                    "caption_status": "single_burned_set", "full_decode_passed": True, "listening_reviewed": False}
        write(target / "delivery.json", delivery)
        deliveries.append(str(target / "delivery.json"))
        science.append(str(brief))
    base["existing_first_lesson"] = {"source_unit": str(old.relative_to(root)),
            "delivery": str(Path(deliveries[0]).relative_to(root)),
            "video_sha256": json.loads(Path(deliveries[0]).read_text())["sha256"]}
    write(unit, base)
    # New-unit contexts must bind the final unit bytes, unlike the historical first context.
    for lesson in lessons[1:]:
        context = root / "runtime/projects" / lesson["project_id"] / "context.json"
        context.unlink()
        subject.curriculum.write_context(unit, lesson["project_id"], context, root)
    monkeypatch.setattr(subject.unit, "caption_bindings", lambda path: copy.deepcopy(candidates[str(path)]))
    monkeypatch.setattr(subject.unit, "verify_delivery", lambda path: subject.common.read_json(path))
    monkeypatch.setattr(subject.opening, "_body", lambda path: (subject.common.read_json(path),
        [(source_author, source_author)], [{"reviewer_agent": prior_reviewer, "reviewer_context": prior_reviewer}]))
    calls = []
    def release(candidate, review, target):
        calls.append(("release_captioned", str(candidate), str(review), str(target)))
        target.mkdir(parents=True, exist_ok=False)
        video = target / "captioned.mp4"
        video.write_bytes((Path(candidate) / "candidate.mp4").read_bytes())
        result = {"video": str(video), "sha256": subject.common.sha(video), "bindings": candidates[str(candidate)],
                  "review_sha256": subject.common.sha(review)}
        write(target / "delivery.json", result)
        return result
    monkeypatch.setattr(subject.unit, "release_captioned", release)
    monkeypatch.setattr(subject.unit, "_frame_pixels", lambda *args: "test-only-identical-pixels")
    def run(command, timeout=180):
        calls.append(("ffmpeg", list(command), timeout))
        if "-filter_complex" in command or "-frames:v" in command:
            Path(command[-1]).write_bytes(b"TEST-ONLY encoded video or frame")
        return ""
    monkeypatch.setattr(subject.pilot, "run", run)
    def probe(path):
        name = Path(path).parent.name
        duration = int(name.split("-lesson-")[-1]) if "-lesson-" in name else 36
        return native(duration)
    monkeypatch.setattr(subject.pilot, "probe", probe)
    actors = {f"{role}_{kind}": uid() for role in ("author", "main", "adapter") for kind in ("agent", "context")}
    monkeypatch.setenv("CODEX_THREAD_ID", actors["adapter_agent"])
    request = root / "request.json"
    write(request, {"chapter_id": "chapter", "version": "v001", "unit": str(unit), "deliveries": deliveries,
                    "science": science, "actors": actors})
    return {"root": root, "request": request, "calls": calls, "actors": actors,
            "desktop": tmp_path / "Desktop/new-chapter", "prior_reviewer": prior_reviewer}


def evidence(root, video, time):
    image = root / "review-pixel.png"
    image.write_bytes(b"TEST-ONLY mocked pixels")
    return {**subject._receipt(image), "video_sha256": video["sha256"], "time": time,
            "finding": "Protocol fixture observation, not a real media finding"}


def review(chapter, plan_path, stage="chapter_assembly", packet=None):
    plan = subject.common.read_json(plan_path)
    current = subject.bindings(plan_path) if packet is None else packet
    value = {"stage": stage, "status": "pass", "bindings": current, "reviewer_role": "independent",
             "reviewer_agent": uid(), "reviewer_context": uid(), "release_authorized": True,
             "blocking_findings": [], "listening_reviewed": False, "listening_status": "not_performed",
             "student_tested": False, "lessons": []}
    for index, source in enumerate(plan["sources"]):
        video = plan["verified"][index]["video"] if packet is None else packet["video"]
        time = .1 if packet is None else packet["segments"][index]["interval"][0] + .1
        names = ("coverage", "handoff", "source_completeness") if packet is None else (
            "full_lesson", "captions", "av_continuity")
        value["lessons"].append({"project_id": source["project_id"], "source_delivery": source["source_delivery"],
            "science": source["science"], "checks": {name: {"status": "pass", "conditions": ["Test-only domain condition"],
            "evidence": [evidence(chapter["root"], video, time)]} for name in names}})
    if packet:
        value["boundaries"] = [{**boundary, "checks": {"seam": {"status": "pass", "conditions": ["Both sides"],
            "evidence": [{**boundary[label], "finding": "Test-only seam observation"} for label in ("before", "after")]}}}
            for boundary in packet["boundaries"]]
    path = chapter["root"] / "runtime/sessions" / f"{stage}.json"
    write(path, value)
    return path


def assembled(chapter):
    plan = subject.prepare(chapter["request"])
    assembly = review(chapter, plan)
    packet = subject.assemble(plan, assembly)
    return plan, assembly, packet


@pytest.mark.parametrize("change", ["one", "duplicate", "order", "wrong-context", "candidate"])
def test_incomplete_or_wrong_sources_cannot_prepare(chapter, change):
    path = chapter["request"]
    request = subject.common.read_json(path)
    if change == "one":
        request["deliveries"] = request["deliveries"][:1]
    elif change == "duplicate":
        request["deliveries"][1] = request["deliveries"][0]
    elif change == "order":
        request["deliveries"][1:3] = request["deliveries"][1:3][::-1]
    else:
        delivery = Path(request["deliveries"][1])
        value = subject.common.read_json(delivery)
        if change == "candidate":
            value["caption_status"] = "candidate_not_released"
            write(delivery, value)
        else:
            context = chapter["root"] / "runtime/projects/lesson-2/context.json"
            data = subject.common.read_json(context)
            data["current_lesson"]["project_id"] = "lesson-3"
            write(context, data)
    write(path, request)
    with pytest.raises(ValueError):
        subject.prepare(path)
    assert not chapter["calls"]


def test_prepare_revalidates_all_eight_without_approval_and_rejects_replay(chapter):
    plan = subject.prepare(chapter["request"])
    assert len(chapter["calls"]) == 8
    value = subject.common.read_json(plan)
    assert value["status"] == "prepared_not_approved"
    assert not (Path(value["output"]) / "candidate").exists()
    assert Path(value["sources"][0]["source_unit"]["path"]).name == "unit.json"
    for source, verified in zip(value["sources"], value["verified"]):
        assert Path(source["video"]["path"]).read_bytes() == Path(verified["video"]["path"]).read_bytes()
    with pytest.raises(FileExistsError):
        subject.prepare(chapter["request"])


@pytest.mark.parametrize("target", ["source_delivery", "review", "science", "examples", "code", "verified"])
def test_drift_invalidates_plan(chapter, monkeypatch, target):
    plan = subject.prepare(chapter["request"])
    value = subject.common.read_json(plan)
    source = value["sources"][0]
    if target == "code":
        monkeypatch.setattr(subject, "_code", lambda: [])
    elif target == "examples":
        (chapter["root"] / "examples/scene1.py").write_text("VALUE = 2\n")
    elif target == "verified":
        Path(value["verified"][0]["video"]["path"]).write_bytes(b"drift")
    else:
        path = Path(source[target]["path"])
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        subject.bindings(plan)


@pytest.mark.parametrize("mutation", ["self", "main", "source-author", "old-context", "old-stage", "one-lesson", "no-evidence", "no-conditions", "non-uuid"])
def test_independent_assembly_gate(chapter, mutation):
    plan = subject.prepare(chapter["request"])
    path = review(chapter, plan)
    data = subject.common.read_json(path)
    if mutation in {"self", "main"}:
        data["reviewer_agent"] = chapter["actors"][("author" if mutation == "self" else "main") + "_agent"]
    elif mutation == "source-author":
        data["reviewer_agent"] = subject.common.read_json(plan)["sources"][0]["authors"][0][0]
    elif mutation == "old-context":
        data["reviewer_context"] = chapter["prior_reviewer"]
    elif mutation == "old-stage":
        data["stage"] = "captions"
    elif mutation == "one-lesson":
        data["lessons"] = data["lessons"][:1]
    elif mutation == "non-uuid":
        data["reviewer_agent"] = "independent-reviewer"
    else:
        data["lessons"][5]["checks"]["coverage"]["evidence" if mutation == "no-evidence" else "conditions"] = []
    write(path, data)
    with pytest.raises(ValueError):
        subject.assemble(plan, path)
    assert all(call[0] != "ffmpeg" for call in chapter["calls"])


def test_candidate_full_concat_is_not_release(chapter):
    plan, assembly, packet = assembled(chapter)
    assert packet["status"] == "candidate_not_released"
    assert len(packet["segments"]) == 8 and len(packet["boundaries"]) == 7
    assert not chapter["desktop"].exists()
    command = next(call[1] for call in chapter["calls"] if call[0] == "ffmpeg" and "-filter_complex" in call[1])
    filters = command[command.index("-filter_complex") + 1]
    assert command.count("-i") == 8 and "concat=n=8:v=1:a=1" in filters
    assert filters.count("setpts=PTS-STARTPTS") == 16
    assert not any(word in filters for word in ("trim", "scale", "subtitles", "ass=", "atempo"))
    assert next(call[2] for call in chapter["calls"] if call[0] == "ffmpeg" and "-filter_complex" in call[1]) == 1800
    with pytest.raises(ValueError):
        subject.release(plan, assembly, chapter["desktop"])
    with pytest.raises(FileExistsError):
        subject.assemble(plan, assembly)


@pytest.mark.parametrize("mutation", ["same-context", "missing-lesson", "missing-seam", "wrong-interval", "listening"])
def test_final_media_gate(chapter, mutation):
    plan, assembly, packet = assembled(chapter)
    path = review(chapter, plan, "chapter_media", packet)
    data = subject.common.read_json(path)
    if mutation == "same-context":
        data["reviewer_context"] = subject.common.read_json(assembly)["reviewer_context"]
    elif mutation == "missing-lesson":
        data["lessons"].pop()
    elif mutation == "missing-seam":
        data["boundaries"].pop()
    elif mutation == "listening":
        data["listening_reviewed"] = True
    else:
        data["lessons"][7]["checks"]["full_lesson"]["evidence"][0]["time"] = .1
    write(path, data)
    with pytest.raises(ValueError):
        subject.release(plan, path, chapter["desktop"])
    assert not chapter["desktop"].exists()


def test_mock_protocol_release_copies_scripts_and_keeps_original_bytes(chapter):
    plan, _, packet = assembled(chapter)
    path = review(chapter, plan, "chapter_media", packet)
    result = subject.release(plan, path, chapter["desktop"])
    assert result["lessons"] == 8 and result["listening_reviewed"] is False and result["student_tested"] is False
    assert len(list(chapter["desktop"].glob("*/lesson.mp4"))) == 8
    assert len(list(chapter["desktop"].rglob("scene*.py"))) == 8
    assert len(list(chapter["desktop"].rglob("narration.json"))) == 8
    assert (chapter["desktop"] / "manifest.json").is_file()
    with pytest.raises(FileExistsError):
        subject.release(plan, path, chapter["desktop"])


def test_failed_encoding_is_pending_and_never_retried(chapter, monkeypatch):
    plan = subject.prepare(chapter["request"])
    path = review(chapter, plan)
    monkeypatch.setattr(subject.pilot, "run", lambda *a, **kw: (_ for _ in ()).throw(TimeoutError("unknown")))
    with pytest.raises(TimeoutError):
        subject.assemble(plan, path)
    candidate = Path(subject.common.read_json(plan)["output"]) / "candidate"
    assert (candidate / "pending.json").exists() and not (candidate / "candidate.json").exists()
    with pytest.raises(FileExistsError):
        subject.assemble(plan, path)


def test_real_examples_dependency_must_be_bound(chapter):
    root = chapter["root"]
    (root / "examples/shared.py").write_text("VALUE = 2\n")
    scene = root / "examples/scene2.py"
    scene.write_text("from shared import VALUE\n")
    render = root / "outputs/lesson-2/visual/render.json"
    value = subject.common.read_json(render)
    value["input_hashes"][str(scene)] = subject.common.sha(scene)
    write(render, value)
    with pytest.raises(ValueError, match="dependency"):
        subject.prepare(chapter["request"])


def test_adapter_requires_actual_thread(chapter, monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", uid())
    with pytest.raises(ValueError, match="actual"):
        subject.prepare(chapter["request"])


@pytest.mark.parametrize("mutation", ["duration", "segments", "boundary", "video", "pixels"])
def test_candidate_tampering_is_rejected(chapter, mutation):
    plan, _, packet = assembled(chapter)
    review_path = review(chapter, plan, "chapter_media", packet)
    candidate = Path(subject.common.read_json(plan)["output"]) / "candidate/candidate.json"
    if mutation == "duration":
        packet["duration"] = 1
    elif mutation == "segments":
        packet["segments"].pop()
    elif mutation == "boundary":
        packet["boundaries"][0]["before"]["time"] = 0
    elif mutation == "video":
        Path(packet["video"]["path"]).write_bytes(b"changed")
    else:
        Path(packet["boundaries"][0]["after"]["path"]).write_bytes(b"changed")
    write(candidate, packet)
    with pytest.raises(ValueError):
        subject.release(plan, review_path, chapter["desktop"])


def test_missing_media_review_and_existing_desktop_are_not_delivery(chapter):
    plan, _, packet = assembled(chapter)
    with pytest.raises(FileNotFoundError):
        subject.release(plan, chapter["root"] / "not-created.json", chapter["desktop"])
    path = review(chapter, plan, "chapter_media", packet)
    chapter["desktop"].mkdir()
    marker = chapter["desktop"] / "original.txt"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        subject.release(plan, path, chapter["desktop"])
    assert marker.read_text() == "keep"


def test_copy_drift_keeps_release_pending_without_manifest(chapter, monkeypatch):
    plan, _, packet = assembled(chapter)
    path = review(chapter, plan, "chapter_media", packet)
    original = subject._copy_receipt
    def copy_and_drift(row, target):
        original(row, target)
        if target.name == "chapter.mp4":
            report = subject.common.read_json(path)
            report["blocking_findings"] = ["changed while copying"]
            write(path, report)
    monkeypatch.setattr(subject, "_copy_receipt", copy_and_drift)
    with pytest.raises(ValueError):
        subject.release(plan, path, chapter["desktop"])
    assert not (chapter["desktop"] / "manifest.json").exists()
    session = Path(subject.common.read_json(plan)["session"])
    assert (session / "release-pending.json").exists() and not (session / "release-complete.json").exists()


def test_bound_examples_dependency_is_archived(chapter):
    root = chapter["root"]
    dependency = root / "examples/shared.py"
    dependency.write_text("VALUE = 2\n")
    scene = root / "examples/scene2.py"
    scene.write_text("from shared import VALUE\n")
    render = root / "outputs/lesson-2/visual/render.json"
    value = subject.common.read_json(render)
    value["input_hashes"].update({str(path): subject.common.sha(path) for path in (scene, dependency)})
    write(render, value)
    plan, _, packet = assembled(chapter)
    path = review(chapter, plan, "chapter_media", packet)
    subject.release(plan, path, chapter["desktop"])
    delivered = chapter["desktop"] / "02-lesson-2/provenance/examples/shared.py"
    assert delivered.read_bytes() == dependency.read_bytes()


@pytest.mark.parametrize("mutation", ["duration", "audio", "fps"])
def test_media_shape_and_clock_gate(chapter, monkeypatch, mutation):
    info = native(36)
    if mutation == "duration":
        info["streams"][1]["duration"] = "35"
    elif mutation == "audio":
        info["streams"][1]["channels"] = 2
    else:
        info["streams"][0]["avg_frame_rate"] = "24/1"
    monkeypatch.setattr(subject.pilot, "probe", lambda path: info)
    with pytest.raises(ValueError):
        subject._media(chapter["root"] / "mock.mp4", 36)
    assert not chapter["calls"]


def test_destination_bytes_cannot_drift_while_copying(chapter, monkeypatch):
    plan, _, packet = assembled(chapter)
    path = review(chapter, plan, "chapter_media", packet)
    original = subject._copy_receipt
    def corrupt_previous_copy(row, target):
        original(row, target)
        if target.name == "lesson.mp4":
            (chapter["desktop"] / "chapter.mp4").write_bytes(b"corruption")
    monkeypatch.setattr(subject, "_copy_receipt", corrupt_previous_copy)
    with pytest.raises(ValueError, match="package changed"):
        subject.release(plan, path, chapter["desktop"])
    assert not (chapter["desktop"] / "manifest.json").exists()
