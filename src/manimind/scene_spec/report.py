"""Rebuild bounded experiment metrics from preserved requests and approved artifacts."""

import argparse
from pathlib import Path

from . import experiment as ex


def build(suite, collaboration):
    out, context, session = ex.paths(suite)
    frozen = ex.pilot.read_json(context / "suite.json")
    ledger = ex.pilot.read_json(session / "requests.json")
    entries = ledger["requests"]
    for entry in entries:
        ex.verify_request(entry, suite)
    _, case_context, case_session = ex.bench.paths(collaboration)
    case = ex.pilot.read_json(case_context / "collaboration.json")
    dialogue = ex.pilot.read_json(case_session / "dialogue.json")
    if case["profile"] != frozen["profile"] or case["purpose"]["suite"] != suite:
        raise ValueError("Collaboration does not belong to this suite/profile")
    source_paths = [context / "suite.json", session / "requests.json", case_context / "collaboration.json", case_session / "dialogue.json"]
    for turn in dialogue["turns"]:
        if turn["case_sha256"] != ex.pilot.sha256(case_context / "collaboration.json"):
            raise ValueError("Changed collaboration case")
        for kind in ["prompt", "reply"]:
            if turn.get(kind + "_sha256") and ex.pilot.sha256(Path(turn[kind + "_path"])) != turn[kind + "_sha256"]:
                raise ValueError("Changed collaboration evidence")
    rows = []
    for run in frozen["settings"]["runs"]:
        run_id = run["id"]
        attempts = [entry for entry in entries if entry["run_id"] == run_id]
        row = {"run_id": run_id, "task": run["task"], "requests": len(attempts),
               "first_schema_valid": bool(attempts and attempts[0]["status"] == "validated"),
               "first_render_pass": False, "first_geometry_pass": False,
               "current_geometry_pass": False, "review_approved": False, "delivery_verified": False}
        first = out / run_id / "render-01"
        if (first / "render.json").exists():
            row["first_render_pass"] = ex.pilot.read_json(first / "render.json")["success"]
            if row["first_render_pass"]:
                try:
                    ex.check_audit(first)
                    row["first_geometry_pass"] = True
                except ValueError as exc:
                    row["first_geometry_error"] = str(exc)
        try:
            run_out, review_context, directory, rendered = ex.render_directory(suite, run_id)
            row["current_attempt"] = attempts[-1]["attempt"]
            row["audit"] = ex.check_audit(directory)
            row["current_geometry_pass"] = True
            row["render_seconds"] = rendered["render_seconds"]
            row["duration"] = ex.pilot.read_json(directory / "timeline.json")["duration"]
            row["hashes"] = ex.hashes(suite, run_id)
            review_path = review_context / "review.json"
            if review_path.exists():
                source_paths.append(review_path)
                review = ex.pilot.read_json(review_path)
                row["review_status"] = review.get("status")
                row["blockers"] = review.get("blockers")
                evidence = ex.pilot.read_json(run_out / "review-input.json")
                ex.pilot.validate_review(review, row["hashes"], evidence["frames"], require_zoom=False)
                row["review_approved"] = True
                delivery_path = run_out / "delivery.json"
                if delivery_path.exists():
                    source_paths.append(delivery_path)
                    delivery = ex.pilot.read_json(delivery_path)
                    if delivery["sha256"] != ex.pilot.sha256(Path(delivery["video"])) or delivery["review_sha256"] != ex.pilot.sha256(review_path):
                        raise ValueError("Delivery or its review changed")
                    row.update(delivery_verified=True, video=delivery["video"])
        except (ValueError, FileNotFoundError) as exc:
            row["current_gate_error"] = str(exc)
        row["first_attempt_approved"] = row["review_approved"] and row.get("current_attempt") == 1
        rows.append(row)
    calls = ex.bench.attempt_records(entries) + ex.bench.attempt_records(dialogue["turns"])
    cost = ex.bench.cost_summary(calls, frozen["profile"].get("pricing"))
    same_task = {}
    for run in frozen["settings"]["runs"]:
        first = next((entry for entry in entries if entry["run_id"] == run["id"] and entry["attempt"] == 1), None)
        if first:
            same_task.setdefault(run["task"], []).append(first["prompt_sha256"])
    return {
        "scope": "derived_output", "writer_role": "experiment_reporter", "consumer_roles": ["lead", "reviewer"],
        "lifecycle": "Rebuildable snapshot of this bounded suite",
        "invalidation_rule": "Any referenced request, review, component, or delivery change requires rebuilding",
        "suite": suite, "collaboration": collaboration, "task_scope": frozen["settings"]["scope"],
        "runs": rows, "total_trials": len(rows),
        "counts": {key: sum(row[key] for row in rows) for key in ["first_schema_valid", "first_render_pass", "first_geometry_pass",
                                                                 "first_attempt_approved", "current_geometry_pass", "review_approved", "delivery_verified"]},
        "generation_requests": len(entries), "dialogue_requests": len(dialogue["turns"]),
        "dialogue_completed": sum(turn["status"] == "completed" for turn in dialogue["turns"]),
        "same_task_prompts_identical": {key: len(set(hashes)) == 1 for key, hashes in same_task.items() if len(hashes) > 1},
        "cost": cost, "sources": {str(path): ex.pilot.sha256(path) for path in source_paths},
        "limitations": ["Five same-archetype short scenes cannot establish population stability or teaching effectiveness",
                        "Model authors constrained data; engineers author renderer, mathematics, narration rules and review orchestration",
                        "First-attempt approval excludes repaired runs; final approval is not first-pass success",
                        "Actual gateway price and upstream model identity are unverified; reviewer/render/TTS/human costs are excluded",
                        "Review identity is a local declaration, not authenticated production approval"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--collaboration", required=True)
    args = parser.parse_args()
    with ex.bench.exclusive_run(args.suite):
        report = build(args.suite, args.collaboration)
        target = ex.paths(args.suite)[0] / "report.json"
        ex.pilot.write_json(target, report)
        print(target)


if __name__ == "__main__":
    main()
