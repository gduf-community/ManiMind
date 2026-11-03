"""Resume-safe supervision of existing independent course-lesson gates.

This adapter never creates review approval or invokes a language/TTS model.
Editors own the immutable chapter unit; the coordinator writes per-stage
session packets; existing renderers and publishers own their output records.
Any bound source, context, media, original audio or review change invalidates
the corresponding packet. A failed version is retained, not overwritten.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re

from manimind import curriculum
from manimind.postproduce import preset_audition as common, understanding_render, unit_film


ROOT = Path(__file__).resolve().parents[3]
CHAPTER = "math-derivative-chapter-20261102"
UNIT = ROOT / f"runtime/projects/{CHAPTER}/unit-v001.json"


def write_once(path, value):
    path = Path(path)
    if path.exists():
        if common.read_json(path) != value:
            raise ValueError(f"Existing artifact differs; retain it and use a new version: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    common.write_json(path, value)


def packet_state(writer, consumers, lifecycle):
    return {"writer": writer, "consumers": consumers, "lifecycle": lifecycle,
            "invalidation": "Any bound context, source, media, text, timing, voice or review change"}


def coverage_status(unit, released_ids):
    """An inventory check only; callers must verify actual release receipts."""
    expected = [row["project_id"] for row in unit["lessons"]]
    released = list(released_ids)
    if len(set(expected)) != len(expected) or len(set(released)) != len(released):
        raise ValueError("Chapter and release entries must have unique lesson IDs")
    unknown = sorted(set(released)-set(expected))
    if unknown:
        raise ValueError(f"Unknown lesson releases: {unknown}")
    missing = [identity for identity in expected if identity not in released]
    return {"complete": not missing, "expected": len(expected), "released": len(released), "missing": missing,
            "scope": "Inventory only, not media approval or student mastery"}


@contextmanager
def stage_lock(session, stage):
    path = session / "active-stage.json"
    session.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "stage": stage, "writer": "Current chapter coordinator process",
                       "consumers": ["resume operator"], "lifecycle": "This active invocation; removed in finally",
                       "invalidation": "Process exit; an orphan lock requires explicit diagnosis, never automatic replay"}, stream)
    except FileExistsError:
        raise RuntimeError(f"An active or unresolved invocation exists: {path}") from None
    try:
        yield
    finally:
        path.unlink()


def paths(project, version, visual_version=None):
    visual_version = visual_version or version
    if (not curriculum.ID.fullmatch(project) or not re.fullmatch(r"v[0-9]{3}", version)
            or not re.fullmatch(r"v[0-9]{3}", visual_version)):
        raise ValueError("Use safe project and version identifiers")
    project_dir = ROOT / "runtime/projects" / project
    session = ROOT / "runtime/sessions" / CHAPTER / project
    output = ROOT / "outputs" / project
    result = {"project": project_dir, "session": session, "output": output,
              "context": project_dir / "context-v001.json", "plan": project_dir / f"plan-{version}.json",
              "draft": project_dir / f"scene-draft-plan-{version}.json",
              "brief": project_dir / "scientific-brief-v001.json",
              "narration": project_dir / f"narration-{version}.json",
              "speech_plan": session / f"speech-plan-{version}.json"}
    for stage in ("visual", "silent", "alignment", "voiced", "caption-candidate", "captioned"):
        result[stage] = output / f"{stage}-{version}"
    for stage in ("visual", "narration", "audio", "caption"):
        result[stage + "_review"] = session / "review" / f"{stage}-{version}.json"
        result[stage + "_packet"] = session / f"{stage}-input-{version}.json"
    result["visual"] = output / f"visual-{visual_version}"
    result["visual_review"] = session / "review" / f"visual-{visual_version}.json"
    return result


def selected_silent(p):
    retained = unit_film.verify_delivery(p["silent"] / "delivery.json")
    for key, selected in (("attempt", "visual"), ("narration", "narration"),
                          ("visual_review", "visual_review"), ("narration_review", "narration_review")):
        if Path(retained[key]).resolve(strict=True) != p[selected].resolve(strict=True):
            raise ValueError("Requested visual/text/reviews differ from retained silent delivery; use a new version")
    if retained["bindings"] != unit_film.bindings(p["visual"], p["narration"]):
        raise ValueError("Requested silent bindings differ; use a new version")
    return retained


def execute(args):
    identity = os.environ.get("CODEX_THREAD_ID")
    if not identity:
        raise ValueError("Actual coordinator identity is required")
    visual_version = getattr(args, "visual_version", None)
    if visual_version and visual_version != args.version and args.stage in {"prepare", "render", "register"}:
        raise ValueError("Visual-version selection is only for post-visual narration and publication stages")
    p = paths(args.project, args.version, visual_version)
    with stage_lock(p["session"], args.stage):
        if args.stage == "prepare":
            draft_path = (getattr(args, "draft", None) or p["draft"]).resolve()
            if not p["context"].exists():
                curriculum.write_context(UNIT, args.project, p["context"], ROOT)
            context = curriculum.verify_context(p["context"], ROOT)
            plan = common.read_json(draft_path)
            brief_path = (ROOT / plan["scientific_brief"] if plan.get("scientific_brief") else p["brief"]).resolve(strict=True)
            if not brief_path.is_relative_to(p["project"].resolve(strict=True)):
                raise ValueError("Scientific brief must belong to this lesson project")
            brief = common.read_json(brief_path)
            if brief.get("project_id") != args.project:
                raise ValueError("Scientific brief project identity differs")
            unit_film._identity(plan, "author")
            plan.update(project_id=args.project, workflow_profile="configs/visual-first-workflow-v4.2-unit.json",
                        lesson_context=str(p["context"].relative_to(ROOT)),
                        scientific_brief=str(brief_path.relative_to(ROOT)),
                        audience=context["audience"], prior_knowledge=context["entry_assumptions"],
                        understanding_goals=brief.get("lesson_design", {}).get("new_understanding", [context["current_lesson"]["new_understanding"]]))
            plan.setdefault("revision_mode", "fresh")
            plan.setdefault("narration_draft", str((p["project"] / f"narration-draft-{args.version}.json").relative_to(ROOT)))
            required = [p["context"], UNIT, Path(context["sources"]["catalogue"]),
                        Path(curriculum.__file__), brief_path, draft_path]
            plan["sources"] = list(dict.fromkeys([*plan.get("sources", []),
                "examples/derivative_chapter_shared.py", *(str(path.relative_to(ROOT)) for path in required)]))
            write_once(p["plan"], plan)
        elif args.stage == "render":
            if (p["visual"] / "render.json").exists():
                if common.read_json(p["plan"]) != common.read_json(p["visual"] / "plan.json"):
                    raise ValueError("Requested plan differs from the retained render; use a new version")
                unit_film.bindings(p["visual"])
            else:
                understanding_render.render(p["plan"], p["visual"])
        elif args.stage == "register":
            plan = common.read_json(p["visual"] / "plan.json")
            current = unit_film.bindings(p["visual"])
            write_once(p["visual_packet"], {"attempt": str(p["visual"]), "bindings": current,
                "audience": plan["audience"], "prior_knowledge": plan["prior_knowledge"],
                "understanding_goals": plan["understanding_goals"],
                "public_context": str(p["context"]), "scientific_brief": str((ROOT / plan["scientific_brief"]).resolve(strict=True)),
                "actual_evidence": str(p["visual"] / "review-input.json"),
                "visual_report_target": str(p["visual_review"]),
                **packet_state("Current visual packet assembler", ["independent first-look reviewer"], "This exact lesson render")})
            if plan["revision_mode"] == "revision":
                write_once(p["session"] / f"regression-input-{args.version}.json", {
                    "attempt": str(p["visual"]), "bindings": current,
                    "contract": str(ROOT / plan["revision_contract"]),
                    "actual_evidence": str(p["visual"] / "review-input.json"),
                    "report_target": str(ROOT / plan["revision_review"]),
                    **packet_state("Current revision packet assembler", ["independent content comparator"], "This exact revision and selected baseline")})
        elif args.stage == "install":
            plan = common.read_json(p["visual"] / "plan.json")
            draft = (getattr(args, "narration_draft", None) or ROOT / plan["narration_draft"]).resolve(strict=True)
            if not p["narration"].exists():
                unit_film.install_narration(p["visual"], draft, p["visual_review"], p["narration"])
            else:
                installed = common.read_json(p["narration"])
                if (Path(installed["source_draft"]).resolve(strict=True) != draft
                        or installed["source_draft_sha256"] != common.sha(draft)
                        or Path(installed["visual_review"]).resolve(strict=True) != p["visual_review"].resolve(strict=True)
                        or installed["visual_review_sha256"] != common.sha(p["visual_review"])):
                    raise ValueError("Requested narration draft/review differs from retained installation; use a new version")
            current = unit_film.bindings(p["visual"], p["narration"])
            write_once(p["narration_packet"], {"attempt": str(p["visual"]), "narration": str(p["narration"]),
                "bindings": current, "actual_evidence": str(p["visual"] / "review-input.json"),
                "report_target": str(p["narration_review"]),
                **packet_state("Current narration packet assembler", ["independent narration reviewer"], "This installed narration and current visual")})
        elif args.stage == "silent":
            if not p["silent"].exists():
                unit_film.release_silent(p["visual"], p["narration"], p["visual_review"], p["narration_review"], p["silent"])
            else:
                selected_silent(p)
        elif args.stage == "speech-plan":
            if not args.reference:
                raise ValueError("speech-plan requires the selected local reference")
            if p["speech_plan"].exists():
                retained = common.read_json(p["speech_plan"])
                selected_silent(p)
                if (Path(retained["source"]["delivery"]).resolve(strict=True) != (p["silent"] / "delivery.json").resolve(strict=True)
                        or retained["source"]["delivery_sha256"] != common.sha(p["silent"] / "delivery.json")
                        or Path(retained["reference_source"]).resolve(strict=True) != args.reference.resolve(strict=True)
                        or retained["reference_sha256"] != common.sha(args.reference)):
                    raise ValueError("Requested speech source/reference differs from retained plan; use a new version")
                unit_film.verify_speech_source(retained)
            else:
                unit_film.speech_plan(p["silent"] / "delivery.json", args.reference, p["speech_plan"])
        elif args.stage == "align":
            if not args.speech or not args.timings:
                raise ValueError("align requires actual original speech and verified timing evidence")
            if not p["alignment"].exists():
                unit_film.align(p["silent"] / "delivery.json", args.voice_plan or p["speech_plan"], args.speech,
                               args.timings, p["alignment"], producer_agent=identity, producer_context=identity)
            else:
                retained = common.read_json(p["alignment"] / "alignment.json")
                requested = {"plan": (args.voice_plan or p["speech_plan"]).resolve(strict=True),
                             "speech": args.speech.resolve(strict=True),
                             "timings": args.timings.resolve(strict=True)}
                if (any(str(path) != retained[key] for key, path in requested.items())
                        or not requested["speech"].is_dir()
                        or common.sha(requested["plan"]) != retained["plan_sha256"]
                        or common.sha(requested["timings"]) != retained["timings_sha256"]):
                    raise ValueError("Requested voice inputs differ from retained alignment; use a new version")
            current = unit_film.audio_bindings(p["alignment"] / "alignment.json")
            write_once(p["audio_packet"], {"alignment": str(p["alignment"] / "alignment.json"), "bindings": current,
                "report_target": str(p["audio_review"]), "actual_evidence": str(p["visual"] / "review-input.json"),
                **packet_state("Current full-original-audio scheduler", ["independent phrase/pixel reviewer"], "This intact audio and actual current visual schedule")})
        elif args.stage == "voice":
            unit_film.release_voiced(p["alignment"] / "alignment.json", p["audio_review"], p["voiced"])
        elif args.stage == "captions":
            if not p["caption-candidate"].exists():
                unit_film.caption_candidate(p["alignment"] / "alignment.json", p["voiced"] / "delivery.json",
                    p["caption-candidate"], producer_agent=identity, producer_context=identity, timing_mode="word_estimates")
            write_once(p["caption_packet"], {"candidate": str(p["caption-candidate"]),
                "bindings": unit_film.caption_bindings(p["caption-candidate"]), "report_target": str(p["caption_review"]),
                **packet_state("Current single-caption assembler", ["independent caption pixel reviewer"], "This exact caption candidate")})
        else:
            unit_film.release_captioned(p["caption-candidate"], p["caption_review"], p["captioned"])
    return {"completed_stage": args.stage, "project": args.project, "version": args.version}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "render", "register", "install", "silent", "speech-plan", "align", "voice", "captions", "release"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", default="v001")
    parser.add_argument("--visual-version")
    for field in ("reference", "speech", "timings", "voice-plan", "draft", "narration-draft"):
        parser.add_argument("--" + field, type=Path)
    print(json.dumps(execute(parser.parse_args()), ensure_ascii=False))


if __name__ == "__main__":
    main()
