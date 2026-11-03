"""Sol workflow with a pixel-review boundary that excludes subtitle prose."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .freeform_team import TeamExperiment
from .learning_runtime import preload_runtime, bind_adapter
from .learning_workflow import prepare_case, freeze_holdout
from .sol_learning_workflow import SolLearningWorkflow, capture_baseline
from manimind.postproduce import pilot


def subtitle_diagnostics(audit, ids):
    allowed = {"cue", "time", "problem", "characters"}
    return {
        "scope": "Mechanical diagnostics only; no subtitle prose, narration spans or future-cue findings",
        "timeline_sha256": audit.get("timeline_sha256"),
        **{kind: [{k: v for k, v in row.items() if k in allowed}
                  for row in audit[kind] if row.get("cue") in ids]
           for kind in ("blockers", "advisories")},
    }


class SolLearningV2(SolLearningWorkflow):
    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__)]

    def protocol(self):
        if self.profile.get("review_input_boundary") != "pixel-first-no-subtitle-prose-v2":
            raise ValueError("This entry point requires the no-subtitle-prose review profile")
        return {**super().protocol(),
                "cold_review_diagnostics": "Only cue-scoped mechanical warnings; never subtitle rows, prose or future-cue findings",
                "input_verification": "Regression tests inspect the final outgoing reviewer text, not only the cold context helper"}

    def review_batch(self, label, context, ids, frames, images, state):
        evidence = pilot.read_json(self.out / "review-input.json")
        temporal = [t for t in evidence["temporal_evidence"] if t["cue"] in ids]
        attachments = list(images) + [Path(s["path"]) for t in temporal for s in t["sheets"]]
        context += "\nActual temporal sheets at 0.5s intervals; labels give video seconds:\n"
        context += json.dumps([{**t, "frames": [{"time": f["time"]} for f in t["frames"]]}
                               for t in temporal], ensure_ascii=False)
        context += "\nMechanical subtitle diagnostic summary (no prose):\n"
        context += json.dumps(subtitle_diagnostics(evidence["subtitle_audit"], ids), ensure_ascii=False)
        # Bypass v1's evidence assembler, not the independent-review validator or transport.
        return TeamExperiment.review_batch(self, label, context, ids, frames, attachments, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--case")
    parser.add_argument("--initialize-only", action="store_true")
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
    experiment = SolLearningV2(path)
    experiment.initialize()
    bind_adapter(experiment)
    if args.initialize_only:
        return
    capture_baseline(experiment)
    with (experiment.session / "quota-observer.log").open("a") as log:
        observer = subprocess.Popen([sys.executable, "-m", "manimind.experiments.subscription_quota",
            "--project", experiment.id], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    try:
        experiment.run_team(resume_received=args.resume_received_request)
    finally:
        try:
            observer.wait(timeout=40)
        except subprocess.TimeoutExpired:
            observer.terminate()
            observer.wait(timeout=10)


if __name__ == "__main__":
    main()
