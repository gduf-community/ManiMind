"""Read-only subscription accounting alongside an autonomous experiment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

from .freeform_isolated import ROOT
from .freeform_team import now
from manimind.postproduce import pilot


def summarize(rows):
    samples = [r for r in rows if "used_percent" in r]
    changed = any(b["resets_at"] != a["resets_at"] or b["used_percent"] < a["used_percent"]
                  for a, b in zip(samples, samples[1:]))
    return {"sample_count": len(samples), "reset_or_window_change_observed": changed,
            "initial_used_percent": samples[0]["used_percent"] if samples else None,
            "latest_used_percent": samples[-1]["used_percent"] if samples else None,
            "account_interval_percentage_points": samples[-1]["used_percent"] - samples[0]["used_percent"]
                if samples and not changed else None,
            "single_job_attribution": False,
            "limitations": ["Account-wide snapshots include any concurrent Codex usage",
                            "Polling can miss usage around resets; no subtraction across changed windows",
                            "Per-role token records identify this experiment's own model calls"]}


class RateReader:
    def __init__(self, directory):
        self.log = (directory / "quota-server.log").open("a")
        self.process = subprocess.Popen([shutil.which("codex"), "app-server", "--stdio",
            "--disable", "apps", "--disable", "plugins", "--disable", "hooks"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1)
        self.sequence = 0
        self.request("initialize", {"clientInfo": {"name": "manimind_quota_audit", "version": "1.0"}})
        self.send({"method": "initialized", "params": {}})

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method, params=None):
        self.sequence += 1
        ident = self.sequence
        self.send({"method": method, "id": ident, **({"params": params} if params is not None else {})})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.process.stdout], [], [], max(0, deadline - time.monotonic()))
            if not ready:
                break
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("Quota reader exited")
            message = json.loads(line)
            if message.get("id") == ident:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message["result"]
        raise TimeoutError("Account quota read timed out")

    def read(self):
        result = self.request("account/rateLimits/read")
        bucket = (result.get("rateLimitsByLimitId") or {}).get("codex") or result.get("rateLimits") or {}
        primary = bucket.get("primary") or {}
        if primary.get("usedPercent") is None:
            raise ValueError("Account quota is unavailable")
        return {"captured_at": now(), "used_percent": primary["usedPercent"],
                "window_minutes": primary["windowDurationMins"], "resets_at": primary["resetsAt"],
                "source": "Codex account/rateLimits/read", "raw_bucket": bucket}

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.log.close()


def watch(project_id):
    session = ROOT / "runtime/sessions" / f"{project_id}-generation"
    out = ROOT / "outputs" / project_id
    context = ROOT / "runtime/projects" / project_id
    lock = session / "quota-capture.lock"
    with lock.open("x") as stream:
        stream.write(str(os.getpid()))
    reader = None
    baseline = pilot.read_json(context / "quota-snapshots.json")["snapshots"][-1]
    rows = [baseline]
    try:
        reader = RateReader(session)
        failures = 0
        while True:
            state = pilot.read_json(session / "team-state.json")
            try:
                sample = {**reader.read(), "team_status": state["status"], "team_turn": state["turn"]}
                failures = 0
            except Exception as exc:
                failures += 1
                sample = {"captured_at": now(), "error_type": type(exc).__name__, "error": str(exc)}
            rows.append(sample)
            with (session / "quota-samples.jsonl").open("a") as stream:
                stream.write(json.dumps(sample, ensure_ascii=False) + "\n")
            pilot.write_json(out / "quota-report.json", {
                **summarize(rows), "team_status": state["status"], "updated_at": now(),
                "writer": "read-only subscription observer", "consumers": ["user", "cost audit"],
                "lifecycle": "This experiment; stops at terminal team status or reader failure",
                "invalidation": "Changed account/window or missing samples prevents precise interval attribution"})
            if state["status"] not in {"ready", "running"} or failures >= 3:
                break
            time.sleep(30)
    finally:
        if reader is not None:
            reader.close()
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    if args.background:
        session = ROOT / "runtime/sessions" / f"{args.project}-generation"
        if (session / "quota-capture.lock").exists():
            raise ValueError("Quota observer already has a lock")
        with (session / "quota-observer.log").open("a") as log:
            process = subprocess.Popen([sys.executable, "-m", "manimind.experiments.subscription_quota",
                "--project", args.project], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                cwd=ROOT, start_new_session=True)
        print(json.dumps({"quota_observer_pid": process.pid}))
    else:
        watch(args.project)


if __name__ == "__main__":
    main()
