"""Fresh Codex subscription requests through the frozen three-role media tools."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .freeform_team import TeamExperiment, SYSTEMS, TEAM_CONTRACT, now
from .freeform_max_effort import ProviderStopped
from .freeform_isolated import ROOT, decode_object
from manimind.postproduce import freeform_pilot as media, pilot


DISABLED = (
    "shell_tool", "unified_exec", "memories", "apps", "plugins", "multi_agent",
    "hooks", "browser_use", "computer_use", "in_app_browser", "image_generation",
    "view_image", "sleep_tool", "goals", "chronicle", "skill_search",
    "fast_mode", "ultrafast_mode", "unbounded_connection_retries",
)


def native_system(role):
    return SYSTEMS[role].replace("DeepSeek", "GPT-6.1 Sol").replace(
        "没有GPT编辑帮助", "没有外部编辑帮助")


def native_contract():
    return TEAM_CONTRACT.replace("DeepSeek", "GPT-6.1 Sol")


def cli_command(executable, directory, system, images):
    args = [executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
            "--skip-git-repo-check", "--sandbox", "read-only", "--json", "--color", "never",
            "--model", "gpt-6.1-sol", "--config", 'model_reasoning_effort="max"',
            "--config", "project_doc_max_bytes=0", "--config", 'web_search="disabled"',
            "--config", "suppress_unstable_features_warning=true",
            "--config", "developer_instructions=" + json.dumps(system, ensure_ascii=False),
            "--enable", "skip_host_skill_discovery", "--cd", str(directory),
            "--output-last-message", str(directory / "answer.txt")]
    for name in DISABLED:
        args += ["--disable", name]
    for image in images:
        args += ["--image", str(image)]
    return [*args, "-"]


def read_events(path):
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    completed = [e for e in events if e.get("type") == "turn.completed"]
    unexpected = [e for e in events if e.get("type") in {"item.started", "item.completed"}
                  and e.get("item", {}).get("type") not in {"agent_message", "reasoning", "error"}]
    if unexpected:
        raise ValueError("Native tools were used outside the frozen JSON tool protocol")
    if len(completed) != 1 or any(e.get("type") in {"error", "turn.failed"} for e in events):
        raise ValueError("Expected exactly one successful native model turn")
    raw = completed[0].get("usage") or {}
    if raw.get("input_tokens") is None or raw.get("output_tokens") is None:
        raise ValueError("Native usage is missing; preserve records without executing the answer")
    return {"prompt_tokens": raw["input_tokens"], "completion_tokens": raw["output_tokens"],
            "cached_tokens": raw.get("cached_input_tokens", 0),
            "reasoning_tokens_included_in_output": raw.get("reasoning_output_tokens"), "raw_usage": raw}, next(
                (e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)


class CodexTeamExperiment(TeamExperiment):
    def launch_background(self):
        self.initialize()
        with (self.session / "launch.lock").open("x"):
            try:
                previous = self.session / "launcher.json"
                if previous.exists():
                    pid = pilot.read_json(previous)["pid"]
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        pass
                    else:
                        raise ValueError("Existing experiment process is still alive; do not duplicate requests")
                state = pilot.read_json(self.team_path)
                if state.get("inflight") or state["status"] not in {"ready", "running"}:
                    raise ValueError("A clean ready/running checkpoint is required for background launch")
                command = ["/usr/bin/caffeinate", "-i", sys.executable, "-m",
                           "manimind.experiments.codex_cli_team", "--config", str(self.config_path)]
                with (self.session / "runner.log").open("a") as log:
                    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                               stderr=subprocess.STDOUT, cwd=ROOT, start_new_session=True)
                pilot.write_json(previous, {
                    "pid": process.pid, "started_at": now(), "argv": command,
                    "writer": "background launcher", "consumers": ["operator", "duplicate-launch guard"],
                    "lifecycle": "Current runner process", "invalidation": "Process exits; unresolved tool remains blocked"})
                return {"pid": process.pid, "log": str(self.session / "runner.log")}
            finally:
                (self.session / "launch.lock").unlink()

    def frozen_paths(self):
        executable = shutil.which("codex")
        return [*super().frozen_paths(), Path(__file__), *([Path(executable).resolve()] if executable else [])]

    def validate_config(self):
        super().validate_config()
        if self.config["model"] != "gpt-6.1-sol" or self.config["transport"] != "codex_subscription_cli":
            raise ValueError("This isolated adapter requires the requested GPT-6.1 Sol subscription model")

    def protocol(self):
        value = super().protocol()
        value.update(systems={role: native_system(role) for role in SYSTEMS},
                     team_contract=native_contract(),
                     release="Independent GPT-6.1 Sol pixel review, then existing media release gate",
                     transport="Fresh ephemeral Codex CLI requests using existing subscription authentication",
                     disabled_native_capabilities=list(DISABLED),
                     native_project_instructions=False, native_memory=False,
                     model="gpt-6.1-sol", reasoning_effort="max",
                     comparison_limit="Same public task, media tools and role loop; Codex native system wrapper and internal transport handling differ from direct DeepSeek API")
        return value

    def actor_context(self, role):
        original = super().actor_context(role)
        marker = "\nROLE-SPECIFIC CONTRACT (overrides solo-author tool permissions):\n"
        return original.replace(marker + TEAM_CONTRACT, marker + native_contract(), 1)

    def install_plan(self, raw, directory):
        plan = decode_object(raw)
        spec = {**plan, "project_id": self.id, "fps": 30, "voice": "zh-CN-YunxiNeural",
                "speech_rate": "+2%", "audience": self.config["brief"]["audience"],
                "facts": self.config["brief"]["facts"],
                "authoring": "Isolated GPT-6.1 Sol subscription CLI; no external content edits",
                "scene": str((self.out / "candidate.py").relative_to(ROOT)),
                "scene_class": "GeneratedLesson",
                "render_config": str((self.out / "render.yml").relative_to(ROOT)),
                "dependencies": [str(p.relative_to(ROOT)) for p in self.frozen_paths() if p.is_relative_to(ROOT)]}
        media.validate_spec(spec)
        pilot.write_json(self.spec_path, spec)
        pilot.write_json(self.context / "authorship.json", {
            "plan_answer": str(directory / "answer.txt"),
            "plan_answer_sha256": pilot.sha256(directory / "answer.txt"),
            "spec_sha256": pilot.sha256(self.spec_path), "content_keys": list(plan),
            "mechanical_additions": ["paths", "fps", "voice", "facts", "dependencies", "authorship"]})
        asyncio.run(media.Production(self.spec_path).prepare("edge"))

    def role_request(self, role, stage, text, images):
        self.verify()
        executable = shutil.which("codex")
        if not executable:
            raise ProviderStopped("Codex CLI is unavailable")
        attachments = []
        roots = [self.out, *[self.role_directory(r) for r in SYSTEMS]]
        for image in images:
            path = Path(image).resolve()
            if not path.is_file() or not any(path.is_relative_to(root.resolve()) for root in roots):
                raise ValueError("Only current-project media can be supplied")
            attachments.append({"path": str(path), "sha256": pilot.sha256(path)})
        directory = self.role_directory(role) / f"request-{len(self.role_requests(role)) + 1:04d}"
        directory.mkdir()
        system = native_system(role)
        pilot.write_json(directory / "input.json", {
            "role": role, "system": system, "text": text, "images": attachments,
            "model": self.config["model"], "reasoning_effort": "max",
            "transport": "fresh ephemeral Codex CLI, no inherited chat, project instructions or memory"})
        command = cli_command(executable, directory, system, [Path(i["path"]) for i in attachments])
        pilot.write_json(directory / "invocation.json", {"argv": command, "cwd": str(directory)})
        record = {"role": role, "stage": stage, "status": "started", "usage": [], "timestamp": now(),
                  "input_sha256": pilot.sha256(directory / "input.json"), "requested_model": self.config["model"],
                  "model_verification": "Explicit CLI model selection; events may omit resolved server model"}
        pilot.write_json(directory / "record.json", record)
        started = time.monotonic()
        print(f"SOL CLI role={role} stage={stage} thinking=max images={len(images)}", flush=True)
        try:
            with (directory / "events.jsonl").open("w") as stdout, (directory / "stderr.log").open("w") as stderr:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                           text=True, cwd=directory, start_new_session=True)
                pilot.write_json(directory / "progress.json", {"status": "running", "pid": process.pid, "started_at": now()})
                try:
                    process.communicate(text, timeout=self.config["timeout_seconds"])
                except BaseException:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise
            record["returncode"] = process.returncode
            if process.returncode != 0:
                raise ProviderStopped("Native CLI failed; inspect preserved stderr without rebilling")
            usage, thread_id = read_events(directory / "events.jsonl")
            record.update(usage=[usage], native_thread_id=thread_id)
            answer = directory / "answer.txt"
            if not answer.is_file() or not answer.read_text().strip():
                raise ProviderStopped("No complete native final answer")
            record.update(status="received", answer_sha256=pilot.sha256(answer))
            return answer.read_text(), directory
        except BaseException as exc:
            record.update(status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed",
                          error_type=type(exc).__name__)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise ProviderStopped(f"{type(exc).__name__}; no implicit native retry") from exc
        finally:
            record.update(elapsed_seconds=time.monotonic() - started, finished_at=now())
            pilot.write_json(directory / "record.json", record)
            pilot.write_json(directory / "progress.json", {"status": record["status"],
                "elapsed_seconds": record["elapsed_seconds"], "finished_at": record["finished_at"]})
            self.report()

    def release(self):
        result = super().release()
        path = self.context / "review.json"
        review = pilot.read_json(path)
        review.update(reviewer_id=f"sol61-team-independent-cycle-{self.team['cycle']}",
                      writer="mechanical adapter of independent GPT-6.1 Sol verdicts")
        review["limitations"] = ["Supervision is by GPT-6.1 Sol director; no external editorial assistance"
                                 if s.startswith("Supervision is by DeepSeek") else s for s in review["limitations"]]
        pilot.write_json(path, review)
        for name in ("delivery.json", "team-delivery.json"):
            target = self.out / name
            data = pilot.read_json(target)
            data.update(model="gpt-6.1-sol", final_gate_review_sha256=pilot.sha256(path))
            data["limitations"] = review["limitations"]
            if name == "delivery.json":
                data["review_sha256"] = pilot.sha256(path)
            else:
                data["legacy_scope_note"] = "Shared pilot preview gate; all creative roles here are GPT-6.1 Sol"
            pilot.write_json(target, data)
        result["scope"] = "GPT-6.1 Sol-reviewed preview"
        return result

    def report(self):
        groups = {}
        for role in SYSTEMS:
            records = [pilot.read_json(p) for p in self.role_requests(role)]
            usages = [u for r in records for u in r.get("usage", [])]
            groups[role] = {"calls": len(records), "prompt_tokens": sum(u["prompt_tokens"] for u in usages),
                "cached_tokens": sum(u.get("cached_tokens", 0) for u in usages),
                "completion_tokens": sum(u["completion_tokens"] for u in usages),
                "request_elapsed_seconds": sum(r.get("elapsed_seconds", 0) for r in records),
                "unknown_usage_requests": sum(not r.get("usage") for r in records)}
        totals = {key: sum(g[key] for g in groups.values()) for key in next(iter(groups.values()))}
        rate = self.config["pricing"]
        estimate = ((totals["prompt_tokens"] - totals["cached_tokens"]) * rate["input_credits_per_million"]
                    + totals["cached_tokens"] * rate["cached_credits_per_million"]
                    + totals["completion_tokens"] * rate["output_credits_per_million"]) / 1e6
        pilot.write_json(self.out / "cost-report.json", {
            "scope": "Isolated GPT-6.1 Sol director/creator/reviewer via subscription CLI", "groups": groups, **totals,
            "standard_credit_rate_equivalent": estimate, "pricing": rate,
            "limitations": ["Credit-rate equivalent is not an invoice or included-allowance percentage",
                            "Account quota snapshots may include concurrent work or resets",
                            "Native wrapper tokens are included; unknown usage is not zero cost"]})
        if self.team_path.exists():
            state = pilot.read_json(self.team_path)
            start, end = state.get("started_at"), state.get("finished_at") or now()
            pilot.write_json(self.out / "timing-report.json", {
                "model_production_started_at": start, "ended_or_sampled_at": end,
                "production_wall_seconds": (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() if start else None,
                "status": state["status"], "turns": state["turn"], "review_cycles": state["cycle"],
                "tool_durations": state.get("tool_durations", []),
                "role_request_elapsed_seconds": {r: v["request_elapsed_seconds"] for r, v in groups.items()}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--background", action="store_true")
    args = parser.parse_args()
    experiment = CodexTeamExperiment(args.config)
    if args.initialize_only:
        experiment.initialize()
    elif args.background:
        print(json.dumps(experiment.launch_background()))
    else:
        experiment.run_team()


if __name__ == "__main__":
    main()
