"""Create-only eight-lesson packaging; never authors review approval.

Public entry points: prepare(request), assemble(plan, review), release(plan, review,
desktop). All inputs are explicit; no newest-version discovery or media generation
other than supervised native FFmpeg concatenation. See docs/导数整章交付.md.
"""

from __future__ import annotations

import argparse
import ast
from fractions import Fraction
import json
import math
import os
from pathlib import Path
from uuid import UUID

from manimind import curriculum
from . import lesson_opening as opening, pilot, preset_audition as common, unit_film as unit
from .formula_film import check_video


ROOT = pilot.ROOT
COUNT = 8
CONTRACT = "chapter-package-v1"
SESSION = "math-derivative-chapter-20261102-package-author"


def _state(writer, consumers, lifecycle):
    return dict(writer=writer, consumers=consumers, lifecycle=lifecycle,
                invalidation="Any bound input, implementation, review, pixel or media change; new version required")


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _receipt(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": common.sha(path)}


def _bound(row):
    if not isinstance(row, dict) or _receipt(row["path"]) != row:
        raise ValueError("Bound source changed")
    return Path(row["path"])


def _identity(value, prefix):
    identity = unit._identity(value, prefix)
    for item in identity:
        if str(UUID(item)) != item:
            raise ValueError("Require canonical actual agent/context UUIDs")
    return identity


def _actor(plan):
    if os.environ.get("CODEX_THREAD_ID") != _identity(plan["actors"], "adapter")[0]:
        raise ValueError("Adapter must be the actual invoking CODEX_THREAD_ID")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("Require finite numeric seconds")
    return value


def _code():
    return [_receipt(path) for path in (__file__, unit.__file__, opening.__file__,
            curriculum.__file__, pilot.__file__, common.__file__)]


def _paths(project, version, session):
    if (not curriculum.ID.fullmatch(project) or not curriculum.ID.fullmatch(version)
            or not curriculum.ID.fullmatch(session)):
        raise ValueError("Unsafe chapter/version/session identifier")
    return (ROOT / "runtime/projects" / project / "chapter-packages" / version,
            ROOT / "outputs" / project / "chapter-packages" / version,
            ROOT / "runtime/sessions" / session / version)


def _dependencies(render, plan):
    """Require local examples imports in the original render's declared inputs."""
    hashes = render["input_hashes"]
    paths = {Path(name).resolve(): digest for name, digest in hashes.items()}
    scene = (ROOT / plan["scene"]).resolve()
    if scene not in paths:
        raise ValueError("Scene absent from actual render inputs")
    for path, digest in paths.items():
        if not path.is_relative_to(ROOT) or common.sha(path) != digest:
            raise ValueError("Render source changed or is outside repository")
        if path.suffix != ".py" or not path.is_relative_to(ROOT / "examples"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    raise ValueError("Relative examples imports require explicit dependency support")
                names = [node.module or "", *[(node.module + "." if node.module else "") + a.name
                                             for a in node.names]]
            for name in names:
                relative = Path(*name.split("."))
                for base in (ROOT / "examples", ROOT):
                    for dependency in (base / relative.with_suffix(".py"), base / relative / "__init__.py"):
                        if dependency.is_file() and dependency.resolve() not in paths:
                            raise ValueError(f"Unbound real examples dependency: {dependency}")
    return [_receipt(path) for path in sorted(paths)]


def _review_frames(value):
    result = []
    if isinstance(value, dict):
        if (isinstance(value.get("path"), str) and "sha256" in value
                and Path(value["path"]).suffix.lower() in {".png", ".jpg", ".jpeg"}):
            row = {key: value[key] for key in ("path", "sha256")}
            _bound(row)
            result.append(row)
        for item in value.values():
            result.extend(_review_frames(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_review_frames(item))
    return result


def _source(delivery_path):
    delivery_path = Path(delivery_path).resolve(strict=True)
    delivery = common.read_json(delivery_path)
    current = unit.caption_bindings(delivery["bindings"]["candidate"])
    if (delivery["bindings"] != current or delivery.get("caption_status") != "single_burned_set"
            or delivery.get("full_decode_passed") is not True or delivery.get("listening_reviewed") is not False
            or common.sha(delivery["video"]) != delivery.get("sha256")
            or delivery["sha256"] != current["files"]["candidate.mp4"]
            or common.sha(delivery["review"]) != delivery.get("review_sha256")):
        raise ValueError("Require unchanged released single-caption source, not a candidate/status claim")
    _, authors, prior = opening._body(delivery_path)
    candidate = Path(current["candidate"])
    manifest = common.read_json(candidate / "candidate.json")
    alignment = common.read_json(manifest["alignment"])
    silent_path = Path(alignment["source"]["delivery"])
    silent = unit.verify_delivery(silent_path)
    attempt = Path(silent["attempt"])
    plan = common.read_json(attempt / "plan.json")
    context_path = (ROOT / plan["lesson_context"]).resolve()
    context = curriculum.verify_context(context_path, ROOT)
    identity = context["current_lesson"]["project_id"]
    if plan.get("project_id") != identity or _number(delivery["duration"]) <= 0:
        raise ValueError("Actual lesson context and render identity disagree")
    sources = _dependencies(common.read_json(attempt / "render.json"), plan)
    archive = [*sources, *[_receipt(path) for path in (
        delivery_path, delivery["review"], candidate / "candidate.json", manifest["alignment"],
        manifest["voiced_delivery"], silent_path, silent["narration"], silent["visual_review"],
        silent["narration_review"], context_path, attempt / "plan.json", attempt / "render.json")],
        *[_receipt(common.read_json(manifest["voiced_delivery"])["review"])]]
    if silent.get("revision_review"):
        archive.append(_receipt(silent["revision_review"]))
    for name in unit.captions.ARTIFACTS:
        if name != "candidate.mp4":
            row = _receipt(candidate / name)
            if row not in archive:
                archive.append(row)
    reviews = [delivery["review"], silent["visual_review"], silent["narration_review"],
               common.read_json(manifest["voiced_delivery"])["review"]]
    if silent.get("revision_review"):
        reviews.append(silent["revision_review"])
    for path in reviews:
        archive.extend(_review_frames(common.read_json(path)))
    return {"project_id": identity, "source_delivery": _receipt(delivery_path),
            "review": _receipt(delivery["review"]), "caption_bindings": current,
            "video": _receipt(delivery["video"]), "duration": delivery["duration"],
            "context": _receipt(context_path), "source_unit": _receipt(context["sources"]["unit"]),
            "authors": [list(person) for person in authors],
            "prior_reviewers": [list(unit._identity(row, "reviewer")) for row in prior],
            "archive": archive}


def _inventory(unit_path, deliveries, science):
    value = common.read_json(unit_path)
    rows = curriculum.catalogue(ROOT / value["catalogue"])
    lessons = curriculum.validate_unit(value, rows)
    if len(lessons) != COUNT or len(deliveries) != COUNT or len(science) != COUNT:
        raise ValueError("All eight ordered distinct lessons/deliveries/science scopes are required")
    if len({str(Path(path).resolve()) for path in deliveries}) != COUNT:
        raise ValueError("Duplicate source delivery")
    sources = []
    for index, (lesson, delivery, scope) in enumerate(zip(lessons, deliveries, science, strict=True)):
        source = _source(delivery)
        if source["project_id"] != lesson["project_id"]:
            raise ValueError("Actual project identity/order differs from chapter unit")
        expected_unit = Path(unit_path).resolve()
        if index == 0 and "existing_first_lesson" in value:
            old = value["existing_first_lesson"]
            expected_unit = (ROOT / old["source_unit"]).resolve()
            if (Path(source["source_delivery"]["path"]) != (ROOT / old["delivery"]).resolve()
                    or source["video"]["sha256"] != old["video_sha256"]):
                raise ValueError("First lesson must retain its exact historical release")
        if source["source_unit"] != _receipt(expected_unit):
            raise ValueError("Wrong actual course-unit provenance")
        scope = _receipt(scope)
        if scope not in source["archive"]:
            raise ValueError("Lesson science scope must be an actual bound render input")
        sources.append({**source, "scope": lesson, "science": scope,
                        "catalogue_excerpts": [rows[name] for name in lesson["catalogue_ids"]]})
    if len({source["video"]["sha256"] for source in sources}) != COUNT:
        raise ValueError("Duplicate lesson media cannot stand in for distinct lessons")
    return value, sources


def prepare(request):
    """Validate eight sources and re-release each via the public frozen gate."""
    request = common.read_json(request)
    actors = request["actors"]
    for role in ("author", "main", "adapter"):
        _identity(actors, role)
    _actor(request)
    unit_path = Path(request["unit"]).resolve(strict=True)
    value, sources = _inventory(unit_path, request["deliveries"], request["science"])
    if request["chapter_id"] != value["unit_id"]:
        raise ValueError("Chapter ID must equal explicit unit ID")
    long, out, session = _paths(request["chapter_id"], request["version"], request.get("session_id", SESSION))
    shared = [_receipt(path) for path in request.get("shared_science", [])]
    # Claim before public release: a failure/unknown outcome permanently retains this version.
    long.mkdir(parents=True, exist_ok=False)
    out.mkdir(parents=True, exist_ok=False)
    session.mkdir(parents=True, exist_ok=False)
    pending = {"status": "pending_not_approved", "actors": actors, "request": request,
               **_state("Chapter adapter", ["operator"], "This one prepare invocation; never automatically replay")}
    _write(session / "prepare-pending.json", pending)
    implementation = _code()
    verified = []
    for index, source in enumerate(sources, 1):
        target = out / "verified-lessons" / f"{index:02d}-{source['project_id']}"
        result = unit.release_captioned(source["caption_bindings"]["candidate"], source["review"]["path"], target)
        if result["sha256"] != source["video"]["sha256"]:
            raise ValueError("Verified copy is not the source bytes")
        verified.append({"video": _receipt(result["video"]), "delivery": _receipt(target / "delivery.json")})
    if _inventory(unit_path, request["deliveries"], request["science"])[1] != sources or _code() != implementation:
        raise ValueError("Sources or implementation drifted during prepare")
    for row in shared:
        _bound(row)
    plan = {"contract": CONTRACT, "status": "prepared_not_approved", "chapter_id": value["unit_id"],
            "title": value["title"], "version": request["version"], "actors": actors,
            "unit": _receipt(unit_path), "implementation": implementation, "sources": sources,
            "shared_science": shared, "verified": verified, "output": str(out), "session": str(session),
            "coverage": {"expected": COUNT, "verified": COUNT, "ordered_ids": [s["project_id"] for s in sources]},
            "listening_reviewed": False, "student_tested": False,
            **_state("Chapter adapter", ["independent assembly reviewer", "assembler", "publisher"],
                     "This immutable chapter package version; preparation grants no approval")}
    _write(long / "plan.json", plan)
    _write(session / "chapter-assembly-input.json", {
        "stage": "chapter_assembly", "bindings": bindings(long / "plan.json"),
        "lessons": [{"project_id": s["project_id"], "video": v["video"], "scope": s["scope"],
                     "science": s["science"], "catalogue_excerpts": s["catalogue_excerpts"],
                     "source_delivery": s["source_delivery"], "review": s["review"], "duration": s["duration"]}
                    for s, v in zip(sources, verified, strict=True)],
        "shared_science": shared, "required_checks": ["coverage", "handoff", "source_completeness"],
        "report_target": str(session / "chapter-assembly-review.json"),
        "boundary": "Review actual media independently, not author source claims; no listening/student certification",
        **_state("Chapter adapter", ["independent chapter reviewer"], "This prepared version")})
    _write(session / "prepare-complete.json", {"plan": _receipt(long / "plan.json"),
           **_state("Chapter adapter", ["operator"], "Prepare completed, not media approved")})
    return str(long / "plan.json")


def bindings(plan_path):
    plan = common.read_json(plan_path)
    if plan.get("contract") != CONTRACT or plan.get("status") != "prepared_not_approved":
        raise ValueError("Not a chapter plan")
    _bound(plan["unit"])
    if _code() != plan["implementation"]:
        raise ValueError("Chapter implementation changed")
    sources = plan["sources"]
    _, current = _inventory(plan["unit"]["path"], [s["source_delivery"]["path"] for s in sources],
                            [s["science"]["path"] for s in sources])
    if current != sources or len(plan["verified"]) != COUNT:
        raise ValueError("Source bindings drifted")
    for row in plan["shared_science"]:
        _bound(row)
    for source, row in zip(sources, plan["verified"], strict=True):
        _bound(row["video"])
        _bound(row["delivery"])
        copy = common.read_json(row["delivery"]["path"])
        if (row["video"]["sha256"] != source["video"]["sha256"] or copy["bindings"] != source["caption_bindings"]
                or copy["review_sha256"] != source["review"]["sha256"] or copy["video"] != row["video"]["path"]):
            raise ValueError("Verified lesson copy drifted")
    return {"contract": CONTRACT, "plan": _receipt(plan_path), "unit": plan["unit"],
            "implementation": plan["implementation"], "sources": sources, "verified": plan["verified"],
            "shared_science": plan["shared_science"]}


def _observation(row, video, duration):
    if Path(row.get("path", "")).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("Review evidence must cite an actual extracted frame")
    opening._pixel(row, video["path"], duration)


def _check(row, name, video, duration):
    check = row.get("checks", {}).get(name, {})
    evidence = check.get("evidence")
    conditions = check.get("conditions")
    if (check.get("status") != "pass" or not isinstance(conditions, list) or not conditions
            or any(not isinstance(c, str) or not c.strip() for c in conditions)
            or not isinstance(evidence, list) or not evidence):
        raise ValueError(f"Missing actual evidence/conditions for {name}")
    for observation in evidence:
        _observation(observation, video, duration)


def _review(plan, review_path, stage, current, prior=()):
    report = common.read_json(review_path)
    reviewer = _identity(report, "reviewer")
    authors = [_identity(plan["actors"], role) for role in ("author", "main", "adapter")]
    authors += [tuple(person) for s in plan["sources"] for person in s["authors"]]
    unit._review(report, stage, current, authors=authors, prior_reviews=prior)
    if any(reviewer[1] == person[1] for s in plan["sources"] for person in s["prior_reviewers"]):
        raise ValueError("Chapter review requires a fresh context, not a reused lesson approval")
    if report.get("listening_status") != "not_performed":
        raise ValueError("Listening must be honestly marked not_performed")
    checked = report.get("lessons")
    if not isinstance(checked, list) or len(checked) != COUNT:
        raise ValueError("Chapter review must explicitly cover all eight lessons")
    for source, verified, row in zip(plan["sources"], plan["verified"], checked, strict=True):
        if (row.get("project_id") != source["project_id"] or row.get("source_delivery") != source["source_delivery"]
                or row.get("science") != source["science"]):
            raise ValueError("Review lesson order, science or source binding mismatch")
        video = verified["video"] if stage == "chapter_assembly" else current["video"]
        duration = source["duration"] if stage == "chapter_assembly" else current["duration"]
        names = ("coverage", "handoff", "source_completeness") if stage == "chapter_assembly" else (
            "full_lesson", "captions", "av_continuity")
        for name in names:
            _check(row, name, video, duration)
        if stage == "chapter_media":
            start, end = current["segments"][plan["sources"].index(source)]["interval"]
            for check in row["checks"].values():
                for observation in check["evidence"]:
                    if not start <= observation["time"] < end:
                        raise ValueError("Media review observations must belong to this lesson interval")
    if stage == "chapter_media":
        boundaries = report.get("boundaries", [])
        expected = current["boundaries"]
        if len(boundaries) != COUNT - 1:
            raise ValueError("Review every chapter boundary")
        for row, boundary in zip(boundaries, expected, strict=True):
            if row.get("before") != boundary["before"] or row.get("after") != boundary["after"]:
                raise ValueError("Review must cite both exact extracted boundary frames")
            _check(row, "seam", current["video"], current["duration"])
            observations = row["checks"]["seam"]["evidence"]
            for frame in (boundary["before"], boundary["after"]):
                if not any(all(item.get(key) == frame[key] for key in ("path", "sha256", "video_sha256", "time"))
                           for item in observations):
                    raise ValueError("Seam review requires observations on both actual boundary frames")
    return report


def _media(path, duration):
    info = pilot.probe(path)
    check_video(info, duration)
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    if audio["codec_name"] != "aac" or audio["sample_rate"] != "48000" or audio["channels"] != 1:
        raise ValueError("Require native 48k mono AAC")
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", path, "-map", "0:v:0", "-map", "0:a:0",
               "-f", "null", "-"], timeout=1800)
    return info


def _segments(plan):
    result, elapsed = [], Fraction(0)
    for source in plan["sources"]:
        end = elapsed + Fraction(str(source["duration"]))
        result.append({"project_id": source["project_id"],
                       "title": source["scope"].get("title", source["project_id"]),
                       "duration": source["duration"], "interval": [float(elapsed), float(end)]})
        elapsed = end
    return result, float(elapsed)


def assemble(plan_path, review_path):
    plan = common.read_json(plan_path)
    _actor(plan)
    current = bindings(plan_path)
    review_receipt = _receipt(review_path)
    _review(plan, review_path, "chapter_assembly", current)
    candidate = Path(plan["output"]) / "candidate"
    candidate.mkdir(exist_ok=False)
    _write(candidate / "pending.json", {"status": "pending_not_released", "bindings": current,
           "review": review_receipt, **_state("Chapter assembler", ["operator"], "Single encoding attempt; retain on failure")})
    command = [pilot.FFMPEG, "-v", "error", "-n"]
    filters, labels = [], []
    segments, duration = _segments(plan)
    for index, (source, verified) in enumerate(zip(plan["sources"], plan["verified"], strict=True)):
        info = pilot.probe(verified["video"]["path"])
        check_video(info, source["duration"])
        command += ["-i", verified["video"]["path"]]
        filters += [f"[{index}:v:0]setpts=PTS-STARTPTS[v{index}]",
                    f"[{index}:a:0]aresample=48000,aformat=channel_layouts=mono,asetpts=PTS-STARTPTS[a{index}]"]
        labels.append(f"[v{index}][a{index}]")
    filters.append("".join(labels) + f"concat=n={COUNT}:v=1:a=1[v][a]")
    video = candidate / "chapter-candidate.mp4"
    command += ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]", "-map_metadata", "-1",
                "-map_chapters", "-1", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "1", "-b:a", "192k",
                "-sn", "-dn", "-movflags", "+faststart", video]
    pilot.run(command, timeout=1800)
    info = _media(video, duration)
    frames = Path(plan["session"]) / "chapter-boundaries"
    frames.mkdir(exist_ok=False)
    boundaries = []
    for index, segment in enumerate(segments[1:], 1):
        boundary = {}
        for label, time in (("before", segment["interval"][0] - 1 / 30), ("after", segment["interval"][0])):
            target = frames / f"{index:02d}-{label}.png"
            pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-ss", str(time), "-i", video,
                       "-map", "0:v:0", "-frames:v", "1", target], timeout=60)
            boundary[label] = {**_receipt(target), "time": time, "video_sha256": common.sha(video)}
        boundaries.append(boundary)
    if bindings(plan_path) != current or _receipt(review_path) != review_receipt:
        raise ValueError("Chapter source/approval drifted while encoding")
    _review(plan, review_path, "chapter_assembly", current)
    packet = {"contract": CONTRACT, "status": "candidate_not_released", "stage": "chapter_media",
              "source_bindings": current, "assembly_review": review_receipt, "video": _receipt(video),
              "duration": duration, "probe": info, "segments": segments, "boundaries": boundaries,
              "command": [str(item) for item in command], "full_decode_passed": True,
              "listening_reviewed": False, "student_tested": False,
              **_state("Chapter assembler", ["independent media reviewer", "publisher"], "This exact full candidate")}
    _write(candidate / "candidate.json", packet)
    _write(Path(plan["session"]) / "chapter-media-input.json", {
        "stage": "chapter_media", "bindings": packet, "report_target": str(Path(plan["session"]) / "chapter-media-review.json"),
        "required_checks": ["full_lesson", "captions", "av_continuity", "seven seams"],
        **_state("Chapter assembler", ["fresh independent media reviewer"], "This candidate only; not released")})
    return packet


