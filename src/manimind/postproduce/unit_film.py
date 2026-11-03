"""Create-only continuous-unit postproduction, separate from frozen publishers.

Project inputs: schema-3 narration and course context. Session inputs: independent
stage reviews and forced-alignment estimates. Versioned outputs: silent delivery,
schema-2 TTS transport, alignment, voiced preview and caption candidate/release.
Each record declares its writer, consumers, lifecycle and invalidation. Current
visual/text approval is always rechecked; immutable speech assets may outlive a
visual revision only with identical ordered units/references and original receipts.
Neither model timing nor release implies listening, ASR accuracy or student tests.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import wave

from manimind import curriculum
from manimind.review import meaning_units as units, understanding_quality as quality
from manimind.review import content_regression as regression
from . import understanding_film as legacy, understanding_render as visual
from . import focus_captions as captions, flexible_voxcpm as vox
from . import word_captions
from . import phrase_alignment as forced
from . import pilot, preset_audition as common
from .formula_film import check_video


def _state(writer, consumers, lifecycle, invalidation):
    return dict(writer=writer, consumers=consumers, lifecycle=lifecycle, invalidation=invalidation)


def _fresh(path):
    path = Path(path).absolute()
    if os.path.lexists(path):
        raise FileExistsError(path)
    return path.resolve()


def _write(path, value):
    path = _fresh(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    common.write_json(path, value)


def _copy(source, target):
    with Path(source).open("rb") as src, Path(target).open("xb") as dst:
        shutil.copyfileobj(src, dst)


def _identity(value, prefix):
    result = tuple(value.get(prefix + "_" + key) for key in ("agent", "context"))
    if any(not isinstance(item, str) or not item.strip() or item != item.strip() for item in result):
        raise ValueError(f"Require explicit {prefix}_agent and {prefix}_context; never infer an independent identity")
    if any(value[key] != result[0] for key in ("agentID", "agent_id") if key in value):
        raise ValueError("Agent identity aliases disagree; role relabeling cannot create independence")
    return result


def _visual_part(value):
    return {k: v for k, v in value.items() if k not in {
        "narration_sha256", "narration_author_agent", "narration_author_context"}}


def bindings(attempt, narration=None):
    attempt = Path(attempt).resolve()
    result = legacy.bindings(attempt)
    plan = common.read_json(attempt / "plan.json")
    author = _identity(plan, "author")
    profile = common.read_json(attempt / "workflow-profile.json")
    if profile.get("delivery_contract") != units.SOURCE_CONTRACT or not plan.get("lesson_context"):
        raise ValueError("Require the new delivery contract and explicit lesson_context")
    context_path = (pilot.ROOT / plan["lesson_context"]).resolve()
    context = curriculum.verify_context(context_path, pilot.ROOT)
    required = {context_path, Path(context["sources"]["unit"]).resolve(),
                Path(context["sources"]["catalogue"]).resolve(), Path(curriculum.__file__).resolve()}
    declared = {(pilot.ROOT / name).resolve() for name in plan.get("sources", [])}
    archived = common.read_json(attempt / "render.json")["input_hashes"]
    if not required <= declared or any(archived.get(str(path)) != common.sha(path) for path in required):
        raise ValueError("Course context and all its sources must be explicit rendered inputs")
    if plan.get("project_id") is not None and plan["project_id"] != context["current_lesson"]["project_id"]:
        raise ValueError("Course context belongs to another lesson")
    result.update(source_contract=units.SOURCE_CONTRACT, publisher_sha256=common.sha(__file__),
                  meaning_units_sha256=common.sha(units.__file__), lesson_context_sha256=common.sha(context_path),
                  legacy_tools_sha256=common.sha(legacy.__file__), caption_tools_sha256=common.sha(captions.__file__),
                  visual_author_agent=author[0], visual_author_context=author[1])
    if narration is not None:
        value = common.read_json(narration)
        narrator = _identity(value, "author")
        units.validate_narration(value, common.read_json(attempt / "timeline.json"), common.read_json(attempt / "focus-events.json"))
        if value.get("source_contract") != units.SOURCE_CONTRACT or value.get("visual_bindings") != bindings(attempt):
            raise ValueError("Narration belongs to another current visual/course contract")
        draft = common.read_json(value["source_draft"])
        if (common.sha(value["source_draft"]) != value.get("source_draft_sha256")
                or _identity(draft, "author") != narrator or draft["units"] != value["units"]):
            raise ValueError("Narration author or original draft changed; relabeling cannot create independence")
        if common.sha(value["visual_review"]) != value.get("visual_review_sha256"):
            raise ValueError("Narration's visual approval changed")
        result.update(narration_sha256=common.sha(narration), narration_author_agent=narrator[0], narration_author_context=narrator[1])
    return result


def require_regression(attempt):
    attempt = Path(attempt).resolve()
    plan, profile = common.read_json(attempt / "plan.json"), common.read_json(attempt / "workflow-profile.json")
    if not regression.revision_required(plan, profile_version=profile["version"]):
        return None
    contract, _ = regression.contract_bindings(pilot.ROOT / plan["revision_contract"], pilot.ROOT)
    path = (pilot.ROOT / plan["revision_review"]).resolve()
    report = common.read_json(path)
    regression.validate_comparison(report, contract, bindings(attempt), common.read_json(attempt / "timeline.json")["duration"])
    _review(report, "content_regression", bindings(attempt), authors=[_identity(plan, "author")])
    if report["status"] != "pass":
        raise ValueError("Independent content regression must pass")
    return path


def _review(value, stage, current, *, authors, prior_reviews=()):
    if (value.get("stage") != stage or value.get("bindings") != current or value.get("status") != "pass"
            or value.get("reviewer_role") != "independent" or not isinstance(value.get("reviewer_agent"), str)
            or not value["reviewer_agent"].strip() or value.get("release_authorized") is not True
            or value.get("blocking_findings") != [] or value.get("listening_reviewed") is not False
            or value.get("student_tested") is not False
            or any(value.get(key, False) is not False for key in (
                "naturalness_approved", "asr_accuracy_certified", "pronunciation_approved"))):
        raise ValueError("Require current independent stage review, empty blockers and honest listening_reviewed=false")
    reviewer = _identity(value, "reviewer")
    if (not authors or any(reviewer[0] == author[0] or reviewer[1] == author[1] for author in authors)
            or any(reviewer[1] == _identity(previous, "reviewer")[1] for previous in prior_reviews)):
        raise ValueError("Authors/producers cannot self-review; stage reviews require fresh reviewer contexts")
    return value


def require_review(attempt, path, *, narration=None):
    stage = "visual" if narration is None else "narration"
    authors = [_identity(common.read_json(Path(attempt) / "plan.json"), "author")]
    prior = []
    if narration is not None:
        value = common.read_json(narration)
        authors.append(_identity(value, "author"))
        prior.append(require_review(attempt, value["visual_review"]))
    report = _review(common.read_json(path), stage, bindings(attempt, narration), authors=authors, prior_reviews=prior)
    quality.validate_editorial_review(report, duration=common.read_json(Path(attempt) / "timeline.json")["duration"], stage=stage)
    comparison = require_regression(attempt)
    if comparison is not None and stage == "visual" and common.read_json(comparison)["reviewer_agent"] == report["reviewer_agent"]:
        raise ValueError("Blind first look and regression require different reviewer contexts")
    return report


def install_narration(attempt, draft, visual_review, target):
    target = _fresh(target)
    attempt, draft = Path(attempt).resolve(), Path(draft).resolve()
    require_review(attempt, visual_review)
    value = common.read_json(draft)
    narrator = _identity(value, "author")
    first_look = common.read_json(visual_review)
    if narrator[0] == first_look["reviewer_agent"] or narrator[1] == _identity(first_look, "reviewer")[1]:
        raise ValueError("The narration author cannot be its visual first-look reviewer")
    units.validate_narration(value, common.read_json(attempt / "timeline.json"), common.read_json(attempt / "focus-events.json"))
    result = {**value, "source_contract": units.SOURCE_CONTRACT, "visual_bindings": bindings(attempt),
              "source_draft": str(draft), "source_draft_sha256": common.sha(draft), "audio_status": "not_generated",
              "visual_review": str(Path(visual_review).resolve()), "visual_review_sha256": common.sha(visual_review),
              **_state("Continuous-unit narration installer", ["independent narration reviewer", "speech planner"],
                       "This current lesson/visual/text revision", "Text, course source, visuals, focus, profile or gate changes")}
    _write(target, result)
    return result


def release_silent(attempt, narration, visual_review, narration_review, output):
    output = _fresh(output)
    attempt, narration, visual_review, narration_review = map(lambda p: Path(p).resolve(),
        (attempt, narration, visual_review, narration_review))
    installed = common.read_json(narration)
    if (Path(installed["visual_review"]).resolve() != visual_review
            or installed["visual_review_sha256"] != common.sha(visual_review)):
        raise ValueError("Silent release must retain the exact independent first look used to install narration")
    require_review(attempt, visual_review)
    require_review(attempt, narration_review, narration=narration)
    current = bindings(attempt, narration)
    reviews = {str(p): common.sha(p) for p in (visual_review, narration_review)}
    record = common.read_json(attempt / "render.json")
    check_video(pilot.probe(record["video"]), record["duration"], silent=True)
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", record["video"], "-f", "null", "-"], timeout=300)
    if bindings(attempt, narration) != current or any(common.sha(p) != h for p, h in reviews.items()):
        raise ValueError("Silent source/review changed during verification")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "visual-master.mp4"
    _copy(record["video"], target)
    if common.sha(target) != current["visual_sha256"]:
        raise ValueError("Silent copy changed")
    result = {"source_contract": units.SOURCE_CONTRACT, "video": str(target), "sha256": common.sha(target),
              "duration": record["duration"], "attempt": str(attempt), "narration": str(narration),
              "visual_review": str(visual_review), "narration_review": str(narration_review),
              "visual_review_sha256": reviews[str(visual_review)], "narration_review_sha256": reviews[str(narration_review)],
              "bindings": current, "full_decode_passed": True, "listening_reviewed": False,
              "audio_status": "pending_local_gpu_generation", "scope": "Current independently approved silent course lesson, not voiced approval",
              **_state("Continuous-unit silent publisher", ["viewer", "speech planner", "alignment gate"],
                       "This approved silent revision", "Media, course context, text, focus, code or review changes")}
    comparison = require_regression(attempt)
    if comparison is not None:
        result.update(revision_review=str(comparison), revision_review_sha256=common.sha(comparison))
    if bindings(attempt, narration) != current or any(common.sha(p) != h for p, h in reviews.items()):
        raise ValueError("Silent inputs/reviews changed during copy")
    _write(output / "delivery.json", result)
    return result


def verify_delivery(path):
    value = common.read_json(path)
    narration = common.read_json(value["narration"])
    if (value.get("source_contract") != units.SOURCE_CONTRACT or value.get("full_decode_passed") is not True
            or value.get("listening_reviewed") is not False or value.get("audio_status") != "pending_local_gpu_generation"
            or common.sha(value["video"]) != value.get("sha256")
            or value.get("bindings") != bindings(value["attempt"], value["narration"])
            or value.get("duration") != common.read_json(Path(value["attempt"]) / "timeline.json")["duration"]
            or value.get("visual_review") != narration.get("visual_review")
            or value.get("visual_review_sha256") != narration.get("visual_review_sha256")):
        raise ValueError("Current approved silent visual/text/course delivery changed")
    for key in ("visual_review", "narration_review"):
        if common.sha(value[key]) != value.get(key + "_sha256"):
            raise ValueError("Current independent editorial review changed")
    require_review(value["attempt"], value["visual_review"])
    require_review(value["attempt"], value["narration_review"], narration=value["narration"])
    comparison = require_regression(value["attempt"])
    if comparison is not None and (value.get("revision_review") != str(comparison)
                                   or value.get("revision_review_sha256") != common.sha(comparison)):
        raise ValueError("Current approved content regression changed")
    return value


def _snapshot(path):
    path = Path(path).resolve()
    payload = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "text": payload.decode("utf-8")}


def _snapshot_value(row):
    # JSON written by this publisher is UTF-8 without a BOM; retain exact bytes.
    if hashlib.sha256(row["text"].encode("utf-8")).hexdigest() != row["sha256"]:
        raise ValueError("Original plan source snapshot text/hash changed")
    if common.sha(row["path"]) != row["sha256"]:
        raise ValueError("Original plan source artifact drifted; never rewrite its receipt")
    return json.loads(row["text"].lstrip("\ufeff"))


def _reference(plan):
    vox.validate_plan(plan)
    if (common.sha(plan["reference_source"]) != vox.REFERENCE_SHA256
            or common.sha(plan["reference_receipt"]) != plan.get("reference_receipt_sha256")
            or common.read_json(plan["reference_receipt"]).get("wav_sha256") != vox.REFERENCE_SHA256):
        raise ValueError("Selected V01 reference or original reference receipt changed")


def speech_plan(delivery_path, reference, target):
    target = _fresh(target)
    delivery_path, reference = Path(delivery_path).resolve(), Path(reference).resolve()
    delivery = verify_delivery(delivery_path)
    attempt = Path(delivery["attempt"])
    narration = common.read_json(delivery["narration"])
    receipt = reference.with_suffix(".receipt.json")
    paths = {"delivery": delivery_path, "narration": Path(delivery["narration"]),
             "focuses": attempt / "focus-events.json", "timeline": attempt / "timeline.json",
             "visual_review": Path(delivery["visual_review"]), "narration_review": Path(delivery["narration_review"])}
    source = {"delivery": str(delivery_path), "delivery_sha256": common.sha(delivery_path),
              "video": delivery["video"], "video_sha256": delivery["sha256"],
              "focuses": str(paths["focuses"]), "focuses_sha256": common.sha(paths["focuses"])}
    result = {"schema_version": 2, "source_contract": units.SOURCE_CONTRACT, "focus_scope": units.FOCUS_SCOPE,
              "synthetic_reference": True, "reference_kind": "selected_synthetic_reference",
              "reference_sha256": vox.REFERENCE_SHA256, "reference_source": str(reference),
              "reference_receipt": str(receipt), "reference_receipt_sha256": common.sha(receipt),
              "reference_text": vox.audition.TEXT, "generation": dict(vox.GENERATION),
              "segments": units.transport_segments(narration), "source": source,
              "source_snapshot": {name: _snapshot(path) for name, path in paths.items()},
              "worker_sha256": common.sha(vox.__file__), "helper_sha256": vox.HELPER_SHA256,
              "execution_status": "prepared_not_generated",
              **_state("Continuous-unit speech planner", ["unchanged flexible VoxCPM worker", "phrase aligner", "unit publisher"],
                       "One original text/voice/model plan; visual-only revisions may reuse its takes",
                       "Unit IDs/cues/text/references, voice, model, worker, receipts or source snapshot changes")}
    verify_speech_source(result)
    if verify_delivery(delivery_path) != delivery:
        raise ValueError("Current silent delivery changed while preparing speech plan")
    _write(target, result)
    return result


def verify_speech_source(plan):
    """Validate ORIGINAL provenance without claiming its old visual approval is current."""
    _reference(plan)
    forced.validate_plan(plan)
    if (plan.get("source_contract") != units.SOURCE_CONTRACT or plan.get("focus_scope") != units.FOCUS_SCOPE
            or "alignment_smoke_source" in plan
            or plan.get("worker_sha256") != common.sha(vox.__file__) or plan.get("helper_sha256") != vox.HELPER_SHA256):
        raise ValueError("Require a new-contract original unit TTS plan and unchanged worker")
    snapshots = {name: _snapshot_value(plan["source_snapshot"][name]) for name in
                 ("delivery", "narration", "focuses", "timeline", "visual_review", "narration_review")}
    original, narration = snapshots["delivery"], snapshots["narration"]
    units.validate_narration(narration, snapshots["timeline"], snapshots["focuses"])
    if (original.get("source_contract") != units.SOURCE_CONTRACT
            or original.get("full_decode_passed") is not True
            or original.get("bindings", {}).get("source_contract") != units.SOURCE_CONTRACT
            or original["bindings"].get("narration_sha256") != plan["source_snapshot"]["narration"]["sha256"]
            or narration.get("visual_bindings") != _visual_part(original["bindings"])
            or plan["segments"] != units.transport_segments(narration)
            or plan["source"] != {"delivery": plan["source_snapshot"]["delivery"]["path"],
                                  "delivery_sha256": plan["source_snapshot"]["delivery"]["sha256"],
                                  "video": original["video"], "video_sha256": original["sha256"],
                                  "focuses": plan["source_snapshot"]["focuses"]["path"],
                                  "focuses_sha256": plan["source_snapshot"]["focuses"]["sha256"]}
            or original["bindings"].get("focuses_sha256") != plan["source"]["focuses_sha256"]
            or common.sha(original["video"]) != original["sha256"]):
        raise ValueError("Original speech plan differs from its approved source snapshot")
    for name in ("visual_review", "narration_review"):
        stage = "visual" if name == "visual_review" else "narration"
        expected = narration["visual_bindings"] if stage == "visual" else original["bindings"]
        authors = [(original["bindings"]["visual_author_agent"], original["bindings"]["visual_author_context"])]
        if stage == "narration":
            authors.append(_identity(narration, "author"))
        _review(snapshots[name], stage, expected, authors=authors,
                prior_reviews=[snapshots["visual_review"]] if stage == "narration" else [])
        quality.validate_editorial_review(snapshots[name], duration=original["duration"], stage=stage)
        if (original[name] != plan["source_snapshot"][name]["path"]
                or original[name + "_sha256"] != plan["source_snapshot"][name]["sha256"]):
            raise ValueError("Original editorial receipt changed")
    return snapshots


def _speech_inputs(plan, plan_path, speech, inputs=None):
    speech = Path(speech).resolve()
    expected_hash = common.sha(plan_path)
    if common.sha(speech / "plan.json") != expected_hash:
        raise ValueError("Worker archived plan differs from original TTS plan")
    state = common.read_json(speech / "state.json")
    ids = [row["id"] for row in plan["segments"]]
    if (state.get("status") != vox.ACCEPTANCE or state.get("attempted") != ids or state.get("done") != ids
            or type(state.get("call_count")) is not int or state["call_count"] != len(ids)
            or type(state.get("model_load_count")) is not int or state["model_load_count"] != 1
            or state.get("plan_sha256") != expected_hash):
        raise ValueError("Each meaning unit requires exactly one original TTS call")
    expected_inputs = [{"wav": str(speech / f"{row['id']}.wav"),
                        "receipt": str(speech / f"{row['id']}.receipt.json")} for row in plan["segments"]]
    for item in expected_inputs:
        if common.sha(item["wav"]) != common.read_json(item["receipt"]).get("wav_sha256"):
            raise ValueError("Original WAV differs from its speech receipt")
    if inputs is not None and (len(inputs) != len(expected_inputs) or any(
            Path(item[key]).resolve() != Path(expected[key]) for item, expected in zip(inputs, expected_inputs, strict=True)
            for key in ("wav", "receipt"))):
        raise ValueError("Alignment must retain every original unit WAV and receipt")
    durations, checked = legacy.speech_inputs(plan, plan_path, expected_inputs if inputs is None else inputs)
    setup = common.read_json(speech / "setup-receipt.json")
    engine = common.read_json(speech / "engine.json")
    if (setup.get("model_id") != vox.audition.MODEL or setup.get("revision") != vox.audition.REVISION
            or vox.model_files_sha256(setup) != vox.MODEL_FILES_SHA256
            or engine.get("model") != vox.audition.MODEL or engine.get("revision") != vox.audition.REVISION
            or engine.get("model_files_sha256") != vox.MODEL_FILES_SHA256
            or engine.get("model_files") != setup["files"] or engine.get("load_options") != vox.audition.LOAD_OPTIONS
            or engine.get("packages", {}).get("voxcpm") != "2.0.3" or engine.get("model_load_count") != 1
            or common.sha(speech / "reference.wav") != vox.REFERENCE_SHA256
            or common.sha(speech / "source/flexible_voxcpm.py") != plan["worker_sha256"]
            or common.sha(speech / "source/voxcpm_audition.py") != vox.HELPER_SHA256):
        raise ValueError("Original worker/model/reference evidence changed")
    for index, (segment, item) in enumerate(zip(plan["segments"], checked, strict=True), 1):
        receipt = common.read_json(item["receipt"])
        request = receipt.get("request", {})
        expected = vox.generate_kwargs(segment, request.get("reference_wav_path", ""), plan["reference_text"])
        if (not state.get("reference_path") or request.get("reference_wav_path") != state["reference_path"]
                or common.canonical(request) != common.canonical(expected)
                or common.canonical(receipt.get("generate_kwargs")) != common.canonical(expected)
                or receipt.get("engine") != engine
                or receipt.get("seed") != vox.GENERATION["seed"] or receipt.get("seed_method") != vox.SEED_METHOD
                or type(receipt.get("segment_call_count")) is not int or receipt["segment_call_count"] != 1
                or type(receipt.get("model_load_count")) is not int or receipt["model_load_count"] != 1
                or type(receipt.get("call_count")) is not int or receipt["call_count"] != index
                or any(engine.get(key) != value for key, value in {
                    "plan_sha256": expected_hash, "setup_sha256": common.sha(speech / "setup-receipt.json"),
                    "worker_sha256": plan["worker_sha256"], "helper_sha256": vox.HELPER_SHA256,
                    "reference_sha256": vox.REFERENCE_SHA256, "seed_method": vox.SEED_METHOD}.items())):
            raise ValueError("Original speech receipt request, model settings or single-call evidence changed")
        if abs(receipt.get("duration_seconds", -1) - durations[index - 1]) > 1 / 48000:
            raise ValueError("Original WAV duration disagrees with its receipt")
    return durations, checked


def _speech_evidence(speech):
    speech = Path(speech)
    names = ("plan.json", "state.json", "engine.json", "setup-receipt.json", "reference.wav",
             "source/flexible_voxcpm.py", "source/voxcpm_audition.py")
    return {name: common.sha(speech / name) for name in names}


def _placement(delivery_path, plan_path, speech, timings_path, inputs=None):
    delivery = verify_delivery(delivery_path)
    plan = common.read_json(plan_path)
    original = verify_speech_source(plan)
    narration = common.read_json(delivery["narration"])
    if units.transport_segments(narration) != plan["segments"]:
        raise ValueError("TTS reuse requires identical ordered unit IDs/cues/text/references; different text cannot reuse")
    durations, inputs = _speech_inputs(plan, plan_path, speech, inputs)
    timings = common.read_json(timings_path)
    units.validate_timings(timings, narration, plan_sha256=common.sha(plan_path),
                           wav_sha256s=[item["sha256"] for item in inputs], durations=durations)
    evidence = forced.verify_production_timings(timings_path, plan_path=plan_path, speech=speech)
    if not evidence.get("files") or not units._hash(evidence.get("evidence_sha256")):
        raise ValueError("Production aligner verifier must return complete bound evidence")
    attempt = Path(delivery["attempt"])
    rows = units.schedule(common.read_json(attempt / "timeline.json"), narration,
                          common.read_json(attempt / "focus-events.json"), timings, durations=durations)
    source = {"delivery": str(Path(delivery_path).resolve()), "delivery_sha256": common.sha(delivery_path),
              "video": delivery["video"], "video_sha256": delivery["sha256"], "bindings": delivery["bindings"]}
    reuse = {"relation": "identical_text_voice_assets_revalidated_against_current_visuals",
             "original_source": plan["source"], "original_narration_sha256": plan["source_snapshot"]["narration"]["sha256"],
             "current_narration_sha256": common.sha(delivery["narration"]),
             "original_visual_approval_is_current": original["delivery"]["bindings"] == delivery["bindings"],
             "receipts_rewritten": False}
    return delivery, rows, inputs, source, reuse, evidence


def align(delivery, plan, speech, timings, output, *, producer_agent=None, producer_context=None):
    output = _fresh(output)
    producer = {"producer_agent": producer_agent, "producer_context": producer_context}
    _identity(producer, "producer")
    delivery, plan, speech, timings = map(lambda p: Path(p).resolve(), (delivery, plan, speech, timings))
    approved, rows, inputs, source, reuse, evidence = _placement(delivery, plan, speech, timings)
    result = {"source_contract": units.SOURCE_CONTRACT, "plan": str(plan), "plan_sha256": common.sha(plan),
              "speech": str(speech), "timings": str(timings), "timings_sha256": common.sha(timings),
              "speech_evidence": _speech_evidence(speech),
              "timing_evidence": evidence, **producer,
              "source": source, "duration": approved["duration"], "units": rows, "inputs": inputs, "reuse": reuse,
              "timing_scope": units.TIMING_SCOPE, "listening_reviewed": False,
              "processing": "Intact original WAV per unit; per-phrase focus intersection; no trim, speedup or global retiming",
              **_state("Continuous-unit phrase scheduler", ["independent audio alignment reviewer", "audio publisher"],
                       "This current delivery, original takes and forced alignment file",
                       "Current visual/text/course review, focus, timings, plan, worker or original speech evidence changes")}
    output.mkdir(parents=True, exist_ok=False)
    _write(output / "alignment.json", result)
    return result


def audio_bindings(alignment_path):
    value = common.read_json(alignment_path)
    if (value.get("source_contract") != units.SOURCE_CONTRACT or value.get("listening_reviewed") is not False
            or value.get("timing_scope") != units.TIMING_SCOPE or common.sha(value["plan"]) != value.get("plan_sha256")
            or common.sha(value["timings"]) != value.get("timings_sha256")
            or value.get("speech_evidence") != _speech_evidence(value["speech"])):
        raise ValueError("Original plan or measured phrase timing source changed")
    producer = _identity(value, "producer")
    delivery, rows, inputs, source, reuse, evidence = _placement(value["source"]["delivery"], value["plan"],
        value["speech"], value["timings"], value["inputs"])
    if (value.get("duration") != delivery["duration"] or value.get("units") != rows or value.get("inputs") != inputs
            or value.get("source") != source or value.get("reuse") != reuse or value.get("timing_evidence") != evidence):
        raise ValueError("Alignment differs from current per-phrase, intact-WAV placement and provenance")
    return {"source_contract": units.SOURCE_CONTRACT, "alignment_sha256": common.sha(alignment_path),
            "plan_sha256": value["plan_sha256"], "timings_sha256": value["timings_sha256"],
            "current_delivery_sha256": source["delivery_sha256"], "current_visual_text_bindings": delivery["bindings"],
            "producer_agent": producer[0], "producer_context": producer[1],
            "timing_evidence_sha256": evidence["evidence_sha256"], "aligner_sha256": common.sha(forced.__file__),
            "publisher_sha256": common.sha(__file__), "meaning_units_sha256": common.sha(units.__file__),
            "editorial_contract_sha256": common.sha(quality.__file__)}


def _alignment_people(value):
    silent = common.read_json(value["source"]["delivery"])
    plan = common.read_json(Path(silent["attempt"]) / "plan.json")
    text = common.read_json(silent["narration"])
    original = common.read_json(value["plan"])["source_snapshot"]["narration"]
    authors = [_identity(plan, "author"), _identity(text, "author"),
               _identity(json.loads(original["text"].lstrip("\ufeff")), "author"), _identity(value, "producer")]
    prior = [common.read_json(silent[key]) for key in ("visual_review", "narration_review")]
    return authors, prior


def _frame_pixels(path, time=None):
    command = [pilot.FFMPEG, "-v", "error"]
    if time is not None:
        command += ["-ss", str(time)]
    result = pilot.run([*command, "-i", path, "-map", "0:v:0", "-frames:v", "1", "-pix_fmt", "rgb24",
                        "-f", "hash", "-hash", "sha256", "-"], timeout=60)
    match = re.fullmatch(r"SHA256=([a-fA-F0-9]{64})\s*", result)
    if not match:
        raise ValueError("Missing decoded frame pixel fingerprint")
    return match[1].lower()


def _audio_frame(item, value, phrase, archived):
    from PIL import Image

    time = item.get("time")
    if (not units.finite(time) or not phrase["visual_start"] <= time < phrase["visual_end"]
            or not isinstance(item.get("finding"), str) or not item["finding"].strip()
            or item.get("video_sha256") != value["source"]["video_sha256"]
            or not isinstance(item.get("path"), str) or not Path(item["path"]).is_absolute()
            or common.sha(item["path"]) != item.get("sha256")):
        raise ValueError("Audio review requires current, in-phrase, video-bound frame observations")
    try:
        with Image.open(item["path"]) as frame:
            if frame.size != (1920, 1080):
                raise ValueError("Audio review frame dimensions differ from the current visual master")
            frame.verify()
    except (OSError, ValueError) as exc:
        raise ValueError("Audio review requires readable current-size image evidence") from exc
    known = any(Path(row["path"]).resolve() == Path(item["path"]).resolve() and row["sha256"] == item["sha256"]
                and abs(row["time"] - time) < 1e-8 for row in archived)
    if not known:
        # New review frames must be lossless extractions, not unrelated images.
        if Path(item["path"]).suffix.lower() != ".png" or (
                _frame_pixels(item["path"]) != _frame_pixels(value["source"]["video"], time)):
            raise ValueError("Review pixels do not match the current video at the declared timestamp")


def require_audio_review(alignment_path, review_path, current=None):
    """Check every actual reference, not a score or bare timing pass.

    Review units mirror alignment IDs/WAV hashes. Each reference declares its
    exact focus/text/visual_start/visual_end plus status and nonempty evidence
    [{time,path,sha256,video_sha256,finding}]. Existing bound render frames may be
    reused; extra PNGs are checked against decoded current-video pixels. This is
    visual timing review, never listening, pronunciation or student certification.
    """
    current = audio_bindings(alignment_path) if current is None else current
    value = common.read_json(alignment_path)
    authors, prior = _alignment_people(value)
    report = _review(common.read_json(review_path), "audio_alignment", current, authors=authors, prior_reviews=prior)
    silent = common.read_json(value["source"]["delivery"])
    archived = common.read_json(Path(silent["attempt"]) / "review-input.json")["frames"]
    checked = report.get("units")
    if not isinstance(checked, list) or len(checked) != len(value["units"]):
        raise ValueError("Independent audio review must cover every intact unit and actual reference")
    frames = {}
    for unit, item, row in zip(value["units"], value["inputs"], checked, strict=True):
        if (not isinstance(row, dict) or row.get("id") != unit["id"] or row.get("wav_sha256") != item["sha256"]
                or not units.finite(row.get("duration_seconds")) or row["duration_seconds"] != unit["duration_seconds"]
                or row.get("status") != "pass"
                or not isinstance(row.get("references"), list) or len(row["references"]) != len(unit["phrases"])):
            raise ValueError("Independent audio review lost or changed an original WAV or phrase")
        for phrase, detail in zip(unit["phrases"], row["references"], strict=True):
            if (not isinstance(detail, dict) or any(detail.get(key) != phrase[key]
                    for key in ("id", "focus", "text", "visual_start", "visual_end"))
                    or not units.finite(detail.get("visual_start")) or not units.finite(detail.get("visual_end"))
                    or detail.get("status") != "pass" or not isinstance(detail.get("evidence"), list) or not detail["evidence"]):
                raise ValueError("Every current reference requires its own actual frame evidence")
            for evidence in detail["evidence"]:
                if not isinstance(evidence, dict):
                    raise ValueError("Audio frame observations must be structured")
                _audio_frame(evidence, value, phrase, archived)
                frames[str(Path(evidence["path"]).resolve())] = evidence["sha256"]
    return {"review_sha256": common.sha(review_path), "frame_sha256": dict(sorted(frames.items()))}


def release_voiced(alignment_path, review_path, output):
    output = _fresh(output)
    alignment_path, review_path = Path(alignment_path).resolve(), Path(review_path).resolve()
    current = audio_bindings(alignment_path)
    review_evidence = require_audio_review(alignment_path, review_path, current)
    review_hash = common.sha(review_path)
    value = common.read_json(alignment_path)
    samples = array.array("h", [0]) * round(value["duration"] * 48000)
    for row, item in zip(value["units"], value["inputs"], strict=True):
        _, pcm = common.pcm_info(item["wav"])
        start = round(row["start"] * 48000)
        if start < 0 or start + len(pcm) > len(samples):
            raise ValueError("Cannot truncate intact unit WAV")
        samples[start:start + len(pcm)] = pcm
    output.mkdir(parents=True, exist_ok=False)
    mix = output / "voice-mix.wav"
    if sys.byteorder != "little":
        samples.byteswap()
    with mix.open("xb") as stream, wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(samples.tobytes())
    target = output / "voiced-preview.mp4"
    pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-i", value["source"]["video"], "-i", mix,
               "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "-1", "-map_chapters", "-1",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-sn", "-dn",
               "-movflags", "+faststart", target], timeout=600)
    check_video(pilot.probe(target), value["duration"])
    captions._media(target, value["duration"])
    captions._decode(target)
    if audio_bindings(alignment_path) != current or common.sha(review_path) != review_hash:
        raise ValueError("Audio inputs/review changed during publication")
    if require_audio_review(alignment_path, review_path, current) != review_evidence:
        raise ValueError("Independent audio review pixels changed during publication")
    result = {"source_contract": units.SOURCE_CONTRACT, "video": str(target), "sha256": common.sha(target),
              "duration": value["duration"], "bindings": current, "review": str(review_path),
              "review_sha256": review_hash, "full_decode_passed": True, "listening_reviewed": False,
              "review_evidence": review_evidence,
              "caption_status": "none", "scope": "Playable multi-focus voiced preview awaiting listening review",
              **_state("Continuous-unit audio publisher", ["listener", "caption producer", "auditor"],
                       "This current alignment and independent timing approval", "Media, alignment, current delivery or review changes")}
    _write(output / "delivery.json", result)
    return result


def _caption_source(alignment_path, delivery_path):
    current = audio_bindings(alignment_path)
    value, delivery = common.read_json(alignment_path), common.read_json(delivery_path)
    if (delivery.get("source_contract") != units.SOURCE_CONTRACT or delivery.get("caption_status") != "none"
            or delivery.get("bindings") != current or delivery.get("full_decode_passed") is not True
            or delivery.get("listening_reviewed") is not False or delivery.get("duration") != value["duration"]
            or common.sha(delivery["video"]) != delivery.get("sha256")
            or common.sha(delivery["review"]) != delivery.get("review_sha256")):
        raise ValueError("Require current uncaptioned voiced delivery; never burn a second caption set")
    if require_audio_review(alignment_path, delivery["review"], current) != delivery.get("review_evidence"):
        raise ValueError("Independent audio review frame evidence changed since voiced release")
    if any(path.name not in {Path(delivery["video"]).name, "delivery.json", "voice-mix.wav"}
           for path in Path(delivery["video"]).parent.iterdir()):
        raise ValueError("Voiced playback directory contains unbound files or subtitle sidecars")
    return value, delivery, {"audio_bindings": current, "alignment": captions._receipt(alignment_path),
                             "delivery": captions._receipt(delivery_path), "review": captions._receipt(delivery["review"])}


def _caption_data(value, style, timing_mode="phrase_ratio"):
    if timing_mode == "word_estimates":
        return word_captions.make_captions(value, style)
    if timing_mode != "phrase_ratio":
        raise ValueError("Unknown caption timing mode")
    # One display interval per aligned reference; this never segments the audio.
    phrases, origins = [], {}
    for unit in value["units"]:
        for phrase in unit["phrases"]:
            identity = f"{unit['id']}.{phrase['id']}"
            phrases.append({"id": identity, "text": phrase["text"], "start": phrase["visual_start"],
                            "end": phrase["visual_end"],
                            "duration_seconds": phrase["visual_end"] - phrase["visual_start"]})
            origins[identity] = {"meaning_unit_id": unit["id"], "reference_id": phrase["id"]}
    result = captions.make_captions({"duration": value["duration"], "segments": phrases}, style)
    for event in result["events"]:
        event.update(origins[event["utterance_id"]])
        event["timing"] = ("model_estimated_forced_alignment_phrase" if event["timing"] == "whole_utterance"
                           else "character_ratio_within_forced_aligned_phrase")
    result.update(timing_scope="Model-estimated forced-alignment phrase boundaries; line splits only use character ratios, not listening certification",
                  audio_continuity="Intact meaning-unit WAVs; caption boundaries never restart speech")
    return result


def caption_candidate(alignment, delivery, output, style=None, *, producer_agent=None, producer_context=None,
                      timing_mode="phrase_ratio"):
    output = _fresh(output)
    alignment, delivery = Path(alignment).resolve(), Path(delivery).resolve()
    producer = {"producer_agent": producer_agent, "producer_context": producer_context}
    _identity(producer, "producer")
    style = captions.validate_style(style)
    word_source = ({"word_caption_tools_sha256": common.sha(word_captions.__file__)}
                   if timing_mode == "word_estimates" else {})
    value, voiced, source = _caption_source(alignment, delivery)
    size = captions._media(voiced["video"], value["duration"])
    filters = pilot.run([pilot.FFMPEG, "-hide_banner", "-filters"])
    if not re.search(r"\bass\s+V->V\b", filters):
        raise ValueError("FFmpeg requires libass")
    data = _caption_data(value, style, timing_mode)
    ass = captions.make_ass(data, style, **size)
    audio_hash = captions._audio_hash(voiced["video"])
    output.mkdir(parents=True, exist_ok=False)
    (output / "support").mkdir()
    for name, record in (("style.json", style), ("captions.json", data), ("source-receipts.json", source)):
        _write(output / name, record)
    with (output / "support/captions.ass").open("x", encoding="utf-8") as stream:
        stream.write(ass)
    filename = str(output / "support/captions.ass").replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")
    for character in "[],;":
        filename = filename.replace(character, "\\" + character)
    target = output / "candidate.mp4"
    pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-i", voiced["video"], "-map", "0:v:0", "-map", "0:a:0",
               "-map_metadata", "-1", "-map_chapters", "-1", "-vf", f"ass=filename='{filename}'",
               "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
               "-c:a", "copy", "-sn", "-dn", "-movflags", "+faststart", target], timeout=1800)
    if captions._media(target, value["duration"]) != size or captions._audio_hash(target) != audio_hash:
        raise ValueError("Caption encode changed image dimensions or copied audio packets")
    captions._decode(target)
    if (_caption_source(alignment, delivery)[2] != source
            or word_source and common.sha(word_captions.__file__) != word_source["word_caption_tools_sha256"]):
        raise ValueError("Caption sources changed during encoding")
    _write(output / "candidate.json", {"source_contract": units.SOURCE_CONTRACT, "status": "candidate_not_released",
           "alignment": str(alignment), "voiced_delivery": str(delivery), **producer,
           "duration": value["duration"], "size": size, "audio_packet_sha256": audio_hash,
           "caption_timing_mode": timing_mode, **word_source,
           "full_decode_passed": True, "listening_reviewed": False,
           **_state("Continuous-unit caption producer", ["independent pixel reviewer", "caption publisher"],
                    "This create-only candidate", "Style, ASS, captions, source media, code or audio inputs change")})
    current = _caption_bindings(output)
    _write(output / "bindings.json", current)
    return current


def _caption_bindings(candidate):
    candidate = Path(candidate).resolve()
    if any(path.suffix.lower() in {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"} for path in candidate.iterdir()):
        raise ValueError("No auto-loaded subtitle sidecars in candidate playback directory")
    manifest = common.read_json(candidate / "candidate.json")
    _identity(manifest, "producer")
    if (manifest.get("source_contract") != units.SOURCE_CONTRACT or manifest.get("status") != "candidate_not_released"
            or manifest.get("full_decode_passed") is not True or manifest.get("listening_reviewed") is not False):
        raise ValueError("Require an honest fully decoded new-contract caption candidate")
    value, _, source = _caption_source(manifest["alignment"], manifest["voiced_delivery"])
    if source != common.read_json(candidate / "source-receipts.json"):
        raise ValueError("Caption source receipt changed")
    style = captions.validate_style(common.read_json(candidate / "style.json"))
    timing_mode = manifest.get("caption_timing_mode", "phrase_ratio")
    if (timing_mode == "word_estimates"
            and manifest.get("word_caption_tools_sha256") != common.sha(word_captions.__file__)):
        raise ValueError("Word-caption timing tools changed")
    data = _caption_data(value, style, timing_mode)
    if (data != common.read_json(candidate / "captions.json") or manifest["duration"] != value["duration"]
            or captions.make_ass(data, style, **manifest["size"]) != (candidate / "support/captions.ass").read_text(encoding="utf-8")):
        raise ValueError("Caption text, timing, style or ASS changed")
    result = {"stage": "captions", "source_contract": units.SOURCE_CONTRACT, "candidate": str(candidate),
            "publisher_sha256": common.sha(__file__), "caption_tools_sha256": common.sha(captions.__file__),
            "meaning_units_sha256": common.sha(units.__file__), "audio_bindings": source["audio_bindings"],
            "files": {name: common.sha(candidate / name) for name in captions.ARTIFACTS}}
    if timing_mode == "word_estimates":
        result["word_caption_tools_sha256"] = common.sha(word_captions.__file__)
    return result


def caption_bindings(candidate):
    current = _caption_bindings(candidate)
    frozen = Path(candidate) / "bindings.json"
    if current != common.read_json(frozen) or frozen.read_text(encoding="utf-8") != json.dumps(current, ensure_ascii=False, indent=2):
        raise ValueError("Frozen caption bindings changed")
    return current


def release_captioned(candidate, review, output):
    output = _fresh(output)
    candidate, review = Path(candidate).resolve(), Path(review).resolve()
    current = caption_bindings(candidate)
    manifest = common.read_json(candidate / "candidate.json")
    authors, prior = _alignment_people(common.read_json(manifest["alignment"]))
    authors.append(_identity(manifest, "producer"))
    voiced = common.read_json(manifest["voiced_delivery"])
    prior.append(common.read_json(voiced["review"]))
    _review(common.read_json(review), "captions", current, authors=authors, prior_reviews=prior)
    captions._caption_review(review, current, manifest["producer_agent"])
    review_hash = common.sha(review)
    video = candidate / "candidate.mp4"
    if (captions._media(video, manifest["duration"]) != manifest["size"]
            or captions._audio_hash(video) != manifest["audio_packet_sha256"]
            or captions._audio_hash(common.read_json(manifest["voiced_delivery"])["video"]) != manifest["audio_packet_sha256"]):
        raise ValueError("Caption candidate dimensions/audio changed")
    captions._decode(video)
    if caption_bindings(candidate) != current or common.sha(review) != review_hash:
        raise ValueError("Caption candidate or independent review changed")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "captioned.mp4"
    _copy(video, target)
    if (common.sha(target) != current["files"]["candidate.mp4"] or caption_bindings(candidate) != current
            or common.sha(review) != review_hash):
        raise ValueError("Captioned delivery copy/source changed")
    captions._clean_playback(output, target.name)
    result = {"source_contract": units.SOURCE_CONTRACT, "video": str(target), "sha256": common.sha(target),
              "duration": manifest["duration"], "bindings": current, "review": str(review), "review_sha256": review_hash,
              "full_decode_passed": True, "listening_reviewed": False, "caption_status": "single_burned_set",
              "audio_packet_sha256": manifest["audio_packet_sha256"], "scope": "Playable single-caption preview awaiting listening review",
              **_state("Continuous-unit caption publisher", ["listener", "viewer", "auditor"],
                       "This independently pixel-reviewed candidate", "Candidate, media, source, style or review changes")}
    _write(output / "delivery.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fields = {"bindings": ("attempt",), "install-narration": ("attempt", "draft", "visual-review", "output"),
              "release-silent": ("attempt", "narration", "visual-review", "narration-review", "output"),
              "speech-plan": ("delivery", "reference", "output"),
              "align": ("delivery", "plan", "speech", "timings", "output"), "audio-bindings": ("alignment",),
              "release-voiced": ("alignment", "review", "output"),
              "caption-candidate": ("alignment", "delivery", "output"), "caption-bindings": ("candidate",),
              "release-captioned": ("candidate", "review", "output")}
    for name, names in fields.items():
        command = commands.add_parser(name)
        for field in names:
            command.add_argument("--" + field, required=True, type=Path)
        if name == "bindings":
            command.add_argument("--narration", type=Path)
        if name == "caption-candidate":
            command.add_argument("--style", type=Path)
        if name in {"align", "caption-candidate"}:
            command.add_argument("--producer-agent", required=True)
            command.add_argument("--producer-context", required=True)
    args = parser.parse_args(argv)
    handlers = {"bindings": lambda: bindings(args.attempt, args.narration),
                "install-narration": lambda: install_narration(args.attempt, args.draft, args.visual_review, args.output),
                "release-silent": lambda: release_silent(args.attempt, args.narration, args.visual_review, args.narration_review, args.output),
                "speech-plan": lambda: speech_plan(args.delivery, args.reference, args.output),
                "align": lambda: align(args.delivery, args.plan, args.speech, args.timings, args.output,
                    producer_agent=args.producer_agent, producer_context=args.producer_context),
                "audio-bindings": lambda: audio_bindings(args.alignment),
                "release-voiced": lambda: release_voiced(args.alignment, args.review, args.output),
                "caption-candidate": lambda: caption_candidate(args.alignment, args.delivery, args.output,
                    None if args.style is None else common.read_json(args.style),
                    producer_agent=args.producer_agent, producer_context=args.producer_context),
                "caption-bindings": lambda: caption_bindings(args.candidate),
                "release-captioned": lambda: release_captioned(args.candidate, args.review, args.output)}
    print(json.dumps(handlers[args.command](), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
