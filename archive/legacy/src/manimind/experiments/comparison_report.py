"""Rebuild comparison measurements without calling models or granting approval."""

import argparse
import json
from pathlib import Path
import statistics

from . import model_comparison as comparison
from . import model_benchmark as bench, model_dialogue as dialogue
from ..scene_spec import experiment
from ..postproduce import pilot


def review_consistency(answer):
    verdict = answer.get("verdict")
    findings = answer.get("findings")
    if verdict not in {"blocked", "acceptable_with_advisories", "insufficient_evidence"} or not isinstance(findings, list):
        return {"valid_shape": False, "pass_with_blockers": False}
    valid = all(isinstance(item, dict) and item.get("severity") in {"blocker", "advisory"} for item in findings)
    contradiction = verdict == "acceptable_with_advisories" and any(
        isinstance(item, dict) and item.get("severity") == "blocker" for item in findings)
    return {"valid_shape": valid, "pass_with_blockers": contradiction}


def call_metrics(calls, pricing):
    result = bench.cost_summary(calls, pricing)
    durations = [c["elapsed_seconds"] for c in calls if c.get("elapsed_seconds") is not None]
    result["request_latency_seconds"] = ({"mean": statistics.mean(durations), "min": min(durations), "max": max(durations)}
                                          if durations else None)
    result["response_models"] = sorted({c["response_model"] for c in calls if c.get("response_model")})
    return result


def verify_sources(evidence):
    if isinstance(evidence, dict):
        items = evidence.items()
    elif isinstance(evidence, list) and all(isinstance(item, dict) and {"path", "sha256"} <= item.keys() for item in evidence):
        items = [(item["path"], item["sha256"]) for item in evidence]
    else:
        raise ValueError("Invalid source hash manifest")
    if not evidence:
        raise ValueError("Empty source hash manifest")
    for path, digest in items:
        if not isinstance(path, str) or not isinstance(digest, str) or pilot.sha256(Path(path)) != digest:
            raise ValueError("Stale independent adjudication")


