"""One schema-only reviewer repair, isolated from unchanged review-cycle tools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .freeform_review_cycle import ReviewCycleExperiment, validate_review, ROOT, pilot


class ReviewRetryExperiment(ReviewCycleExperiment):
    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__),
                *[ROOT / p for p in self.config.get("prior_failed_cost_reports", [])]]

    def initialize(self):
        super().initialize()
        path = self.context / "review-schema-repair-protocol.json"
        if not path.exists():
            pilot.write_json(path, {
                "writer": "coordinator", "consumers": ["reviewer", "evaluator"],
                "lifecycle": "This new experiment only; never rewrites prior failed run",
                "invalidation": "Tool/config fingerprints change",
                "repair": "At most one schema-only API repair per segment or whole review",
                "input": "Same review request/images, unedited answer, raw validation exception",
                "excluded": "No human semantic edits, hints, rewritten issues or reference results",
                "prior_failed_cost_reports": self.config.get("prior_failed_cost_reports", []),
            })

    def report(self):
        super().report()
        path = self.out / "cost-report.json"
        report = pilot.read_json(path)
        priors = [{"path": p, "sha256": pilot.sha256(ROOT / p),
                   "report": pilot.read_json(ROOT / p)}
                  for p in self.config.get("prior_failed_cost_reports", [])]
        prior_cost = sum(p["report"]["known_peak_uncached_estimate_CNY"] for p in priors)
        report["current_run_peak_uncached_estimate_CNY"] = report["known_peak_uncached_estimate_CNY"]
        report["prior_failed_attempts_peak_uncached_estimate_CNY"] = prior_cost
        report["known_peak_uncached_estimate_CNY"] += prior_cost
        report["unknown_usage_requests"] += sum(p["report"]["unknown_usage_requests"] for p in priors)
        report["prior_failed_attempts"] = priors
        pilot.write_json(path, report)

    def review_batch(self, label, context, ids, frames, images, state):
        before = set(self.review_requests())
        try:
            return super().review_batch(label, context, ids, frames, images, state)
        except (ValueError, KeyError, TypeError) as exc:
            new_requests = sorted(set(self.review_requests()) - before)
            if not new_requests:
                raise
            record_path = new_requests[-1]
            directory = record_path.parent
            answer = directory / "answer.txt"
            record = pilot.read_json(record_path)
            if not answer.is_file() or record["status"] not in {"received", "failed"}:
                raise
            raw = answer.read_text()
            error = {"type": type(exc).__name__, "message": str(exc)}
            pilot.write_json(directory / "schema-error.json", error)
            original = pilot.read_json(directory / "input.json")
            actual_images = [Path(item["path"]) for item in original["images"]]
            if any(pilot.sha256(Path(item["path"])) != item["sha256"] for item in original["images"]):
                raise ValueError("Reviewer image changed before schema repair")
            text = original["text"] + "\nYour unedited response:\n" + raw
            text += "\nRaw output-validation error:\n" + json.dumps(error, ensure_ascii=False)
            text += ("\nReturn corrected final review JSON only. Repair the output structure to match "
                     "the original schema; preserve your own judgments and evidence. "
                     "Do not request more frames. No coordinator content advice is supplied.")
            value, repaired = self.reviewer_request(label + "-schema-repair", text, actual_images)
            timeline = pilot.read_json(self.out / "timeline.json")
            cues = {c["id"]: c for c in timeline["cues"]}
            available = {cue: [f["time"] for f in frames if f["cue"] == cue] for cue in ids}
            image_paths = {str(p) for p in actual_images}
            for index in self.review_session.glob("request-*/extra-frames.json"):
                for frame in pilot.read_json(index):
                    if frame["path"] in image_paths:
                        for cue in ids:
                            c = cues[cue]
                            if c["start"] <= frame["time"] < c["start"] + c["duration"]:
                                available[cue].append(frame["time"])
            validate_review(value, ids, available, timeline["duration"])
            return {"request": str(repaired), "answer_sha256": pilot.sha256(repaired / "answer.txt"),
                    "review": value, "schema_repair_of": str(directory)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    ReviewRetryExperiment(args.config).run_cycles()


if __name__ == "__main__":
    main()
