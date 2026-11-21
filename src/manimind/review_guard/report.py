"""Review report schema, skeleton generator and pre-submission check.

Replaces the per-reviewer ``review_tools.py`` / ``build_report.py`` /
``verify_report.py`` scripts found under ``runtime/sessions/*-reviewer/``.
The frozen gates (``unit_film._review``, ``understanding_quality``,
``content_regression``) stay authoritative; this module only makes a report
*structurally* submittable before it reaches them and keeps every field those
gates read with the same name and meaning.

Status is a fixed enum:

* ``pass`` -- the only status a release gate accepts;
* ``revise`` -- a judgment with blocking findings;
* ``incomplete`` -- the reviewer could not cover what the packet requires yet
  (needs ``incomplete_reason``); never a judgment, never gate-ready;
* ``blocked`` -- the review cannot proceed (missing tool/media, binding
  mismatch); needs ``blocked_reason``.

``playback_coverage`` is a new, non-blocking honesty field: it records how
the reviewer actually watched (``sampled`` stills/decoding,
``continuous_1x_partial`` or ``continuous_1x_complete``) and tool limits.  It
never upgrades or downgrades ``status``; a coverage gap is not by itself a
reason to re-render identical content.

Writer: the independent reviewer.  Consumers: coordinator, frozen gates.
Lifecycle: the bound attempt only.  Invalidation: any binding change.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys

STATUSES = ("pass", "revise", "incomplete", "blocked")
JUDGMENT_STATUSES = ("pass", "revise")
PLAYBACK_LEVELS = ("sampled", "continuous_1x_partial", "continuous_1x_complete")
STAGES = ("visual", "narration", "content_regression", "audio_alignment", "captions")
EDITORIAL_STAGES = ("visual", "narration")
# Flags unit_film._review requires to be honestly false.
HONEST_FALSE = ("listening_reviewed", "student_tested")
HONEST_FALSE_IF_PRESENT = ("naturalness_approved", "asr_accuracy_certified", "pronunciation_approved")
QUALITY_DIMENSIONS = ("science", "causality", "visual_explanation", "finish", "pacing", "interest")
EDITORIAL_CHECKS = ("mechanism", "attention", "pacing", "meaning_alignment", "transfer")


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def skeleton(stage, bindings, reviewer_agent, reviewer_context, *, attempt=None):
    """A report with every gate-read field present and status ``incomplete``."""
    if stage not in STAGES:
        raise ValueError(f"Unknown stage {stage!r}")
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError("Copy the packet's exact bindings; never rebuild them by hand")
    if not _text(reviewer_agent) or not _text(reviewer_context):
        raise ValueError("Require explicit reviewer_agent and reviewer_context")
    report = {
        "schema_version": 1, "stage": stage, "reviewer_role": "independent",
        "reviewer_agent": reviewer_agent, "reviewer_context": reviewer_context,
        "bindings": dict(bindings), "status": "incomplete",
        "incomplete_reason": "Skeleton generated; evidence not yet recorded",
        "release_authorized": False, "blocking_findings": [],
        "listening_reviewed": False, "student_tested": False,
        "naturalness_approved": False, "asr_accuracy_certified": False, "pronunciation_approved": False,
        "playback_coverage": {"level": "sampled", "segments": [], "tool_limitations": ""},
        "writer": reviewer_agent, "consumers": ["coordinator", "frozen release gate"],
        "lifecycle": "Only the bound attempt and evidence",
        "invalidation": "Any bound input, media, evidence or report change",
    }
    if attempt is not None:
        report["attempt"] = str(attempt)
    if stage in EDITORIAL_STAGES:
        report.update(
            action="review",
            viewer_test={"can_explain": "", "missing_links": [], "transfer_question": "", "supported_answer": ""},
            quality={name: {"rating": None, "evidence": ""} for name in QUALITY_DIMENSIONS},
            editorial_checks={name: {"status": None, "evidence": []} for name in EDITORIAL_CHECKS},
        )
    return report


def _coverage_errors(value, duration):
    errors, warnings = [], []
    if value is None:
        warnings.append("playback_coverage missing: state how the media was actually watched")
        return errors, warnings
    if not isinstance(value, dict) or value.get("level") not in PLAYBACK_LEVELS:
        return [f"playback_coverage.level must be one of {PLAYBACK_LEVELS}"], warnings
    segments = value.get("segments", [])
    if not isinstance(segments, list):
        return ["playback_coverage.segments must be a list"], warnings
    for index, row in enumerate(segments):
        if (not isinstance(row, dict) or not _finite(row.get("start")) or not _finite(row.get("end"))
                or row["start"] < 0 or row["end"] <= row["start"]
                or duration is not None and row["end"] > duration + 1e-6):
            errors.append(f"playback_coverage.segments[{index}] needs 0 <= start < end <= duration")
    if not isinstance(value.get("tool_limitations", ""), str):
        errors.append("playback_coverage.tool_limitations must be text")
    level = value["level"]
    if level.startswith("continuous_1x") and not segments:
        errors.append(f"{level} requires the actually watched segments")
    if level == "continuous_1x_complete" and duration is not None and not errors:
        covered = 0.0  # contiguous coverage from t=0, tolerating 0.5 s seams
        for row in sorted(segments, key=lambda r: r["start"]):
            if row["start"] > covered + 0.5:
                break
            covered = max(covered, row["end"])
        if covered < duration - 0.5:
            errors.append(f"continuous_1x_complete but watched segments stop at {covered:.2f}s of {duration:.2f}s")
    if level == "sampled" and not value.get("tool_limitations"):
        warnings.append("sampled coverage: record tool limitations for normal-speed viewing")
    return errors, warnings


def precheck(report, *, expected_bindings=None, stage=None, duration=None):
    """Return ``{"valid", "gate_ready", "errors", "warnings"}`` without raising.

    ``valid`` means the report is structurally honest and submittable;
    ``gate_ready`` additionally means its status is ``pass`` (the only status
    the frozen gates accept).  This never certifies the judgment itself.
    """
    errors, warnings = [], []
    if not isinstance(report, dict):
        return {"valid": False, "gate_ready": False, "errors": ["Report must be a JSON object"], "warnings": []}
    if report.get("stage") not in STAGES:
        errors.append(f"stage must be one of {STAGES}")
    elif stage is not None and report["stage"] != stage:
        errors.append(f"stage {report['stage']!r} does not match the requested {stage!r}")
    if report.get("reviewer_role") != "independent":
        errors.append("reviewer_role must be 'independent'")
    for key in ("reviewer_agent", "reviewer_context"):
        if not _text(report.get(key)):
            errors.append(f"{key} must be an explicit non-empty id without surrounding spaces")
    for alias in ("agentID", "agent_id"):
        if alias in report and report[alias] != report.get("reviewer_agent"):
            errors.append(f"{alias} disagrees with reviewer_agent")
    bindings = report.get("bindings")
    if not isinstance(bindings, dict) or not bindings:
        errors.append("bindings must be the packet's non-empty bindings object")
    elif not all(isinstance(k, str) and isinstance(v, str) and v for k, v in bindings.items()):
        errors.append("bindings must map names to non-empty strings (hashes/contract ids)")
    elif expected_bindings is not None and bindings != expected_bindings:
        missing = sorted(set(expected_bindings) - set(bindings))
        extra = sorted(set(bindings) - set(expected_bindings))
        changed = sorted(k for k in set(bindings) & set(expected_bindings) if bindings[k] != expected_bindings[k])
        errors.append(f"bindings differ from the packet: missing={missing} extra={extra} changed={changed}")
    status = report.get("status")
    if status not in STATUSES:
        errors.append(f"status must be one of {STATUSES}")
    if type(report.get("release_authorized")) is not bool:
        errors.append("release_authorized must be true or false")
    elif report["release_authorized"] and status != "pass":
        errors.append("Only status=pass may set release_authorized=true")
    elif status == "pass" and not report["release_authorized"]:
        errors.append("status=pass must declare release_authorized=true; otherwise use revise")
    findings = report.get("blocking_findings")
    if not isinstance(findings, list):
        errors.append("blocking_findings must be a list")
    elif status == "pass" and findings:
        errors.append("status=pass cannot carry blocking findings")
    elif status == "revise" and not findings:
        errors.append("status=revise needs at least one concrete blocking finding")
    if status == "blocked" and not _text(report.get("blocked_reason")):
        errors.append("status=blocked needs blocked_reason")
    if status == "incomplete" and not _text(report.get("incomplete_reason")):
        errors.append("status=incomplete needs incomplete_reason")
    for key in HONEST_FALSE:
        if report.get(key) is not False:
            errors.append(f"{key} must be false; this review cannot certify it")
    for key in HONEST_FALSE_IF_PRESENT:
        if report.get(key, False) is not False:
            errors.append(f"{key} must be false or absent")
    more_errors, more_warnings = _coverage_errors(report.get("playback_coverage"), duration)
    errors += more_errors
    warnings += more_warnings
    if report.get("stage") in EDITORIAL_STAGES and status in JUDGMENT_STATUSES:
        from manimind.review.understanding_quality import validate_editorial_review
        try:
            validate_editorial_review(report, duration=duration, stage=report["stage"])
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            errors.append(f"editorial schema: {error}")
    valid = not errors
    return {"valid": valid, "gate_ready": valid and status == "pass", "status": status,
            "errors": errors, "warnings": warnings}


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8").lstrip("﻿"))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m manimind.review_guard.report")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("skeleton", help="write a report skeleton bound to a packet")
    make.add_argument("--packet", required=True)
    make.add_argument("--stage", required=True, choices=STAGES)
    make.add_argument("--agent", required=True)
    make.add_argument("--context", required=True)
    make.add_argument("--out", required=True)
    check = sub.add_parser("precheck", help="validate stage, reviewer_role, bindings and status before submission")
    check.add_argument("report")
    check.add_argument("--packet", help="packet whose bindings must match exactly")
    check.add_argument("--stage", choices=STAGES)
    check.add_argument("--duration", type=float)
    check.add_argument("--registry", help="reviewer identity registry to check against")
    check.add_argument("--lesson")
    check.add_argument("--version")
    args = parser.parse_args(argv)
    if args.command == "skeleton":
        packet = _read(args.packet)
        value = skeleton(args.stage, packet.get("bindings"), args.agent, args.context, attempt=packet.get("attempt"))
        out = Path(args.out)
        if os.path.lexists(out):
            raise FileExistsError(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        result, code = {"written": str(out.resolve()), "status": value["status"]}, 0
    else:
        report = _read(args.report)
        expected = _read(args.packet).get("bindings") if args.packet else None
        result = precheck(report, expected_bindings=expected, stage=args.stage, duration=args.duration)
        if args.registry:
            from . import identity
            if not (args.lesson and args.version):
                parser.error("--registry needs --lesson and --version")
            try:
                identity.check(identity.load(args.registry), report.get("reviewer_agent"),
                               report.get("reviewer_context"), args.lesson, args.version, report.get("stage"))
            except ValueError as error:
                result["errors"].append(f"identity: {error}")
                result["valid"] = result["gate_ready"] = False
        code = 0 if result["valid"] else 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