def build(identifier):
    record = comparison.load(identifier)
    out, context, _ = bench.paths(identifier)
    sources = {}

    def read(path):
        path = Path(path)
        value = pilot.read_json(path)
        sources[str(path)] = pilot.sha256(path)
        return value

    read(context / "comparison.json")
    lock = read(context / "ground-truth-lock.json")
    truth_path = Path(lock["ground_truth_path"])
    if pilot.sha256(truth_path) != lock["sha256"]:
        raise ValueError("Ground truth changed after candidate evaluation")
    read(truth_path)
    settings = record["settings"]
    baseline_id, suite = settings["baseline_suite"], settings["generation_suite"]
    baseline = read(bench.ROOT / "outputs" / baseline_id / "report.json")
    old_entries = read(bench.ROOT / "runtime/sessions" / f"{baseline_id}-generation/requests.json")["requests"]
    new_out, new_context, new_session = experiment.paths(suite)
    frozen = read(new_context / "suite.json")
    entries = read(new_session / "requests.json")["requests"]
    runs = []
    for config_run in frozen["settings"]["runs"]:
        run_id = config_run["id"]
        attempts = [entry for entry in entries if entry["run_id"] == run_id]
        for entry in attempts:
            experiment.verify_request(entry, suite)
        row = {"run_id": run_id, "requests": len(attempts), "schema_valid": bool(attempts and attempts[0]["status"] == "validated"),
               "review_approved": False, "delivery_verified": False}
        old_first = next(entry for entry in old_entries if entry["run_id"] == run_id and entry["attempt"] == 1)
        experiment.verify_request(old_first, baseline_id)
        row["same_first_prompt_as_mimo"] = bool(attempts and attempts[0]["prompt_sha256"] == old_first["prompt_sha256"])
        try:
            run_out, run_context, directory, rendered = experiment.render_directory(suite, run_id)
            row["render_success"] = rendered["success"]
            row["audit"] = experiment.check_audit(directory)
            row["render_seconds"] = rendered["render_seconds"]
            current_hashes = experiment.hashes(suite, run_id)
            old_run = next(item for item in baseline["runs"] if item["run_id"] == run_id)
            row["same_components_audio_timeline_as_mimo"] = all(current_hashes[k] == old_run["hashes"][k]
                for k in [*experiment.COMPONENTS, "audio", "timeline", "config"])
            review_path = run_context / "review.json"
            if review_path.exists():
                review = read(review_path)
                evidence = read(run_out / "review-input.json")
                pilot.validate_review(review, current_hashes, evidence["frames"], require_zoom=False)
                row["review_approved"] = True
                delivery_path = run_out / "delivery.json"
                if delivery_path.exists():
                    delivery = read(delivery_path)
                    if delivery["sha256"] != pilot.sha256(Path(delivery["video"])) or delivery["review_sha256"] != pilot.sha256(review_path):
                        raise ValueError("Changed delivery")
                    row.update(delivery_verified=True, video=delivery["video"])
        except (ValueError, FileNotFoundError) as exc:
            row["gate_error"] = str(exc)
        row["first_attempt_approved"] = row["review_approved"] and len(attempts) == 1
        runs.append(row)
    generation_calls = bench.attempt_records(entries)
    review_results, review_calls, prompt_hashes = {}, {}, {}
    for provider, profile in record["review_profiles"].items():
        rows, calls = [], []
        for case in record["cases"]:
            case_id = f"{identifier}-{provider}-{case['id']}"
            candidate_out, candidate_context, session = bench.paths(case_id)
            if not (session / "dialogue.json").exists():
                rows.append({"case_id": case["id"], "status": "not_attempted"})
                continue
            ledger = read(session / "dialogue.json")
            case_record = read(candidate_context / "collaboration.json")
            if case_record["profile"] != profile:
                raise ValueError("Changed review provider")
            turns = ledger["turns"]
            for turn in turns:
                if turn["case_sha256"] != pilot.sha256(candidate_context / "collaboration.json"):
                    raise ValueError("Changed candidate case")
                for kind in ("prompt", "reply"):
                    if turn.get(kind + "_sha256") and pilot.sha256(Path(turn[kind + "_path"])) != turn[kind + "_sha256"]:
                        raise ValueError("Changed candidate evidence")
                    if turn.get(kind + "_sha256"):
                        sources[turn[kind + "_path"]] = turn[kind + "_sha256"]
            row = {"case_id": case["id"], "status": turns[-1]["status"]}
            if turns[-1]["status"] == "completed":
                answer = read(candidate_out / "dialogue-01.json")
                if answer != dialogue.parse_reply(Path(turns[-1]["reply_path"]).read_text(encoding="utf-8")):
                    raise ValueError("Parsed review differs from original API answer")
                row.update(verdict=answer.get("verdict"), consistency=review_consistency(answer))
            rows.append(row)
            calls.extend(bench.attempt_records(turns))
            prompt_hashes.setdefault(case["id"], []).append(turns[0]["prompt_sha256"])
        review_calls[provider] = calls
        review_results[provider] = {"cases": rows, "cost_and_latency": call_metrics(calls, profile.get("pricing"))}
    adjudication_path = context / "adjudication.json"
    adjudication = read(adjudication_path) if adjudication_path.exists() else None
    if adjudication:
        verify_sources(adjudication["source_hashes"])
    report = {
        "scope": "derived_output", "writer_role": "experiment_reporter", "consumer_roles": ["lead", "reviewer"],
        "lifecycle": "Rebuildable comparison snapshot", "invalidation_rule": "Any bound evidence or adjudication changes require rebuilding",
        "comparison": identifier, "baseline_generation_counts": baseline["counts"], "generation_runs": runs,
        "generation_cost_and_latency": call_metrics(generation_calls, frozen["profile"].get("pricing")),
        "deepseek_generation_and_review_cost": call_metrics(generation_calls + review_calls["deepseek"], frozen["profile"].get("pricing")),
        "review_results": review_results,
        "same_review_prompts": {key: len(value) == len(record["review_profiles"]) and len(set(value)) == 1 for key, value in prompt_hashes.items()},
        "independent_adjudication": adjudication, "sources": sources,
        "limitations": record["limitations"] + ["Non-thinking mode only; no audio evaluation", "Token upper estimates are not bills; human review costs excluded"],
    }
    pilot.write_json(out / "report.json", report)
    return out / "report.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", default="ds-mimo-review-20261018")
    args = parser.parse_args()
    with bench.exclusive_run(args.comparison):
        print(build(args.comparison))


if __name__ == "__main__":
    main()
