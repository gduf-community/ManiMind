"""DeepSeek high transport for the frozen v3 learning and media-review workflow."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
import time

from .freeform_agent import api_reference
from .freeform_max_effort import ProviderStopped
from .freeform_team import ALLOWED, SYSTEMS, TEAM_CONTRACT, now
from .learning_runtime import preload_runtime, bind_adapter
from .learning_workflow import LearningWorkflow, ROOT, prepare_case
from .sol_learning_v2 import SolLearningV2
from .sol_learning_v3 import SolLearningV3
from manimind.postproduce import pilot
from manimind.review import learning_quality


HIGH_CONTRACT = TEAM_CONTRACT.replace("maximum-thinking", "high-thinking")


class DeepSeekLearningV3(LearningWorkflow):
    # These frozen methods contain no Sol transport or zero-argument super calls.
    # Reuse their exact evidence and verdict logic without inheriting the CLI adapter.
    review_batch = SolLearningV2.review_batch
    independent_review = SolLearningV3.independent_review

    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__),
                Path(__file__).with_name("sol_learning_v2.py"),
                Path(__file__).with_name("sol_learning_v3.py"),
                Path(__file__).with_name("learning_runtime.py")]

    def validate_config(self):
        if self.config.get("seed_config") or self.config.get("prior_failed_cost_reports"):
            raise ValueError("Fresh experiment cannot adopt previous candidates or reviews")
        if (self.config.get("model") != "deepseek-flash"
                or self.config.get("transport") != "deepseek_openai_api"
                or self.config.get("base_url") != "https://api.deepseek.com/v1"
                or self.config.get("api_key_env") != "DEEPSEEK_API_KEY"):
            raise ValueError("This adapter requires the official image-capable DeepSeek API")
        if (self.config.get("thinking") != {"type": "enabled"}
                or self.config.get("reasoning_effort") != "high"):
            raise ValueError("All three roles must explicitly use high reasoning")
        for key in ("max_requests", "max_renders", "max_review_cycles", "max_cost_CNY"):
            if self.config[key] is not None:
                raise ValueError(f"No additional {key} ceiling is configured for this experiment")

    def protocol(self):
        if (self.profile.get("version") != "v3"
                or self.profile.get("review_input_boundary") != "pixel-first-no-subtitle-prose-v2"
                or self.profile.get("execution_mode") != "batch-evidence-dual-whole-review-v3"):
            raise ValueError("DeepSeek high requires the current v3 learning workflow")
        return {**super().protocol(), "team_contract": HIGH_CONTRACT,
                "model": self.config["model"], "reasoning_effort": "high",
                "transport": "Official DeepSeek API; one system and one current-role context per request",
                "inspection_transport": "Batch current cue evidence; rendered pixels are not automatic observations",
                "independent_review": "Two fresh whole-film requests: pixel first, then source/timing; both must pass",
                "comparison_limit": "Same public brief and v3 workflow; provider and reasoning level differ from Sol max"}

    def actor_context(self, role):
        marker = "\nROLE-SPECIFIC CONTRACT (overrides solo-author tool permissions):\n"
        return super().actor_context(role).replace(marker + TEAM_CONTRACT, marker + HIGH_CONTRACT, 1)

    def inspect_segments(self, ids, state):
        known = {cue["id"] for cue in pilot.read_json(self.out / "timeline.json")["cues"]}
        if (not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids)
                or len(set(ids)) != len(ids) or not set(ids) <= known):
            raise ValueError("Select distinct current cue ids")
        result, images = [], []
        for offset in range(0, len(ids), 2):
            result.extend(super().inspect_segments(ids[offset:offset + 2], state))
            images.extend(state["images"])
        state.update(images=images, pending_cues=list(ids))
        return result

    def dispatch_role(self, role, command, state):
        action, args = command["action"], command.get("args", {})
        if action not in ALLOWED.get(role, set()):
            raise ValueError(f"Tool {action} is not available to {role}")
        if action == "read_api":
            names = args["symbols"]
            if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
                raise ValueError("Request a nonempty list of public symbols")
            return [row for offset in range(0, len(names), 4)
                    for row in api_reference(names[offset:offset + 4])]
        if action == "inspect_segments":
            result = self.inspect_segments(args["ids"], state)
        else:
            result = super().dispatch_role(role, command, state)
            if action != "render" or not (state.get("latest_render") or {}).get("tool_success"):
                return result
            ids = [cue["id"] for cue in pilot.read_json(self.out / "timeline.json")["cues"]]
            result = {**result, "automatic_inspection": self.inspect_segments(ids, state)}
        self.team["actors"][role].update(images=list(state["images"]), pending_cues=list(state["pending_cues"]))
        return result

    def report(self):
        super().report()
        path = self.out / "cost-report.json"
        report = pilot.read_json(path)
        report.update(reasoning_effort="high", workflow_profile_sha256=pilot.sha256(self.profile_path))
        pilot.write_json(path, report)

    def role_request(self, role, stage, text, images):
        from manimind.llm.client import OpenAI

        self.verify()
        self.validate_config()
        if role not in SYSTEMS:
            raise ValueError("Unknown production role")
        if role == "reviewer":
            text += "\nFROZEN GENERIC WORKFLOW GUIDANCE:\n" + json.dumps(self.profile, ensure_ascii=False)
            text += "\n" + learning_quality.QUALITY_FORMAT + "\nReview stage: " + stage
        key = os.environ.get(self.config["api_key_env"])
        if not key:
            raise ProviderStopped("Configured provider credential is unavailable")
        attachments = []
        roots = [self.out, *[self.role_directory(r) for r in SYSTEMS]]
        for image in images:
            path = Path(image).resolve()
            if not path.is_file() or not any(path.is_relative_to(root.resolve()) for root in roots):
                raise ValueError("Only this experiment's actual media may enter a role request")
            attachments.append({"path": str(path), "sha256": pilot.sha256(path)})
        directory = self.role_directory(role) / f"request-{len(self.role_requests(role)) + 1:04d}"
        directory.mkdir()
        params = {"model": self.config["model"], "reasoning_effort": self.config["reasoning_effort"],
                  "thinking": self.config["thinking"], "top_p": self.config["top_p"],
                  "max_tokens": self.config["max_output_tokens"]}
        pilot.write_json(directory / "input.json", {
            "role": role, "system": SYSTEMS[role], "text": text, "images": attachments, **params,
            "messages_scope": "One role system and one assembled public/own-project context; no external history"})
        record = {"role": role, "stage": stage, "status": "started", "usage": [], "timestamp": now(),
                  "requested_model": params["model"], "reasoning_effort": params["reasoning_effort"],
                  "input_sha256": pilot.sha256(directory / "input.json")}
        pilot.write_json(directory / "record.json", record)
        content = [{"type": "text", "text": text}]
        for item in attachments:
            path = Path(item["path"])
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            content.append({"type": "image_url", "image_url": {
                "url": f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode(), "detail": "original"}})
        started = progress_at = time.monotonic()
        answer_chars = thinking_chars = 0
        finish_reason = response_model = None
        print(f"DEEPSEEK API role={role} stage={stage} thinking=high images={len(images)}", flush=True)
        try:
            with OpenAI(api_key=key, base_url=self.config["base_url"], max_retries=0,
                        timeout=self.config["timeout_seconds"]) as client:
                with client.chat.completions.create(
                    model=params["model"], messages=[{"role": "system", "content": SYSTEMS[role]},
                                                    {"role": "user", "content": content}],
                    stream=True, stream_options={"include_usage": True}, max_tokens=params["max_tokens"],
                    reasoning_effort=params["reasoning_effort"], top_p=params["top_p"],
                    response_format={"type": "json_object"}, extra_body={"thinking": params["thinking"]},
                ) as stream, (directory / "answer.txt").open("w", encoding="utf-8") as answer:
                    for chunk in stream:
                        response_model = chunk.model or response_model
                        for choice in chunk.choices:
                            fragment = choice.delta.content or ""
                            answer.write(fragment)
                            answer.flush()
                            answer_chars += len(fragment)
                            thinking_chars += len(getattr(choice.delta, "reasoning_content", None) or "")
                            finish_reason = choice.finish_reason or finish_reason
                        if chunk.usage is not None:
                            usage = chunk.usage.model_dump()
                            record["usage"] = [{"prompt_tokens": usage.get("prompt_tokens"),
                                "completion_tokens": usage.get("completion_tokens"),
                                "cached_tokens": usage.get("prompt_cache_hit_tokens") or
                                    (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                                "raw_usage": usage, "response_model": response_model}]
                        if time.monotonic() - progress_at >= 15:
                            pilot.write_json(directory / "progress.json", {
                                "elapsed_seconds": time.monotonic() - started,
                                "answer_chars": answer_chars, "thinking_chars": thinking_chars})
                            progress_at = time.monotonic()
            if finish_reason != "stop" or not answer_chars or not record["usage"]:
                raise ProviderStopped("Incomplete response or missing usage; preserve response without execution")
            record.update(status="received", answer_sha256=pilot.sha256(directory / "answer.txt"))
            return (directory / "answer.txt").read_text(), directory
        except BaseException as exc:
            record.update(status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed",
                          error_type=type(exc).__name__, http_status=getattr(exc, "status_code", None))
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise ProviderStopped(f"{type(exc).__name__}; no implicit retry") from exc
        finally:
            record.update(elapsed_seconds=time.monotonic() - started, finished_at=now(),
                          answer_chars=answer_chars, thinking_chars=thinking_chars,
                          finish_reason=finish_reason, response_model=response_model)
            pilot.write_json(directory / "record.json", record)
            pilot.write_json(directory / "progress.json", {
                "status": record["status"], "elapsed_seconds": record["elapsed_seconds"],
                "answer_chars": answer_chars, "thinking_chars": thinking_chars})
            self.report()


def launch(study, profile, case):
    config = prepare_case(study.resolve(), case, profile.resolve())
    experiment = DeepSeekLearningV3(config)
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
            command = [sys.executable, "-m", "manimind.experiments.deepseek_learning_v3",
                       "--study", str(study.resolve()), "--profile", str(profile.resolve()), "--case", case]
            if Path("/usr/bin/caffeinate").is_file():
                command = ["/usr/bin/caffeinate", "-i", *command]
            with (experiment.session / "runner.log").open("a") as log:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, cwd=ROOT, start_new_session=True)
            value = {"pid": process.pid, "started_at": now(), "argv": command,
                     "launcher_source": str(Path(__file__).resolve()), "launcher_sha256": pilot.sha256(Path(__file__)),
                     "config_sha256": pilot.sha256(config), "model": experiment.config["model"],
                     "reasoning_effort": "high", "engine": "deepseek-learning-v3",
                     "writer": "background execution adapter", "consumers": ["operator", "duplicate guard", "auditor"],
                     "lifecycle": "Current runner process; no extra model or candidate context",
                     "invalidation": "Exited process, unresolved checkpoint or frozen-input drift requires inspection"}
            pilot.write_json(receipt, value)
            return value
        finally:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--resume-received-request", action="store_true")
    args = parser.parse_args()
    if args.background and (args.initialize_only or args.resume_received_request):
        parser.error("Background launch cannot implicitly resume or initialize only")
    preload_runtime()
    if args.background:
        print(json.dumps(launch(args.study, args.profile, args.case)))
        return
    config = prepare_case(args.study.resolve(), args.case, args.profile.resolve())
    experiment = DeepSeekLearningV3(config)
    experiment.initialize()
    bind_adapter(experiment)
    if not args.initialize_only:
        experiment.run_team(resume_received=args.resume_received_request)


if __name__ == "__main__":
    main()
