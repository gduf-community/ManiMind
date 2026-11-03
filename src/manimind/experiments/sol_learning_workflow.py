"""GPT-6.1 Sol transport for versioned, independently reviewed learning videos."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from .codex_cli_team import CodexTeamExperiment, native_system
from .freeform_team import now
from .learning_runtime import preload_runtime, bind_adapter
from .learning_workflow import LearningWorkflow, prepare_case, freeze_holdout
from .subscription_quota import RateReader
from manimind.postproduce import pilot


class SolLearningWorkflow(LearningWorkflow, CodexTeamExperiment):
    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__),
                Path(__file__).with_name("learning_runtime.py"),
                Path(__file__).with_name("subscription_quota.py")]

    def launch_background(self):
        raise ValueError("Use the sol_learning_workflow entry point, not the legacy team launcher")

    def received_checkpoint(self):
        pending = self.team.get("inflight")
        if not pending or pending["phase"] != "request":
            raise ValueError("Only a received request with no tool started can be recovered")
        role = pending["role"]
        matches = [p for p in self.role_requests(role) if
                   pilot.read_json(p)["stage"] == f"team-{pending['turn']:04d}"]
        if len(matches) != 1:
            raise ValueError("No unique completed response; do not repeat a potentially billed request")
        directory = matches[0].parent
        record = pilot.read_json(matches[0])
        original = pilot.read_json(directory / "input.json")
        images = [{"path": str(Path(p).resolve()), "sha256": pilot.sha256(Path(p))}
                  for p in self.team["actors"][role]["images"]]
        if (record["status"] != "received" or record["role"] != role
                or record["answer_sha256"] != pilot.sha256(directory / "answer.txt")
                or record["input_sha256"] != pilot.sha256(directory / "input.json")
                or original["text"] != self.actor_context(role)
                or original["system"] != native_system(role) or original["images"] != images):
            raise ValueError("Completed response or its context changed; recovery refused")
        return (directory / "answer.txt").read_text(), directory


def capture_baseline(experiment):
    path = experiment.context / "quota-snapshots.json"
    if path.exists():
        return
    reader = RateReader(experiment.session)
    try:
        sample = reader.read()
    finally:
        reader.close()
    pilot.write_json(path, {
        "snapshots": [sample], "captured_at": now(),
        "writer": "read-only quota observer before the first Sol request",
        "consumers": ["quota observer", "user", "cost auditor"],
        "lifecycle": "Initial account snapshot for this isolated production run",
        "invalidation": "Account/window changes prevent interval subtraction; concurrent work prevents sole attribution",
    })


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
    experiment = SolLearningWorkflow(path)
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