def _candidate(plan_path):
    plan = common.read_json(plan_path)
    packet = common.read_json(Path(plan["output"]) / "candidate/candidate.json")
    segments, duration = _segments(plan)
    if (packet.get("contract") != CONTRACT or packet.get("stage") != "chapter_media"
            or packet.get("status") != "candidate_not_released" or packet.get("source_bindings") != bindings(plan_path)
            or packet.get("full_decode_passed") is not True or packet.get("listening_reviewed") is not False
            or packet.get("student_tested") is not False or packet.get("segments") != segments
            or packet.get("duration") != duration or len(packet.get("boundaries", [])) != COUNT - 1
            or Path(packet["video"]["path"]) != Path(plan["output"]) / "candidate/chapter-candidate.mp4"):
        raise ValueError("Candidate/source bindings changed")
    _bound(packet["video"])
    _bound(packet["assembly_review"])
    for boundary, segment in zip(packet["boundaries"], segments[1:], strict=True):
        for label, offset in (("before", -1 / 30), ("after", 0)):
            row = boundary[label]
            _bound({key: row[key] for key in ("path", "sha256")})
            if row["time"] != segment["interval"][0] + offset or row["video_sha256"] != packet["video"]["sha256"]:
                raise ValueError("Boundary timestamps or candidate pixels changed")
            _observation({**row, "finding": "Extracted chapter boundary"}, packet["video"], duration)
    return packet


