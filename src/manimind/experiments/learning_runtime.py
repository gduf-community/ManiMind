"""Isolate ManimGL's import-time CLI parser from the orchestration CLI."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import time

from .freeform_agent import api_reference
from .freeform_isolated import decode_object
from .freeform_team import now
from .learning_workflow import LearningWorkflow, prepare_case, freeze_holdout
from manimind.postproduce import pilot


def preload_runtime():
    original = sys.argv
    try:
        sys.argv = [original[0]]
        importlib.import_module("manimlib")
    finally:
        sys.argv = original


def bind_adapter(experiment):
    path = experiment.context / "runtime-adapter.json"
    source = Path(__file__).resolve()
    if path.exists():
        if pilot.read_json(path)["sha256"] != pilot.sha256(source):
            raise ValueError("Bound runtime adapter changed; do not resume automatically")
        return
    pilot.write_json(path, {
        "source": str(source), "sha256": pilot.sha256(source), "adopted_at": now(),
        "completed_requests_before_adapter": sum(len(experiment.role_requests(r)) for r in ("creator", "director", "reviewer")),
        "scope": "CLI argument isolation only; no candidate or prompt edits",
        "writer": "runtime launcher", "consumers": ["launcher", "auditor"],
        "lifecycle": "Immutable execution-adapter binding for this run",
        "invalidation": "Any adapter implementation hash change",
    })


def recover_read_api(experiment):
    """Finish only a proven read-only query; never replay an unknown media action."""
    if (experiment.session / "team.lock").exists():
        raise ValueError("Existing team lock blocks recovery")
    experiment.verify()
    team = pilot.read_json(experiment.team_path)
    pending = team.get("inflight")
    if (team["status"] != "interrupted" or not pending or pending["phase"] != "tool"
            or pending["turn"] != team["turn"] + 1):
        raise ValueError("Only an interrupted read_api tool checkpoint can be recovered")
    step = Path(pending["step"]).resolve()
    if not step.is_relative_to(experiment.session.resolve()) or (step / "result.json").exists():
        raise ValueError("Unexpected step or an already-recorded tool result")
    command_record = pilot.read_json(step / "command.json")
    command = command_record["command"]
    request = Path(command_record["request"]).resolve()
    if command.get("action") != "read_api" or pending["role"] != command_record["role"]:
        raise ValueError("Only the original read_api action may be recovered")
    if not request.is_relative_to(experiment.role_directory(pending["role"]).resolve()):
        raise ValueError("Request belongs to another role or project")
    record = pilot.read_json(request / "record.json")
    if (record["status"] != "received" or record["role"] != pending["role"]
            or record["stage"] != f"team-{pending['turn']:04d}"
            or pilot.sha256(request / "input.json") != record["input_sha256"]
            or pilot.sha256(request / "answer.txt") != record["answer_sha256"]
            or record["answer_sha256"] != command_record["answer_sha256"]
            or decode_object((request / "answer.txt").read_text()) != command):
        raise ValueError("Original received request evidence changed")
    watched = [p for p in [experiment.spec_path, experiment.out / "candidate.py",
                           experiment.out / "timeline.json"] if p.exists()]
    before = {str(p): pilot.sha256(p) for p in watched}
    start = time.monotonic()
    try:
        result = api_reference(command["args"]["symbols"])
    except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        result = {"error_type": type(exc).__name__, "raw_error": str(exc)}
    if {str(p): pilot.sha256(p) for p in watched} != before:
        raise ValueError("Read-only recovery changed candidate media inputs")
    pilot.write_json(step / "readonly-recovery.json", {
        "writer": "runtime launcher", "consumers": ["auditor"],
        "lifecycle": "Permanent technical-recovery receipt", "invalidation": "Bound request or source hashes change",
        "reason": "ManimGL import parsed orchestration arguments before API validation",
        "request": str(request), "request_record_sha256": pilot.sha256(request / "record.json"),
        "candidate_hashes_unchanged": before, "provider_called": False,
        "adapter_sha256": pilot.sha256(Path(__file__)), "recovered_at": now(),
    })
    pilot.write_json(step / "result.json", result)
    actor = team["actors"][pending["role"]]
    actor["history"].append({"turn": pending["turn"], "notes": command.get("notes"),
                             "observations": command.get("observations"), "action": "read_api", "result": result})
    team["tool_durations"].append({"turn": pending["turn"], "role": pending["role"],
                                   "action": "read_api", "seconds": time.monotonic() - start,
                                   "read_only_recovery": True})
    team.update(status="running", turn=pending["turn"], inflight=None)
    experiment.team = team
    experiment.save_team()
    experiment.report()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--case")
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--recover-read-api", action="store_true")
    parser.add_argument("--resume-received-request", action="store_true")
    parser.add_argument("--freeze-holdout", action="store_true")
    args = parser.parse_args()
    if args.freeze_holdout:
        print(freeze_holdout(args.study.resolve(), args.profile.resolve()))
        return
    if not args.case:
        parser.error("--case is required")
    preload_runtime()
    path = prepare_case(args.study.resolve(), args.case, args.profile.resolve())
    experiment = LearningWorkflow(path)
    experiment.initialize()
    bind_adapter(experiment)
    if args.initialize_only:
        return
    if args.recover_read_api:
        recover_read_api(experiment)
    experiment.run_team(resume_received=args.resume_received_request)


if __name__ == "__main__":
    main()
