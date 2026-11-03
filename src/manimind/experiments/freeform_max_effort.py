"""Fresh-context, maximum-effort author/reviewer experiment without spend caps.

Reuses the existing isolated tools and review validation. It never adopts a
previous candidate, changes its content, or grants itself publishing approval.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from . import freeform_review_cycle as review_module
from . import freeform_review_retry as retry_module
from .freeform_agent import AgentExperiment, check_agent_source
from .freeform_isolated import ROOT, SYSTEM, decode_object
from .freeform_review_retry import ReviewRetryExperiment
from manimind.postproduce import freeform_pilot as media, pilot


UNMETERED_GUIDANCE = """
This is a NEW, from-scratch production. No previous candidate is supplied.
There is NO monetary, request-count, render-count or review-cycle ceiling.
Null maxima mean unlimited, not zero. Do not stop because of an assumed budget.
The model is configured for enabled thinking at maximum reasoning effort.
Use your own judgment to plan, implement, render, inspect and revise this lesson.
Preserve an honest distinction between what you observed and what you inferred.
An independent same-model reviewer will examine your submitted media in a fresh
context. Its original feedback will be returned without coordinator editing.
You can change your own script as well as code. The runtime will remeasure TTS.
The existing isolation, evidence freshness and final publishing gates still apply.
"""


class ProviderStopped(RuntimeError):
    """Stop on transport/protocol failure rather than silently rebilling."""


class MaxEffortExperiment(ReviewRetryExperiment):
    def frozen_paths(self):
        return [*AgentExperiment.frozen_paths(self), Path(review_module.__file__),
                Path(retry_module.__file__), Path(__file__)]

    def validate_config(self):
        if self.config.get("seed_config") or self.config.get("prior_failed_cost_reports"):
            raise ValueError("Fresh experiment cannot adopt previous candidates or reviews")
        if self.config["thinking"] != {"type": "enabled"} or self.config["reasoning_effort"] != "max":
            raise ValueError("Author and reviewer must both use maximum thinking")
        for key in ("max_requests", "max_renders", "max_review_cycles", "max_cost_CNY"):
            if self.config[key] is not None:
                raise ValueError(f"This experiment has no {key} ceiling")

    def initialize(self):
        self.validate_config()
        path = self.context / "max-effort-protocol.json"
        if path.exists():
            self.verify()
            return
        if self.requests() or self.spec_path.exists() or (self.out / "candidate.py").exists():
            raise ValueError("A fresh project id and empty author context are required")
        AgentExperiment.initialize(self)
        self.review_session.mkdir(parents=True, exist_ok=True)
        pilot.write_json(path, {
            "writer": "coordinator", "consumers": ["author", "reviewer", "evaluator"],
            "lifecycle": "Frozen before first request; a changed contract requires a new id",
            "invalidation": "Configuration, implementation or request-contract change",
            "guidance": UNMETERED_GUIDANCE,
            "review_system": review_module.REVIEW_SYSTEM,
            "review_format": review_module.REVIEW_FORMAT,
            "fresh_context": True, "seed": None,
            "author_inputs": "Public brief, generic runtime, own outputs, raw tool results and own-run reviewer feedback",
            "reviewer_inputs": "Public brief, current source, narration timeline and actual current frames only",
            "excluded": "Old candidates, reference videos, old reviews, chat, memory and coordinator editorial advice",
            "caps": {"cost": None, "author_calls": None, "renders": None, "review_cycles": None},
            "safety_stop": "Provider failure, user interruption, provenance failure, or repeated identical failed tool action without content change",
            "release": "Separate independent final media approval required; this runner cannot publish",
        })
        pilot.write_json(self.cycle_path, {"phase": "author", "cycle": 0, "feedback": None})
        self.report()

    def verify(self):
        AgentExperiment.verify(self)
        path = self.context / "max-effort-protocol.json"
        if path.exists():
            value = pilot.read_json(path)
            if (value["guidance"] != UNMETERED_GUIDANCE
                    or value["review_system"] != review_module.REVIEW_SYSTEM
                    or value["review_format"] != review_module.REVIEW_FORMAT):
                raise ValueError("Maximum-effort protocol changed")

    def report(self):
        author = [pilot.read_json(p) for p in self.requests()]
        reviewers = [pilot.read_json(p) for p in self.review_requests()]
        rates = self.config["pricing"]
        groups = {}
        for role, records in (("author", author), ("reviewer", reviewers)):
            usage = [u for r in records for u in r.get("usage", [])]
            incoming = sum(u.get("prompt_tokens") or 0 for u in usage)
            outgoing = sum(u.get("completion_tokens") or 0 for u in usage)
            cached = sum(u.get("cached_tokens") or 0 for u in usage)
            high = (incoming * rates["input_per_million_peak_uncached"]
                    + outgoing * rates["output_per_million_peak"]) / 1e6
            low = ((incoming - cached) * rates["input_per_million_offpeak_uncached"]
                   + cached * rates["input_per_million_offpeak_cached"]
                   + outgoing * rates["output_per_million_offpeak"]) / 1e6
            groups[role] = {"calls": len(records), "prompt_tokens": incoming,
                            "completion_tokens": outgoing, "cached_tokens": cached,
                            "offpeak_cached_estimate_CNY": low,
                            "peak_uncached_estimate_CNY": high,
                            "unknown_usage_requests": sum(not r.get("usage") or any(
                                u.get("prompt_tokens") is None or u.get("completion_tokens") is None
                                for u in r.get("usage", [])) for r in records)}
        pilot.write_json(self.out / "cost-report.json", {
            "scope": "New isolated maximum-effort production; no inherited seed cost",
            "model": self.config["model"], "reasoning_effort": "max", "groups": groups,
            "author_calls": len(author), "reviewer_calls": len(reviewers),
            "known_peak_uncached_estimate_CNY": sum(g["peak_uncached_estimate_CNY"] for g in groups.values()),
            "known_offpeak_cached_estimate_CNY": sum(g["offpeak_cached_estimate_CNY"] for g in groups.values()),
            "unknown_usage_requests": sum(g["unknown_usage_requests"] for g in groups.values()),
            "pricing": rates, "financial_limit": None, "manual_candidate_edits": False,
            "excluded_costs": ["Codex infrastructure and final verification", "TTS", "local rendering"],
            "limitations": ["Usage-derived estimates, not a provider invoice", "Not an equal-budget model benchmark"],
        })

    def stream_request(self, role, stage, text, images):
        from manimind.llm.client import OpenAI
        self.verify()
        key = os.environ.get(self.config["api_key_env"])
        if not key:
            raise ProviderStopped("Configured provider credential is unavailable")
        reviewer = role == "reviewer"
        parent = self.review_session if reviewer else self.session
        records = self.review_requests() if reviewer else self.requests()
        directory = parent / f"request-{len(records) + 1:04d}"
        system = review_module.REVIEW_SYSTEM if reviewer else SYSTEM
        attachments = []
        for raw in images:
            p = Path(raw).resolve()
            if not any(p.is_relative_to(root.resolve()) for root in (self.out, self.session, self.review_session)):
                raise ValueError("Images must belong to this isolated experiment")
            attachments.append({"path": str(p), "sha256": pilot.sha256(p)})
        directory.mkdir()
        params = {"model": self.config["model"], "thinking": self.config["thinking"],
                  "reasoning_effort": "max", "max_tokens": self.config["max_output_tokens"],
                  "top_p": self.config["top_p"], "response_format": {"type": "json_object"}}
        pilot.write_json(directory / "input.json", {
            "system": system, "text": text, "images": attachments, **params,
            "messages_scope": "One system and one user message; no external history",
        })
        record = {"stage": stage, "role": role, "status": "started", "usage": [],
                  "timestamp": datetime.now(timezone.utc).isoformat(),
                  "input_sha256": pilot.sha256(directory / "input.json")}
        pilot.write_json(directory / "record.json", record)
        content = [{"type": "text", "text": text}, *[
            {"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," + base64.b64encode(Path(a["path"]).read_bytes()).decode(),
                "detail": "original"}} for a in attachments]]
        start = time.monotonic()
        progress_at, answer_chars, thinking_chars = start, 0, 0
        finish_reason, response_model = None, None
        print(f"API {role} {stage} thinking=max images={len(images)}", flush=True)
        try:
            with OpenAI(api_key=key, base_url=self.config["base_url"], max_retries=0,
                        timeout=self.config["timeout_seconds"]) as client:
                with client.chat.completions.create(
                    model=params["model"], messages=[{"role": "system", "content": system},
                                                    {"role": "user", "content": content}],
                    stream=True, stream_options={"include_usage": True},
                    max_tokens=params["max_tokens"], reasoning_effort="max", top_p=params["top_p"],
                    response_format=params["response_format"], extra_body={"thinking": params["thinking"]},
                ) as stream, (directory / "answer.txt").open("w", encoding="utf-8") as answer:
                    for chunk in stream:
                        response_model = chunk.model or response_model
                        for choice in chunk.choices:
                            delta = choice.delta
                            fragment = delta.content or ""
                            answer.write(fragment)
                            answer.flush()
                            answer_chars += len(fragment)
                            thinking_chars += len(getattr(delta, "reasoning_content", None) or "")
                            finish_reason = choice.finish_reason or finish_reason
                        if chunk.usage is not None:
                            u = chunk.usage.model_dump()
                            record["usage"] = [{
                                "prompt_tokens": u.get("prompt_tokens"),
                                "completion_tokens": u.get("completion_tokens"),
                                "cached_tokens": u.get("prompt_cache_hit_tokens") or
                                    (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                                "raw_usage": u, "requested_model": params["model"],
                                "response_model": response_model,
                            }]
                        if time.monotonic() - progress_at >= 15:
                            pilot.write_json(directory / "progress.json", {
                                "elapsed_seconds": time.monotonic() - start,
                                "thinking_chars": thinking_chars, "answer_chars": answer_chars,
                            })
                            progress_at = time.monotonic()
            record.update(finish_reason=finish_reason, response_model=response_model,
                          thinking_chars=thinking_chars, answer_chars=answer_chars)
            if finish_reason != "stop" or not answer_chars or not record["usage"]:
                raise ProviderStopped("Incomplete response or missing provider usage; original answer retained")
            record.update(status="received", answer_sha256=pilot.sha256(directory / "answer.txt"))
            return (directory / "answer.txt").read_text(), directory
        except Exception as exc:
            record.update(status="failed", error_type=type(exc).__name__,
                          http_status=getattr(exc, "status_code", None))
            raise ProviderStopped(f"{type(exc).__name__}; inspect request record, no silent retry") from exc
        finally:
            record["elapsed_seconds"] = time.monotonic() - start
            pilot.write_json(directory / "record.json", record)
            self.report()

    def request(self, stage, text, images=()):
        return self.stream_request("author", stage, text, images)

    def reviewer_request(self, stage, text, images):
        raw, directory = self.stream_request("reviewer", stage, text, images)
        return decode_object(raw), directory

    def context_text(self, state):
        text = AgentExperiment.context_text(self, state) + "\n" + UNMETERED_GUIDANCE
        cycle = pilot.read_json(self.cycle_path)
        if cycle.get("feedback"):
            path = Path(cycle["feedback"])
            if pilot.sha256(path) != cycle["feedback_sha256"]:
                raise ValueError("Independent feedback changed")
            text += "\nRAW INDEPENDENT REVIEW OF YOUR CURRENT PROJECT:\n" + path.read_text()
        return text

    def dispatch(self, command, state):
        if command["action"] != "render":
            return AgentExperiment.dispatch(self, command, state)
        check_agent_source((self.out / "candidate.py").read_text())
        state["renders"] += 1
        self.invalidate(state)
        self.save_state(state)
        production = media.Production(self.spec_path)
        before = set(production.session.glob("render-*.json"))
        error = None
        try:
            self.render("h")
        except Exception as exc:
            error = str(exc)
        receipts = sorted(set(production.session.glob("render-*.json")) - before)
        receipt = pilot.read_json(receipts[0]) if len(receipts) == 1 else None
        if receipt:
            receipt["tool_success"] = error is None and receipt["success"]
        state["latest_render"] = receipt
        result = {"receipt": receipt, "execution_error": error}
        if receipt:
            result["raw_log_tail"] = Path(receipt["log"]).read_text()[-18000:]
        try:
            video, seconds = self.latest_video(state)
            result.update(actual_seconds=seconds, video=str(video))
        except Exception as exc:
            result["media_probe_error"] = str(exc)
        return result

    def run_author(self):
        state = pilot.read_json(self.state_path)
        if len(self.requests()) != state["turn"]:
            raise ValueError("Unresolved request; recovery must not duplicate provider calls")
        while state["status"] == "running":
            self.verify()
            turn = state["turn"] + 1
            self.current_step = self.session / f"step-{turn:04d}"
            self.current_step.mkdir()
            text = self.context_text(state)
            command, stop_error = None, None
            print(f"AUTHOR turn={turn} renders={state['renders']} observed={state['observed']}", flush=True)
            try:
                raw, directory = self.request(f"agent_{turn:04d}", text, [Path(p) for p in state["images"]])
                command = decode_object(raw)
                observations = {o["cue"] for o in command.get("observations", [])
                                if isinstance(o, dict) and isinstance(o.get("findings"), list)
                                and o["findings"] and o.get("cue") in state["pending_cues"]}
                state["observed"] = sorted(set(state["observed"]) | observations)
                state.update(images=[], pending_cues=[])
                pilot.write_json(self.current_step / "command.json", {
                    "request": str(directory), "answer_sha256": pilot.sha256(directory / "answer.txt"),
                    "command": command})
                print(f"AUTHOR action={command['action']}", flush=True)
                result = self.dispatch(command, state)
            except ProviderStopped as exc:
                result = {"error_type": type(exc).__name__, "raw_error": str(exc)}
                state["status"] = "provider_stopped"
                stop_error = exc
            except Exception as exc:
                result = {"error_type": type(exc).__name__, "raw_error": str(exc)}
            pilot.write_json(self.current_step / "result.json", result)
            recent = {"turn": turn, "notes": command.get("notes") if command else None,
                      "observations": command.get("observations") if command else None,
                      "action": command.get("action") if command else None, "result": result}
            state["recent"].append(recent)
            state["turn"] = len(self.requests())
            # A repeated identical failed action with unchanged content is a
            # mechanical runaway, not a monetary or quality-revision budget.
            if "error_type" in result:
                source = self.out / "candidate.py"
                signature = json.dumps({"command": command, "error": result,
                                        "source": pilot.sha256(source) if source.exists() else None,
                                        "spec": pilot.sha256(self.spec_path) if self.spec_path.exists() else None},
                                       sort_keys=True, ensure_ascii=False)
                same = signature == state.get("last_failed_action")
                state["identical_failures"] = state.get("identical_failures", 0) + 1 if same else 1
                state["last_failed_action"] = signature
                if state["identical_failures"] >= 3:
                    state["status"] = "repeated_identical_failure"
            else:
                state.update(identical_failures=0, last_failed_action=None)
            self.save_state(state)
            self.report()
            if stop_error:
                raise stop_error
        return state

    def run_cycles(self):
        self.initialize()
        lock = self.session / "max-effort.lock"
        with lock.open("x") as stream:
            stream.write(str(os.getpid()))
        try:
            cycle = pilot.read_json(self.cycle_path)
            if cycle["phase"] == "reviewing":
                raise ValueError("Interrupted independent review requires explicit recovery")
            while cycle["phase"] in {"author", "review"}:
                if cycle["phase"] == "author":
                    state = self.run_author()
                    if state["status"] != "submitted_for_independent_review":
                        cycle.update(phase="author_stopped", author_status=state["status"])
                        break
                cycle["cycle"] += 1
                cycle["phase"] = "reviewing"
                pilot.write_json(self.cycle_path, cycle)
                path, verdict = self.independent_review(cycle["cycle"])
                cycle.update(feedback=str(path), feedback_sha256=pilot.sha256(path))
                print(f"INDEPENDENT REVIEW cycle={cycle['cycle']} status={verdict['status']}", flush=True)
                if verdict["status"] == "pass":
                    cycle["phase"] = "awaiting_external_review"
                else:
                    cycle["phase"] = "author"
                    state = pilot.read_json(self.state_path)
                    state["status"] = "running"
                    self.save_state(state)
                pilot.write_json(self.cycle_path, cycle)
            pilot.write_json(self.cycle_path, cycle)
            self.report()
            pilot.write_json(self.out / "review-cycle-report.json", {
                **cycle, "author_state": pilot.read_json(self.state_path),
                "cost": pilot.read_json(self.out / "cost-report.json"),
                "manual_candidate_edits": False, "release_allowed": False})
        finally:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    MaxEffortExperiment(args.config).run_cycles()


if __name__ == "__main__":
    main()
