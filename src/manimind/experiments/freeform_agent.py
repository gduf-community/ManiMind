"""Autonomous API author with bounded, provenance-preserving local tools."""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
from pathlib import Path
import re
import shutil

from .freeform_isolated import Experiment, ROOT, check_source, decode_object
from manimind.postproduce import freeform_pilot as media, pilot
from manimind.render.manim_renderer import extract_keyframes


TOOLS = """
You control your own authoring, execution and visual revision loop.
Return ONE JSON object per turn, no markdown:
{"notes":"your own reasoning and next steps",
 "observations":[{"cue":"id","findings":["what you actually see in supplied images"]}],
 "action":"tool name","args":{...}}
Tools:
write_plan {"plan":{"title":"...", "rationale":"...", "cues":[
 {"id":"safe_id","heading":"...", "spoken":"Chinese narration",
 "subtitle_lines":["..."],"visual":"your visual design",
 "min_duration":number,"lead_in":0.3,"tail":0.65}]}}
  Creates or revises YOUR script, measures TTS, returns actual timing.
write_code {"source":"complete Python GeneratedLesson source"}
replace_code {"edits":[{"old":"exact unique existing text","new":"replacement"}]}
  Applies exact replacements you authored; no automatic semantic fixes.
read_api {"symbols":["Line.put_start_and_end_on", "Scene.play", "Group"]}
  Returns installed ManimGL source/signatures, never other authors' content.
render {}
  Runs the current source in the isolated renderer. Returns real logs,
  success/failure and duration. Does not silently repair code.
inspect_segments {"ids":["cue_id", "another_id"]}
  Up to TWO cues. Returns actual six-frame contact sheets per available cue
  and timing. Your NEXT response should record observations for EACH cue.
inspect_frames {"times":[seconds,...]}
  Up to SIX actual full-resolution frames for closer inspection.
finish {"assessment":"your own conclusion", "remaining_issues":[...]}
  Submits to independent review, NOT self-approval. Requires complete current
  render and your pixel observations for every cue since the last revision.
stop {"reason":"..."} is available if you cannot finish.
You may revise narrative, scene design and code freely. Tools and budget are
fixed. Tool errors are evidence, not editorial suggestions. All failed attempts
are retained. No shell, arbitrary files, network or other experiment access.
You have not heard the audio or watched continuous video: do not claim otherwise.
"""


def apply_edits(source, edits):
    if not isinstance(edits, list) or not edits:
        raise ValueError("edits must be a nonempty list")
    for edit in edits:
        old, new = edit["old"], edit["new"]
        if not isinstance(old, str) or not old or not isinstance(new, str):
            raise ValueError("old/new must be strings, old must be nonempty")
        if source.count(old) != 1:
            raise ValueError("old text must match exactly once; nothing is written")
        source = source.replace(old, new, 1)
    return source


def check_agent_source(source):
    tree = check_source(source)
    forbidden = {
        "os", "sys", "subprocess", "Path", "pathlib", "builtins", "ctypes",
        "read_text", "read_bytes", "write_text", "write_bytes", "fromfile",
        "tofile", "load", "save", "loadtxt", "savetxt", "memmap", "open",
        "unlink", "mkdir", "rmdir", "rename", "replace", "glob", "rglob",
        "environ", "system", "popen", "out", "exec", "eval",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in forbidden:
            raise ValueError(f"IO/runtime capability is unavailable: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            raise ValueError(f"IO/runtime capability is unavailable: {node.attr}")
    return tree


def api_reference(symbols):
    import inspect
    import manimlib
    from .freeform_support import LessonScene
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= 4:
        raise ValueError("Request one to four API symbols")
    results = []
    for name in symbols:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9_]*)?", name):
            raise ValueError("Only public class/function names and one public member")
        parts = name.split(".")
        obj = LessonScene if parts[0] == "LessonScene" else getattr(manimlib, parts[0], None)
        if obj is None or not (inspect.isclass(obj) or inspect.isfunction(obj)):
            results.append({"symbol": name, "error": "No such public class/function"})
            continue
        if len(parts) == 2:
            obj = getattr(obj, parts[1], None)
        if not (inspect.isclass(obj) or inspect.isfunction(obj)):
            results.append({"symbol": name, "error": "No such public class/function"})
            continue
        module = getattr(obj, "__module__", "")
        if not (module.startswith("manimlib.") or module == LessonScene.__module__):
            raise ValueError("Only installed ManimGL and the public helper API")
        try:
            signature = str(inspect.signature(obj))
            source = inspect.getsource(obj)
            results.append({"symbol": name, "signature": signature,
                            "source": source[:18000], "truncated": len(source) > 18000})
        except (OSError, TypeError, ValueError) as exc:
            results.append({"symbol": name, "error": type(exc).__name__})
    return results


