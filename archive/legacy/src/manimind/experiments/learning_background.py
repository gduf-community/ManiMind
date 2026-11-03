"""Duplicate-safe background launcher for frozen Sol workflows."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .freeform_team import now
from .learning_workflow import ROOT, prepare_case
from .sol_learning_v2 import SolLearningV2
from .sol_learning_v3 import SolLearningV3
from manimind.postproduce import pilot


def launch(study, profile, case, engine="sol-v2"):
    engines = {"sol-v2": (SolLearningV2, "sol_learning_v2", "v2"),
               "sol-v3": (SolLearningV3, "sol_learning_v3", "v3")}
    if engine not in engines:
        raise ValueError("Unknown Sol workflow engine")
    experiment_type, module_name, version = engines[engine]
    if pilot.read_json(profile)["version"] != version:
        raise ValueError("Workflow engine and profile version must match")
    config = prepare_case(study.resolve(), case, profile.resolve())
    experiment = experiment_type(config)
    experiment.initialize()
    lock = experiment.session / "launch.lock"
    with lock.open("x"):
        try:
            receipt = experiment.session / "launcher.json"
            if receipt.exists():
                try:
                    os.kill(pilot.read_json(receipt)["pid"], 0)
                except ProcessLookupError:
                    pass
                else:
                    raise ValueError("Existing runner is alive; do not launch duplicate requests")
            state = pilot.read_json(experiment.team_path)
            if ((experiment.session / "team.lock").exists() or state.get("inflight")
                    or state["status"] not in {"ready", "running"}):
                raise ValueError("A clean, unlocked ready/running checkpoint is required")
            command = [sys.executable, "-m", f"manimind.experiments.{module_name}", "--study", str(study.resolve()),
                       "--profile", str(profile.resolve()), "--case", case]
            if Path("/usr/bin/caffeinate").is_file():
                command = ["/usr/bin/caffeinate", "-i", *command]
            with (experiment.session / "runner.log").open("a") as log:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                           cwd=ROOT, start_new_session=True)
            value = {"pid": process.pid, "started_at": now(), "argv": command,
                     "launcher_source": str(Path(__file__).resolve()), "launcher_sha256": pilot.sha256(Path(__file__)),
                     "config_sha256": pilot.sha256(config), "model": "gpt-6.1-sol", "engine": engine,
                     "writer": "background execution adapter", "consumers": ["operator", "duplicate guard", "auditor"],
                     "lifecycle": "This runner process only; no additional model or candidate context",
                     "invalidation": "Exited process, unresolved checkpoint or frozen input drift requires inspection"}
            pilot.write_json(receipt, value)
            return value
        finally:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--engine", choices=("sol-v2", "sol-v3"), default="sol-v2")
    args = parser.parse_args()
    print(json.dumps(launch(args.study, args.profile, args.case, args.engine)))


if __name__ == "__main__":
    main()
