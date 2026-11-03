"""Resume a proven capacity-failed visual reviewer detail, without restarting production."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time

from .codex_cli_team import native_system
from .freeform_isolated import decode_object
from .freeform_review_cycle import validate_review
from .freeform_team import now
from .learning_runtime import bind_adapter, preload_runtime
from .sol_visual_first import SolVisualFirst
from .subscription_quota import RateReader, summarize
from manimind.postproduce import pilot
from manimind.review.learning_quality import QUALITY_FORMAT, validate_learning_review


def genuine_answer(directory, role):
    record = pilot.read_json(directory / "record.json")
    if (record["status"] != "received" or record["role"] != role
            or record["input_sha256"] != pilot.sha256(directory / "input.json")
            or record["answer_sha256"] != pilot.sha256(directory / "answer.txt")):
        raise ValueError("Received request provenance changed")
    return decode_object((directory / "answer.txt").read_text())


def capacity_failure(directory):
    record = pilot.read_json(directory / "record.json")
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines() if line.strip()]
    if (record["status"] != "failed" or record.get("returncode") != 1
            or record.get("error_type") != "ProviderStopped" or record.get("usage")
            or record["input_sha256"] != pilot.sha256(directory / "input.json")
            or any(e.get("type") == "turn.completed" for e in events)
            or not any(e.get("type") == "turn.failed" and e.get("error", {}).get("message")
                       == "Selected model is at capacity. Please try a different model." for e in events)):
        raise ValueError("Not a confirmed capacity failure; never replay unknown billing")
    return record


def checkpoint(experiment):
    """Read-only preflight. No request, state advance, extraction or render."""
    experiment.verify()
    for name in ("team.lock", "launch.lock"):
        if (experiment.session / name).exists():
            raise ValueError("Existing execution lock blocks recovery")
    launcher = experiment.session / "launcher.json"
    if launcher.exists():
        try:
            os.kill(pilot.read_json(launcher)["pid"], 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError("Original runner is still alive")
    for role in ("director", "creator", "reviewer"):
        for path in experiment.role_requests(role):
            if pilot.read_json(path)["status"] in {"started", "interrupted"}:
                raise ValueError("Unresolved role request blocks recovery")
    team = pilot.read_json(experiment.team_path)
    pending = team.get("inflight")
    if (team["status"] != "execution_stopped" or not pending or pending["phase"] != "tool"
            or pending["role"] != "director" or pending["turn"] != team["turn"] + 1):
        raise ValueError("Only a stopped director review-tool checkpoint is supported")
    step = Path(pending["step"]).resolve()
    if step != (experiment.session / f"team-step-{pending['turn']:04d}").resolve() or (step / "result.json").exists():
        raise ValueError("Unexpected or already finished tool step")
    command_record = pilot.read_json(step / "command.json")
    director = Path(command_record["request"]).resolve()
    if not director.is_relative_to(experiment.director_session.resolve()):
        raise ValueError("Director request belongs to another production")
    command = genuine_answer(director, "director")
    if (command != command_record["command"] or command.get("action") != "request_review"
            or command_record["role"] != "director"
            or command_record["answer_sha256"] != pilot.sha256(director / "answer.txt")
            or any(h["turn"] == pending["turn"] for h in team["actors"]["director"]["history"])):
        raise ValueError("Original pending review command changed or already committed")
    kind = "narration" if (experiment.out / "narration-plan.json").exists() else "visual"
    cycle = experiment.review_session / f"cycle-{team['cycle']:02d}-{kind}"
    if (cycle / "report.json").exists():
        raise ValueError("Review already has a report; do not repeat a received verdict")
    evidence = pilot.read_json(cycle / "evidence.json")
    video, _ = experiment.latest_video(pilot.read_json(experiment.state_path))
    if (evidence != pilot.read_json(experiment.out / "review-input.json")
            or evidence["hashes"] != experiment.hashes() or evidence["video_sha256"] != pilot.sha256(video)):
        raise ValueError("Current media no longer matches the original review")
    label = f"cycle-{team['cycle']:02d}-{kind}-whole"
    failed = experiment.role_requests("reviewer")[-1].parent
    record = capacity_failure(failed)
    if record["role"] != "reviewer" or record["stage"] != label + "-detail":
        raise ValueError("Failure is not this cycle's reviewer detail request")
    initial = [p.parent for p in experiment.role_requests("reviewer")
               if pilot.read_json(p)["stage"] == label]
    if len(initial) != 1:
        raise ValueError("Exactly one original first-look request is required")
    initial = initial[0]
    requested = genuine_answer(initial, "reviewer")
    extra = pilot.read_json(initial / "extra-frames.json")
    original = pilot.read_json(initial / "input.json")
    saved = pilot.read_json(failed / "input.json")
    if (requested.get("action") != "inspect_frames" or requested.get("times") != [f["time"] for f in extra]
            or not 1 <= len(extra) <= 6 or not original["text"].endswith("\n" + QUALITY_FORMAT)):
        raise ValueError("Original frame request evidence changed")
    expected = original["text"][:-len("\n" + QUALITY_FORMAT)]
    expected += "\nYour unedited frame request:\n" + json.dumps(requested, ensure_ascii=False)
    expected += "\nAdditional frame timestamps, image order:\n" + json.dumps(requested["times"])
    expected += "\nNow return the final review JSON; no more frame requests for this batch.\n" + QUALITY_FORMAT
    expected_images = original["images"] + [{"path": f["path"], "sha256": f["sha256"]} for f in extra]
    if (saved["text"] != expected or saved["images"] != expected_images
            or saved["system"] != native_system("reviewer") or saved["role"] != "reviewer"
            or saved["model"] != "gpt-6.1-sol" or saved["reasoning_effort"] != "max"
            or experiment.config["model"] != "gpt-6.1-sol"):
        raise ValueError("Detail input differs from the unchanged original request")
    supplied = {f["path"]: f["sha256"] for f in saved["images"]}
    for f in [*evidence["frames"], *[s for t in evidence["temporal_evidence"] for s in t["sheets"]]]:
        if supplied.get(f["path"]) != f["sha256"]:
            raise ValueError("Original evidence is missing from saved reviewer inputs")
    for f in [*saved["images"], *[f for t in evidence["temporal_evidence"] for f in t["frames"]]]:
        if pilot.sha256(Path(f["path"])) != f["sha256"]:
            raise ValueError("Original pixels changed")
    timeline = pilot.read_json(experiment.out / "timeline.json")
    available = {cue: [f["time"] for f in evidence["frames"] if f["cue"] == cue] for cue in evidence["cue_ids"]}
    for cue in timeline["cues"]:
        available[cue["id"]].extend(f["time"] for f in extra if cue["start"] <= f["time"] < cue["start"] + cue["duration"])
    return {"team": team, "step": step, "command": command, "kind": kind, "cycle": cycle,
            "evidence": evidence, "failed": failed, "saved": saved, "available": available}


def finish_review(experiment, pending, raw, request, elapsed):
    """Commit only the genuine reviewer answer to the existing interrupted tool turn."""
    review = decode_object(raw)
    validate_learning_review(review, whole=True)
    validate_review(review, pending["evidence"]["cue_ids"], pending["available"], pending["evidence"]["duration"])
    if genuine_answer(request, "reviewer") != review:
        raise ValueError("Recovered judgment is not the raw received answer")
    experiment.verify()
    if (experiment.hashes() != pending["evidence"]["hashes"]
            or pilot.read_json(experiment.out / "review-input.json") != pending["evidence"]):
        raise ValueError("Media inputs changed during recovery")
    report = {"kind": pending["kind"], "status": review["status"], "hashes": experiment.hashes(),
              "video_sha256": pending["evidence"]["video_sha256"],
              "judgment": {"request": str(request), "answer_sha256": pilot.sha256(request / "answer.txt"), "review": review},
              "evidence_sha256": pilot.sha256(pending["cycle"] / "evidence.json"),
              "narration_sha256": pilot.sha256(experiment.out / "narration-plan.json") if pending["kind"] == "narration" else None,
              "limitations": ["Sampled pixels, not continuous viewing", "No audio/listening or student comprehension test",
                              "Same-model fresh-context review; not different-model agreement"]}
    path = pending["cycle"] / "report.json"
    pilot.write_json(path, report)
    result = {"raw_independent_review": report}
    pilot.write_json(pending["step"] / "result.json", result)
    team = experiment.team = pending["team"]
    turn = team["inflight"]["turn"]
    command = pending["command"]
    team["actors"]["director"]["history"].append({"turn": turn, "notes": command.get("notes"),
        "observations": command.get("observations"), "action": "request_review", "result": result})
    team["tool_durations"].append({"turn": turn, "role": "director", "action": "request_review",
        "seconds": elapsed, "scope": "Recovery only; original interrupted review time remains in request records"})
    team.update(turn=turn, inflight=None, status="running", identical_failures=0, failed_signature=None)
    team[f"{pending['kind']}_review"] = {"path": str(path), "sha256": pilot.sha256(path)}
    team["visual_phase"] = f"{pending['kind']}_{'approved' if review['status'] == 'pass' else 'revision'}"
    experiment.save_team()
    experiment.report()
    return report


def accounting(prior, started, ended, samples):
    before = (datetime.fromisoformat(prior["stopped_at"]) - datetime.fromisoformat(prior["started_at"])).total_seconds()
    resumed = (datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds()
    return {"prior_active_seconds": before, "resumed_active_seconds": resumed,
            "total_active_seconds": before + resumed,
            "excluded_pause_seconds": (datetime.fromisoformat(started) - datetime.fromisoformat(prior["stopped_at"])).total_seconds(),
            "resume_quota_interval": summarize(samples),
            "limitations": ["Active wall time includes model and render waits, not operator downtime",
                            "Original timing-report includes downtime; use this segmented report",
                            "Original quota-report and this resume interval must remain separate",
                            "Unknown failed-request usage remains unknown, never zero"]}


def recover(experiment):
    experiment.initialize()
    bind_adapter(experiment)
    directory = experiment.session / "review-recovery"
    directory.mkdir(exist_ok=True)
    lock = directory / "recovery.lock"
    with lock.open("x") as stream:
        stream.write(str(os.getpid()))
    reader, samples, receipt = None, [], None
    started = now()
    try:
        pending = checkpoint(experiment)
        if (directory / "receipt.json").exists():
            raise ValueError("Recovery already attempted; inspect receipt before another paid request")
        for name in ("team-state.json", "agent-state.json"):
            pilot.write_json(directory / f"before-{name}", pilot.read_json(experiment.session / name))
        for name in ("cost-report.json", "quota-report.json", "timing-report.json"):
            if (experiment.out / name).exists():
                pilot.write_json(directory / f"before-{name}", pilot.read_json(experiment.out / name))
        receipt = {"status": "running", "pid": os.getpid(), "started_at": started,
                   "source": str(Path(__file__).resolve()), "source_sha256": pilot.sha256(Path(__file__)),
                   "failed_request": str(pending["failed"]), "input_sha256": pilot.sha256(pending["failed"] / "input.json"),
                   "hashes": experiment.hashes(), "authorization": "User requested same-model continuation from the review checkpoint",
                   "writer": "technical recovery adapter", "consumers": ["operator", "audit"],
                   "lifecycle": "One explicit recovery attempt; original records retained",
                   "invalidation": "Any bound input, source, evidence or process changes; no automatic replay"}
        pilot.write_json(directory / "receipt.json", receipt)
        try:
            reader = RateReader(directory)
            samples.append(reader.read())
        except Exception as exc:
            samples.append({"captured_at": now(), "error": str(exc)})
        with (experiment.session / "team.lock").open("x") as stream:
            stream.write(str(os.getpid()))
        try:
            experiment.team = pending["team"]
            start = time.monotonic()
            saved = pending["saved"]
            raw, request = experiment.role_request("reviewer", "capacity-recovery-detail", saved["text"],
                                                  [Path(f["path"]) for f in saved["images"]])
            receipt.update(recovered_request=str(request), request_input_sha256=pilot.sha256(request / "input.json"))
            pilot.write_json(directory / "receipt.json", receipt)
            if pilot.read_json(request / "input.json") != saved:
                raise ValueError("Recovery transport changed the original request")
            report = finish_review(experiment, pending, raw, request, time.monotonic() - start)
            receipt.update(recovered_status=report["status"], recovered_turn=experiment.team["turn"])
            pilot.write_json(directory / "receipt.json", receipt)
        finally:
            (experiment.session / "team.lock").unlink()
        experiment.run_team()
        receipt["status"] = pilot.read_json(experiment.team_path)["status"]
    except BaseException as exc:
        if receipt is not None:
            receipt.update(status="stopped", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        if receipt is not None:
            if reader is not None:
                try:
                    samples.append(reader.read())
                except Exception as exc:
                    samples.append({"captured_at": now(), "error": str(exc)})
            ended = now()
            receipt["ended_at"] = ended
            pilot.write_json(directory / "receipt.json", receipt)
            pilot.write_json(directory / "quota-samples.json", samples)
            pilot.write_json(experiment.out / "recovery-accounting.json", accounting(pending["team"], started, ended, samples))
        if reader is not None:
            reader.close()
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    preload_runtime()
    experiment = SolVisualFirst(args.config)
    if args.check_only:
        value = checkpoint(experiment)
        print(json.dumps({"resume_turn": value["team"]["inflight"]["turn"], "failed": str(value["failed"]),
                          "model": "gpt-6.1-sol", "effort": "max"}))
    else:
        recover(experiment)


if __name__ == "__main__":
    main()