class AgentExperiment(Experiment):
    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__)]

    @property
    def state_path(self):
        return self.session / "agent-state.json"

    def initialize(self):
        super().initialize()
        path = self.context / "agent-protocol.json"
        if not path.exists():
            pilot.write_json(path, {
                "scope": "isolated_autonomous_author", "tools": TOOLS,
                "writer": "coordinator", "consumers": ["author", "reviewer"],
                "lifecycle": "Frozen for this experiment; tool changes require a new id",
                "invalidation": "Any tool/config/input fingerprint change",
                "parent_protocol_sha256": pilot.sha256(self.context / "isolation.json"),
                "difference": "Replaces the parent no-tools author with this bounded tool loop",
                "reference_or_previous_candidates_supplied": False,
                "review": "Independent reviewer, never author self-approval",
                "safety": "AST filter and macOS read/write/network sandbox, not adversarial proof",
            })
        if not self.state_path.exists():
            self.save_state({"turn": 0, "renders": 0, "recent": [], "images": [],
                             "pending_cues": [], "observed": [], "status": "running"})

    def save_state(self, state):
        pilot.write_json(self.state_path, state)

    def verify(self):
        super().verify()
        protocol_path = self.context / "agent-protocol.json"
        if protocol_path.exists():
            protocol = pilot.read_json(protocol_path)
            if (protocol["tools"] != TOOLS or protocol["parent_protocol_sha256"]
                    != pilot.sha256(self.context / "isolation.json")):
                raise ValueError("Autonomous tool protocol changed")
        origin_path = self.out / "candidate-origin.json"
        if origin_path.exists():
            origin = pilot.read_json(origin_path)
            if (pilot.sha256(Path(origin["answer"])) != origin["answer_sha256"]
                    or pilot.sha256(Path(origin["extracted_source"])) != origin["source_sha256"]
                    or pilot.sha256(self.out / "candidate.py") != origin["source_sha256"]):
                raise ValueError("Candidate provenance changed")

    def sandbox(self):
        path = super().sandbox()
        extra = ["(deny file-write* (subpath " + json.dumps(str(Path.home())) + "))",
                 "(allow file-write* (subpath " + json.dumps(str(self.out)) + "))",
                 "(allow file-write* (subpath " + json.dumps(str(Path.home() / "Library/Caches")) + "))"]
        path.write_text(path.read_text() + "\n" + "\n".join(extra) + "\n")
        return path

    def report(self):
        super().report()
        path = self.out / "cost-report.json"
        report = pilot.read_json(path)
        report["unknown_usage_requests"] = sum(
            not r["usage"] or any(u.get("prompt_tokens") is None or
                                 u.get("completion_tokens") is None for u in r["usage"])
            for r in report["requests"])
        report["scope"] = "Autonomous isolated author; all attempts included"
        pilot.write_json(path, report)

    def invalidate(self, state):
        state.update(observed=[], pending_cues=[], images=[], latest_render=None)
        for name in ("render.json", "review-input.json"):
            path = self.out / name
            if path.exists():
                shutil.copy2(path, self.current_step / f"before-{name}")
                path.unlink()

    def install_source(self, source, state):
        check_agent_source(source)
        directory = self.current_step / "extracted-code"
        directory.mkdir()
        (directory / "answer.txt").write_text(source)
        self.install_answer(source, directory)
        self.invalidate(state)
        return {"source_sha256": pilot.sha256(self.out / "candidate.py")}

    def latest_video(self, state):
        receipt = state.get("latest_render")
        if not receipt or receipt["input_hashes"] != media.Production(self.spec_path).input_hashes():
            raise ValueError("Render the current source first")
        path = receipt.get("video_path")
        if not path:
            name = Path(receipt["code_path"]).stem
            choices = sorted((self.out / "manim/media/manimgl").glob(f"**/{name}_temp.mp4"))
            if len(choices) != 1:
                raise ValueError("No uniquely identified playable partial render")
            path = str(choices[0])
        video = Path(path)
        stream = next(s for s in pilot.probe(video)["streams"] if s["codec_type"] == "video")
        return video, float(stream["duration"])

    def frame_records(self, video, times, directory):
        result = extract_keyframes(video_path=video, output_dir=directory,
                                   timestamps=times, ffmpeg_executable=pilot.FFMPEG)
        if not result.success or len(result.frame_paths) != len(times):
            raise ValueError("Actual frame extraction failed")
        return [{"time": t, "path": p, "sha256": pilot.sha256(Path(p))}
                for t, p in zip(times, result.frame_paths)]

    def inspect_segments(self, ids, state):
        from PIL import Image, ImageDraw
        if not isinstance(ids, list) or not 1 <= len(ids) <= 2 or len(set(ids)) != len(ids):
            raise ValueError("Select one or two distinct cue ids")
        video, duration = self.latest_video(state)
        cues = {c["id"]: c for c in pilot.read_json(self.out / "timeline.json")["cues"]}
        outputs, images, pending = [], [], []
        for cue_id in ids:
            cue = cues[cue_id]
            end = min(cue["start"] + cue["duration"], duration - 1 / 30)
            if end <= cue["start"]:
                raise ValueError(f"{cue_id} has not rendered")
            times = [round(cue["start"] + (end - cue["start"]) * f, 3)
                     for f in (.03, .20, .40, .60, .80, .98)]
            records = self.frame_records(video, times, self.current_step / cue_id)
            sheet = Image.new("RGB", (1920, 3 * 570), "#202226")
            draw = ImageDraw.Draw(sheet)
            for index, frame in enumerate(records):
                with Image.open(frame["path"]) as image:
                    image.thumbnail((960, 540))
                    x, y = index % 2 * 960, index // 2 * 570
                    sheet.paste(image, (x, y + 28))
                    draw.text((x + 8, y + 5), f"{cue_id}: {frame['time']:.3f}s", fill="white")
            path = self.current_step / f"{cue_id}-sheet.jpg"
            sheet.save(path, quality=95)
            images.append(str(path))
            pending.append(cue_id)
            outputs.append({"cue": cue, "frames": records, "sheet": str(path),
                            "video_sha256": pilot.sha256(video),
                            "complete_cue": end >= cue["start"] + cue["duration"] - .05})
        state.update(images=images, pending_cues=pending)
        return outputs

    def dispatch(self, command, state):
        action, args = command["action"], command.get("args", {})
        if action == "write_plan":
            directory = self.current_step / "extracted-plan"
            directory.mkdir()
            raw = json.dumps(args["plan"], ensure_ascii=False, indent=2)
            (directory / "answer.txt").write_text(raw)
            # Archive any prior model script before revising the plan and TTS.
            for name, folder in (("spec.json", self.out), ("authorship.json", self.context),
                                 ("timeline.json", self.out)):
                path = folder / name
                if path.exists():
                    shutil.copy2(path, self.current_step / f"before-{name}")
            self.invalidate(state)
            self.save_state(state)
            self.install_plan(raw, directory)
            return {"timeline": pilot.read_json(self.out / "timeline.json")}
        if action == "write_code":
            if not self.spec_path.exists():
                raise ValueError("Write your plan and measure narration first")
            return self.install_source(args["source"], state)
        if action == "replace_code":
            source = (self.out / "candidate.py").read_text()
            return self.install_source(apply_edits(source, args["edits"]), state)
        if action == "read_api":
            return api_reference(args["symbols"])
        if action == "render":
            if state["renders"] >= self.config["max_renders"]:
                raise ValueError("Render budget exhausted")
            check_agent_source((self.out / "candidate.py").read_text())
            state["renders"] += 1
            self.invalidate(state)
            self.save_state(state)
            production = media.Production(self.spec_path)
            old_receipts = set(production.session.glob("render-*.json"))
            expected_log = production.session / f"render-{len(old_receipts) + 1:03d}.log"
            error = None
            try:
                self.render("h")
            except Exception as exc:
                error = str(exc)
            receipts = sorted(set(production.session.glob("render-*.json")) - old_receipts)
            receipt = pilot.read_json(receipts[0]) if len(receipts) == 1 else None
            if receipt:
                receipt["tool_success"] = error is None and receipt["success"]
            state["latest_render"] = receipt
            response = {"receipt": receipt, "execution_error": error}
            if receipt:
                response["raw_log_tail"] = Path(receipt["log"]).read_text()[-18000:]
            elif expected_log.exists():
                response["raw_log_tail"] = expected_log.read_text()[-18000:]
            try:
                video, seconds = self.latest_video(state)
                response.update(actual_seconds=seconds, video=str(video))
            except Exception as exc:
                response["media_probe_error"] = str(exc)
            return response
        if action == "inspect_segments":
            return self.inspect_segments(args["ids"], state)
        if action == "inspect_frames":
            video, duration = self.latest_video(state)
            times = args["times"]
            if (not isinstance(times, list) or not 1 <= len(times) <= 6 or
                    any(type(t) not in (int, float) or not math.isfinite(t)
                        or not 0 <= t < duration for t in times)):
                raise ValueError("Select one to six actual in-range timestamps")
            frames = self.frame_records(video, times, self.current_step / "detail")
            state.update(images=[r["path"] for r in frames], pending_cues=[])
            return frames
        if action == "finish":
            receipt = state.get("latest_render")
            cues = {c["id"] for c in pilot.read_json(self.out / "timeline.json")["cues"]}
            if (not receipt or not receipt.get("tool_success") or not receipt["success"]
                    or not (self.out / "review-input.json").exists()):
                raise ValueError("Complete current render and inspection evidence required")
            if cues != set(state["observed"]):
                raise ValueError(f"Current-render observations missing: {sorted(cues - set(state['observed']))}")
            video, _ = self.latest_video(state)
            evidence = pilot.read_json(self.out / "review-input.json")
            if evidence["hashes"] != media.Production(self.spec_path).hashes(video):
                raise ValueError("Current review evidence is stale")
            state["status"] = "submitted_for_independent_review"
            return {"author_assessment": args, "release_allowed": False}
        if action == "stop":
            state["status"] = "author_stopped"
            return args
        raise ValueError("Unknown tool")

    def context_text(self, state):
        context = json.dumps(self.config["brief"], ensure_ascii=False) + "\n" + TOOLS
        if self.spec_path.exists():
            context += "\n" + self.author_context()
        if (self.out / "candidate.py").exists():
            context += "\nYOUR CURRENT SOURCE:\n" + (self.out / "candidate.py").read_text()
        context += "\nYOUR RECENT ACTIONS/NOTES/RAW TOOL RESULTS:\n" + json.dumps(state["recent"], ensure_ascii=False)
        context += "\nSTATE:\n" + json.dumps({
            "turns_used": len(self.requests()), "max_turns": self.config["max_requests"],
            "renders_used": state["renders"], "max_renders": self.config["max_renders"],
            "current_render_observed_cues": state["observed"],
            "images_to_review_now": state["pending_cues"],
            "latest_render_success": bool(state.get("latest_render", {}).get("success"))
                if state.get("latest_render") else False,
        }, ensure_ascii=False)
        return context

    def run(self):
        self.initialize()
        lock = self.session / "agent.lock"
        with lock.open("x") as stream:
            stream.write(str(os.getpid()))
        try:
            state = pilot.read_json(self.state_path)
            if len(self.requests()) != state["turn"]:
                raise ValueError("Unresolved prior request; do not duplicate automatically")
            while state["status"] == "running" and state["turn"] < self.config["max_requests"]:
                self.verify()
                text = self.context_text(state)
                cost = pilot.read_json(self.out / "cost-report.json") if self.requests() else {}
                # UTF-8 bytes plus a deliberately generous image allowance reserve
                # one request before sending. This is an estimate, not a bill cap.
                reserve = ((len(text.encode()) + 40000 * len(state["images"])) * 2
                           + self.config["max_output_tokens"] * 8) / 1e6
                if cost.get("unknown_usage_requests", 0):
                    state["status"] = "unknown_cost_stopped"
                    break
                if cost.get("known_peak_uncached_estimate_CNY", 0) + reserve > self.config["max_cost_CNY"]:
                    state["status"] = "budget_stopped"
                    break
                turn = state["turn"] + 1
                print(f"AGENT turn={turn} renders={state['renders']} observed={state['observed']}", flush=True)
                self.current_step = self.session / f"step-{turn:03d}"
                self.current_step.mkdir()
                command = None
                previous_images = list(state["images"])
                try:
                    raw, directory = self.request(f"agent_{turn:03d}", text, [Path(p) for p in previous_images])
                    command = decode_object(raw)
                    observed = {o["cue"] for o in command.get("observations", [])
                                if isinstance(o, dict) and isinstance(o.get("findings"), list)
                                and o["findings"] and o.get("cue") in state["pending_cues"]}
                    state["observed"] = sorted(set(state["observed"]) | observed)
                    state.update(images=[], pending_cues=[])
                    pilot.write_json(self.current_step / "command.json", {
                        "request": str(directory), "answer_sha256": pilot.sha256(directory / "answer.txt"),
                        "command": command})
                    print(f"AGENT tool={command['action']}", flush=True)
                    result = self.dispatch(command, state)
                except Exception as exc:
                    result = {"error_type": type(exc).__name__, "raw_error": str(exc)}
                pilot.write_json(self.current_step / "result.json", result)
                recent = {"turn": turn, "notes": command.get("notes") if command else None,
                          "observations": command.get("observations") if command else None,
                          "action": command.get("action") if command else None, "result": result}
                state["recent"] = (state["recent"] + [recent])[-8:]
                state["turn"] = turn
                self.save_state(state)
                self.report()
                print(f"AGENT completed_turn={turn} status={state['status']}", flush=True)
            if state["status"] == "running":
                state["status"] = "turn_budget_stopped"
            self.save_state(state)
            print(json.dumps({"status": state["status"], "turns": state["turn"],
                              "renders": state["renders"]}), flush=True)
        finally:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    AgentExperiment(args.config).run()


if __name__ == "__main__":
    main()