def _copy_receipt(row, target):
    _bound(row)
    target.parent.mkdir(parents=True, exist_ok=True)
    unit._copy(row["path"], target)
    if common.sha(target) != row["sha256"]:
        raise ValueError("Package copy differs from source bytes")


def release(plan_path, review_path, desktop):
    plan = common.read_json(plan_path)
    _actor(plan)
    packet = _candidate(plan_path)
    assembly = _review(plan, packet["assembly_review"]["path"], "chapter_assembly", bindings(plan_path))
    review_receipt = _receipt(review_path)
    _review(plan, review_path, "chapter_media", packet, prior=[assembly])
    _media(packet["video"]["path"], packet["duration"])
    desktop = Path(desktop).absolute()
    if desktop.parent.resolve() != (Path.home() / "Desktop").resolve() or desktop.is_symlink():
        raise ValueError("Release requires a new direct Desktop child; no cloud/GitHub destinations")
    session = Path(plan["session"])
    _write(session / "release-pending.json", {"destination": str(desktop), "candidate": packet["video"],
           "review": review_receipt, **_state("Chapter publisher", ["operator"], "One attempt; unknown result never retried")})
    desktop.mkdir(exist_ok=False)
    expected = {}

    def copy(row, target):
        if target.exists() or target.is_symlink():
            _bound(row)
            if target.is_symlink() or expected.get(str(target)) != row["sha256"] or common.sha(target) != row["sha256"]:
                raise ValueError("Unowned or changed package target")
        else:
            _copy_receipt(row, target)
        expected[str(target)] = row["sha256"]

    copy(packet["video"], desktop / "chapter.mp4")
    for index, (source, verified) in enumerate(zip(plan["sources"], plan["verified"], strict=True), 1):
        folder = desktop / f"{index:02d}-{source['project_id']}"
        copy(verified["video"], folder / "lesson.mp4")
        for row in source["archive"]:
            path = Path(row["path"])
            if not path.is_relative_to(ROOT):
                raise ValueError("Archive source outside repository")
            target = folder / "provenance" / path.relative_to(ROOT)
            copy(row, target)
    for row in [plan["unit"], *plan["shared_science"], packet["assembly_review"], review_receipt,
                _receipt(plan_path), _receipt(Path(plan["output"]) / "candidate/candidate.json"),
                *[_receipt(row[label]["path"]) for row in packet["boundaries"] for label in ("before", "after")],
                *_review_frames(assembly), *_review_frames(common.read_json(review_path))]:
        target = desktop / "chapter-provenance" / Path(row["path"]).relative_to(ROOT)
        copy(row, target)
    with (desktop / "目录.md").open("x", encoding="utf-8") as stream:
        stream.write(f"# {plan['title']}\n\n")
        for index, row in enumerate(packet["segments"], 1):
            seconds = round(row["duration"])
            stream.write(f"{index:02d}. {row['title']} ({seconds // 60:02d}:{seconds % 60:02d})\n")
        stream.write("\n听审未进行；学生测试未进行。合辑与八分课均为单套烧录字幕预览。\n")
    expected[str(desktop / "目录.md")] = common.sha(desktop / "目录.md")
    if _candidate(plan_path) != packet or _receipt(review_path) != review_receipt:
        raise ValueError("Source/approval changed during copy; retain pending, do not deliver")
    _review(plan, review_path, "chapter_media", packet, prior=[assembly])
    files = [_receipt(path) for path in sorted(desktop.rglob("*")) if path.is_file()]
    if {row["path"]: row["sha256"] for row in files} != expected:
        raise ValueError("Delivered package changed during copying; retain pending")
    result = {"contract": CONTRACT, "status": "released_complete_chapter_preview", "lessons": COUNT,
              "destination": str(desktop), "candidate": packet, "media_review": review_receipt,
              "listening_reviewed": False, "listening_status": "not_performed", "student_tested": False,
              "files": files, **_state("Chapter publisher", ["viewer", "auditor"], "This exact new Desktop package")}
    _write(desktop / "manifest.json", result)
    _write(session / "release-complete.json", {"manifest": _receipt(desktop / "manifest.json"),
           **_state("Chapter publisher", ["operator"], "Copy completed; no listening or cloud upload claim")})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "bindings", "assemble", "release"))
    parser.add_argument("--request", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--desktop", type=Path)
    args = parser.parse_args(argv)
    required = {"prepare": [args.request], "bindings": [args.plan],
                "assemble": [args.plan, args.review], "release": [args.plan, args.review, args.desktop]}
    if any(item is None for item in required[args.stage]):
        parser.error("Explicit request/plan/review/destination arguments required for this stage")
    handlers = {"prepare": lambda: prepare(args.request), "bindings": lambda: bindings(args.plan),
                "assemble": lambda: assemble(args.plan, args.review),
                "release": lambda: release(args.plan, args.review, args.desktop)}
    print(json.dumps(handlers[args.stage](), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
