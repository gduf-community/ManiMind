"""Visual-first Sol production: silent review before optional future speech."""

from __future__ import annotations

import argparse
import inspect
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from .codex_cli_team import CodexTeamExperiment, native_system
from .freeform_agent import AgentExperiment, api_reference, apply_edits
from .freeform_isolated import decode_object
from .freeform_team import now
from .learning_runtime import preload_runtime, bind_adapter
from .learning_workflow import LearningWorkflow
from .sol_learning_workflow import SolLearningWorkflow, capture_baseline
from .visual_first_data import check_visual_source, narration_plan, validate_events, visual_timeline
from manimind.postproduce import pilot
from manimind.render.manim_renderer import build_manim_render_command, write_scene_code, _render_environment
from manimind.review.learning_quality import QUALITY_FORMAT, validate_learning_review

ROOT = pilot.ROOT
ALLOWED = {
    "director": {"write_visual_plan", "delegate", "read_api", "inspect_segments", "inspect_frames",
                 "request_review", "write_narration", "finish", "stop"},
    "creator": {"write_code", "replace_code", "render", "read_api", "inspect_segments", "inspect_frames", "handoff", "stop"},
}
CONTRACT = """
This is a NEW visual-first production. No old film, script, review or main chat is supplied.
The first deliverable is a polished SILENT animation, not a TTS-paced slideshow.
Do not write narration until actual visual evidence has passed independent review.
Do not render narration subtitles. Necessary labels, formulas and visual explanations are welcome;
not every abstract idea must be understandable without future spoken explanation.
Keep the physical model clock conceptually separate from the presentation clock.
No fixed shot count, character, palette or amount of motion is required. Choose visual durations
for observation, comparison and anticipation. You may revise them by changing your visual plan.
The director owns the plan and later narration, the creator owns code. All roles are Sol max.

Return one JSON object: {"notes":"brief work record", "observations":[
 {"cue":"id","findings":["actual observations of supplied pixels"]}],"action":"...","args":{...}}.
Available actions (role permissions apply):
write_visual_plan {"plan":{"title":"...","rationale":"...","cues":[
 {"id":"safe_id","heading":"...","visual":"your original visual design",
 "learning_purpose":"what the viewer should notice","duration":seconds,
 "anchors":[{"id":"unique_event_id","meaning":"your actual visual milestone"}]}]}}
  Visual timing only. No TTS, narration, sentence clock or audio is generated.
delegate/handoff {"message":"your complete original message to the other role"}
write_code {"source":"complete GeneratedLesson Python source"}
replace_code {"edits":[{"old":"unique exact text","new":"your replacement"}]}
read_api {"symbols":["Line", "VisualLessonScene.mark", "Scene.play"]}
render {}  Produces actual video, measured visual events, and current cue evidence.
inspect_segments {"ids":["current_cue_id",...]}
inspect_frames {"times":[seconds,...]}  Up to six in-range full-resolution samples.
request_review {}  Director must first have recorded actual observations for every current cue.
  Before narration: a fresh reviewer sees public goals and actual silent pixels, not your plan/code.
  After narration: a fresh reviewer checks current code, measured events, narration intent and pixels.
write_narration {"plan":{"segments":[{"cue":"cue_id","anchor":"measured_event_id",
 "relation":"before|during|after","text":"natural Chinese speech for this visual moment"}]}}
  Only AFTER current silent visual approval. This drafts speech for future open-source TTS;
  it neither creates audio nor changes the visual clock. Cover every cue; no fixed text length.
finish {} Requires both genuine independent approvals, unchanged inputs and full decode.
stop {"reason":"..."}  Transport/unknown requests are never implicitly rebilled.

Runtime: Python 3.12, ManimGL 1.7.2 (not ManimCE), 1920x1080, 30fps.
Use from manimlib import *, numpy, math, and
from manimind.experiments.visual_first_support import VisualLessonScene
Define GeneratedLesson(VisualLessonScene). Do not override setup/tear_down.
self.cues has your visual cue start/duration/anchors. self.until(visual_seconds, *animations)
or self.play/self.wait are available. End at the planned VISUAL timeline duration.
self.mark(event_id) records the actual time AFTER the named visual state is visible.
Record every declared event once, inside its cue. These are measured events, not predicted times.
self.cn(text,size=32,color=...), self.formula(latex,size=38,color=...),
self.number(value,size=32,color=...,decimals=2) provide typography.
Use Group for objects containing raster images; VGroup is vector-only. Never Write on images.
No candidate filesystem, networking, process or environment access. Do not invent private APIs.
You have received sampled frames, not continuous video/audio. Do not claim listening or student tests.
"""


class SolVisualFirst(CodexTeamExperiment):
    received_checkpoint = SolLearningWorkflow.received_checkpoint

    @property
    def profile_path(self):
        return ROOT / self.config["workflow_profile"]

    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__), self.profile_path,
                Path(__file__).with_name("visual_first_data.py"), Path(__file__).with_name("visual_first_support.py"),
                Path(__file__).with_name("learning_workflow.py"), Path(__file__).with_name("learning_runtime.py"),
                Path(__file__).with_name("sol_learning_workflow.py"), Path(__file__).with_name("subscription_quota.py"),
                ROOT / "src/manimind/review/learning_quality.py"]

    def protocol(self):
        return {"systems": {r: native_system(r) for r in ("director", "creator", "reviewer")},
                "contract": CONTRACT, "allowed_actions": {r: sorted(a) for r, a in ALLOWED.items()},
                "profile": pilot.read_json(self.profile_path), "model": "gpt-6.1-sol", "effort": "max",
                "writer": "visual-first orchestrator", "consumers": ["roles", "review gate", "auditor"],
                "lifecycle": "Frozen before production", "invalidation": "Config, profile or implementation drift",
                "delivery": "Silent visual master plus text/event narration draft; no final voice approval"}

    def verify(self):
        super().verify()
        path = self.out / "narration-plan.json"
        if path.exists():
            origin = pilot.read_json(self.context / "narration-authorship.json")
            raw = Path(origin["extracted_plan"])
            expected = narration_plan(pilot.read_json(raw), pilot.read_json(self.out / "timeline.json"),
                                      pilot.read_json(self.out / "visual-events.json"))
            if (pilot.sha256(raw) != origin["extracted_sha256"] or pilot.sha256(path) != origin["narration_sha256"]
                    or pilot.read_json(path) != expected):
                raise ValueError("Post-visual narration was changed outside its original model plan")

    def actor_context(self, role):
        actor = self.team["actors"][role]
        payload = {"public_brief": self.config["brief"], "your_role": role,
                   "allowed_actions": sorted(ALLOWED[role]), "own_history": actor["history"],
                   "team_messages_to_you": actor["incoming"], "observed": actor["observed"],
                   "images_to_review_now": actor["pending_cues"],
                   "workflow_profile": pilot.read_json(self.profile_path),
                   "phase": self.team.get("visual_phase", "visual_draft")}
        for key, path in (("visual_plan", self.spec_path), ("visual_timeline", self.out / "timeline.json"),
                          ("measured_visual_events", self.out / "visual-events.json"),
                          ("narration_draft", self.out / "narration-plan.json")):
            if path.exists():
                payload[key] = pilot.read_json(path)
        if (self.out / "candidate.py").exists():
            payload["current_source"] = (self.out / "candidate.py").read_text()
        for key in ("visual_review", "narration_review"):
            if self.team.get(key):
                payload[key] = pilot.read_json(Path(self.team[key]["path"]))
        return json.dumps(payload, ensure_ascii=False) + "\n" + CONTRACT

    def hashes(self):
        return {name: pilot.sha256(self.out / name) for name in
                ("spec.json", "timeline.json", "candidate.py", "visual-events.json")}

    def invalidate_visual(self, state):
        self.invalidate(state)
        self.team.update(visual_phase="visual_draft", visual_review=None, narration_review=None, approval_current=False)
        for name in ("narration-plan.json", "visual-events.json"):
            path = self.out / name
            if path.exists():
                shutil.copy2(path, self.current_step / f"before-{name}")
                path.unlink()

    def install_visual_plan(self, plan, state):
        timeline = visual_timeline(plan)
        self.invalidate_visual(state)
        directory = self.current_step / "extracted-visual-plan"
        directory.mkdir()
        pilot.write_json(directory / "answer.json", plan)
        pilot.write_json(self.spec_path, {**plan, "facts": self.config["brief"]["facts"]})
        pilot.write_json(self.out / "timeline.json", timeline)
        pilot.write_json(self.context / "authorship.json", {
            "plan_answer": str(directory / "answer.json"), "plan_answer_sha256": pilot.sha256(directory / "answer.json"),
            "spec_sha256": pilot.sha256(self.spec_path), "scope": "model-authored visual plan, no narration or TTS"})
        return {"visual_timeline": timeline, "audio_generated": False}

    def install_source(self, source, state):
        if not self.spec_path.exists():
            raise ValueError("Create the visual plan first")
        check_visual_source(source)
        self.invalidate_visual(state)
        directory = self.current_step / "extracted-code"
        directory.mkdir()
        (directory / "answer.txt").write_text(source)
        (self.out / "candidate.py").write_text(source)
        pilot.write_json(self.out / "candidate-origin.json", {
            "answer": str(directory / "answer.txt"), "answer_sha256": pilot.sha256(directory / "answer.txt"),
            "extracted_source": str(directory / "answer.txt"), "source_sha256": pilot.sha256(self.out / "candidate.py")})
        return {"source_sha256": pilot.sha256(self.out / "candidate.py")}

    def latest_video(self, state):
        receipt = state.get("latest_render")
        if not receipt or not receipt.get("tool_success") or receipt["input_hashes"] != self.hashes():
            raise ValueError("Render and validate the current silent source first")
        video = Path(receipt["video_path"])
        if pilot.sha256(video) != receipt["video_sha256"]:
            raise ValueError("Rendered video changed")
        return video, float(next(s for s in pilot.probe(video)["streams"] if s["codec_type"] == "video")["duration"])

    def render_silent(self, state):
        self.verify()
        check_visual_source((self.out / "candidate.py").read_text())
        self.invalidate_visual(state)
        state["renders"] += 1
        self.save_state(state)
        version = state["renders"]
        name = f"visual-v{version:03d}"
        code = write_scene_code((self.out / "candidate.py").read_text(), output_dir=self.out, segment_id=name)
        before = {p: pilot.sha256(self.out / p) for p in ("spec.json", "timeline.json", "candidate.py")}
        command = build_manim_render_command(code_path=code, scene_class_name="GeneratedLesson", output_dir=self.out,
                                            segment_id=name, quality="h", config_file=self.out / "render.yml")
        inherited = _render_environment()
        env = {k: inherited[k] for k in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "VIRTUAL_ENV") if k in inherited}
        env.update(MANIMIND_FREEFORM_OUTPUT=str(self.out), PYTHONPATH=str(ROOT / "src"),
                   MANIMIND_DISABLE_DOTENV="1", PYTHONDONTWRITEBYTECODE="1")
        log = self.session / f"render-{version:03d}.log"
        receipt = {"version": version, "tool_success": False, "log": str(log)}
        try:
            with log.open("w") as stream:
                result = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(self.sandbox()), *command],
                                        env=env, cwd=self.out, stdout=stream, stderr=subprocess.STDOUT, timeout=2400)
            if result.returncode:
                raise RuntimeError(f"Renderer exit {result.returncode}")
            videos = list((self.out / "manim/media/manimgl").glob(f"**/{name}.mp4"))
            if len(videos) != 1 or before != {p: pilot.sha256(self.out / p) for p in before}:
                raise ValueError("Render output is ambiguous or source inputs changed")
            video = videos[0]
            timeline = pilot.read_json(self.out / "timeline.json")
            validate_events(timeline, pilot.read_json(self.out / "visual-events.json"))
            streams = pilot.probe(video)["streams"]
            if [s["codec_type"] for s in streams] != ["video"]:
                raise ValueError("Visual master must contain no audio or narration subtitle stream")
            if abs(float(streams[0]["duration"]) - timeline["duration"]) > .15:
                raise ValueError("Rendered visual duration drift")
            receipt.update(tool_success=True, video_path=str(video), video_sha256=pilot.sha256(video), input_hashes=self.hashes())
            state["latest_render"] = receipt
            pilot.write_json(self.out / "render.json", receipt)
            frames = []
            for cue in timeline["cues"]:
                times = [round(cue["start"] + cue["duration"] * f, 3) for f in (.12, .37, .62, .87)]
                frames.extend({**r, "cue": cue["id"]} for r in self.frame_records(video, times, self.out / f"frames-v{version:03d}" / cue["id"]))
            pilot.write_json(self.out / "review-input.json", {
                "video_path": str(video), "hashes": self.hashes(), "video_sha256": pilot.sha256(video),
                "duration": timeline["duration"], "frames": frames, "cue_ids": [c["id"] for c in timeline["cues"]],
                "mode": "silent_no_narration_subtitles"})
            LearningWorkflow.collect_motion_evidence(self)
            inspection = self.inspect_segments([c["id"] for c in timeline["cues"]], state)
            return {"receipt": receipt, "automatic_inspection": inspection}
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            receipt["tool_success"] = False
            state["latest_render"] = receipt
            return {"receipt": receipt, "execution_error": str(exc),
                    "raw_log_tail": log.read_text()[-18000:] if log.exists() else ""}
        finally:
            pilot.write_json(self.session / f"render-{version:03d}.json", receipt)

    def inspect_segments(self, ids, state):
        known = {c["id"] for c in pilot.read_json(self.out / "timeline.json")["cues"]}
        if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or not set(ids) <= known:
            raise ValueError("Select distinct current cues")
        result, images = [], []
        evidence = pilot.read_json(self.out / "review-input.json")
        for offset in range(0, len(ids), 2):
            result.extend(AgentExperiment.inspect_segments(self, ids[offset:offset + 2], state))
            images.extend(state["images"])
        images.extend(s["path"] for t in evidence["temporal_evidence"] if t["cue"] in ids for s in t["sheets"])
        state.update(images=images, pending_cues=list(ids))
        return result

    def reviewer_request(self, stage, text, images):
        raw, directory = self.role_request("reviewer", stage, text + "\n" + QUALITY_FORMAT, images)
        value = decode_object(raw)
        validate_learning_review(value, whole=True)
        return value, directory

    def approval(self, kind):
        entry = self.team.get(f"{kind}_review")
        if not entry or pilot.sha256(Path(entry["path"])) != entry["sha256"]:
            raise ValueError(f"Current independent {kind} approval is required")
        report = pilot.read_json(Path(entry["path"]))
        video, _ = self.latest_video(pilot.read_json(self.state_path))
        if (report["status"] != "pass" or report["hashes"] != self.hashes()
                or report["video_sha256"] != pilot.sha256(video)):
            raise ValueError(f"Independent {kind} approval is stale or did not pass")
        if kind == "narration" and report["narration_sha256"] != pilot.sha256(self.out / "narration-plan.json"):
            raise ValueError("Narration changed since independent review")
        judgment = report["judgment"]
        request = Path(judgment["request"]).resolve()
        if not request.is_relative_to(self.review_session.resolve()):
            raise ValueError("Review request belongs to another production")
        record = pilot.read_json(request / "record.json")
        original = pilot.read_json(request / "input.json")
        if (record["status"] != "received" or record["role"] != "reviewer"
                or record["input_sha256"] != pilot.sha256(request / "input.json")
                or record["answer_sha256"] != pilot.sha256(request / "answer.txt")
                or judgment["answer_sha256"] != record["answer_sha256"]
                or decode_object((request / "answer.txt").read_text()) != judgment["review"]
                or judgment["review"]["status"] != "pass"):
            raise ValueError("Approval differs from the genuine independent answer")
        validate_learning_review(judgment["review"], whole=True)
        supplied = {row["path"]: row["sha256"] for row in original["images"]}
        evidence_path = Path(entry["path"]).parent / "evidence.json"
        if pilot.sha256(evidence_path) != report["evidence_sha256"]:
            raise ValueError("Review evidence changed")
        evidence = pilot.read_json(evidence_path)
        if evidence != pilot.read_json(self.out / "review-input.json"):
            raise ValueError("Current review evidence differs")
        for frame in [*evidence["frames"], *[s for t in evidence["temporal_evidence"] for s in t["sheets"]]]:
            if supplied.get(frame["path"]) != frame["sha256"] or pilot.sha256(Path(frame["path"])) != frame["sha256"]:
                raise ValueError("Independent reviewer did not receive current pixels")
        for frame in [f for t in evidence["temporal_evidence"] for f in t["frames"]]:
            if pilot.sha256(Path(frame["path"])) != frame["sha256"]:
                raise ValueError("Original temporal evidence changed")
        return report

    def review_current(self, state):
        self.latest_video(state)
        evidence = pilot.read_json(self.out / "review-input.json")
        if set(self.team["actors"]["director"]["observed"]) != set(evidence["cue_ids"]):
            raise ValueError("Director must inspect every current visual cue before independent review")
        kind = "narration" if (self.out / "narration-plan.json").exists() else "visual"
        if kind == "narration":
            self.approval("visual")
        self.team["cycle"] += 1
        self.save_team()
        directory = self.review_session / f"cycle-{self.team['cycle']:02d}-{kind}"
        directory.mkdir()
        pilot.write_json(directory / "evidence.json", evidence)
        timeline = pilot.read_json(self.out / "timeline.json")
        context = {"public_brief": self.config["brief"], "review_mode": kind,
                   "cue_boundaries": [{k: c[k] for k in ("id", "start", "duration")} for c in timeline["cues"]],
                   "instruction": "Judge actual silent visuals. No spoken audio or narration subtitles exist. Necessary labels are allowed; not every abstract explanation must be speech-free. Do not claim listening or student testing."}
        if kind == "narration":
            context.update(current_source=(self.out / "candidate.py").read_text(),
                           visual_plan=pilot.read_json(self.spec_path),
                           measured_events=pilot.read_json(self.out / "visual-events.json"),
                           narration_draft=pilot.read_json(self.out / "narration-plan.json"),
                           instruction="Audit scientific source and narration intent against current pixels and measured events. before/during/after is semantic intent, NOT final spoken timing. Check that future narration explains rather than repeats the screen. No audio exists; do not certify final synchronization or voice quality.")
        images = [Path(f["path"]) for f in evidence["frames"]]
        images += [Path(s["path"]) for t in evidence["temporal_evidence"] for s in t["sheets"]]
        pilot.write_json(directory / "context.json", context)
        judgment = self.review_batch(f"cycle-{self.team['cycle']:02d}-{kind}-whole", json.dumps(context, ensure_ascii=False),
                                     evidence["cue_ids"], evidence["frames"], images, state)
        if evidence["hashes"] != self.hashes():
            raise ValueError("Visual inputs changed during review")
        report = {"kind": kind, "status": judgment["review"]["status"], "hashes": self.hashes(),
                  "video_sha256": evidence["video_sha256"], "judgment": judgment,
                  "evidence_sha256": pilot.sha256(directory / "evidence.json"),
                  "narration_sha256": pilot.sha256(self.out / "narration-plan.json") if kind == "narration" else None,
                  "limitations": ["Sampled pixels, not continuous viewing", "No audio/listening or student comprehension test",
                                  "Same-model fresh-context review; not different-model agreement"]}
        path = directory / "report.json"
        pilot.write_json(path, report)
        self.team[f"{kind}_review"] = {"path": str(path), "sha256": pilot.sha256(path)}
        self.team["visual_phase"] = ("visual_approved" if kind == "visual" else "narration_approved") if report["status"] == "pass" else f"{kind}_revision"
        return {"raw_independent_review": report}

    def release_silent(self, state):
        self.verify()
        visual, narration = self.approval("visual"), self.approval("narration")
        video, duration = self.latest_video(state)
        pilot.run([pilot.FFMPEG, "-v", "error", "-i", video, "-f", "null", "-"], timeout=300)
        self.verify()
        self.approval("visual")
        self.approval("narration")
        folder = self.out / "playback"
        folder.mkdir()
        target = folder / "visual-master.mp4"
        shutil.copyfile(video, target)
        if pilot.sha256(target) != visual["video_sha256"]:
            raise ValueError("Playback copy changed")
        delivery = {"video": str(target), "sha256": pilot.sha256(target), "duration": duration,
                    "scope": "independently reviewed silent visual master", "audio_status": "not_generated",
                    "narration_plan": str(self.out / "narration-plan.json"),
                    "narration_sha256": pilot.sha256(self.out / "narration-plan.json"),
                    "visual_review": self.team["visual_review"], "narration_review": self.team["narration_review"],
                    "hashes": self.hashes(), "full_decode_passed": True,
                    "limitations": narration["limitations"] + ["Narration is a text draft for later open-source speech; final voice and audio/visual synchronization remain unapproved"]}
        pilot.write_json(self.out / "delivery.json", delivery)
        self.team.update(status="complete", finished_at=now(), visual_phase="silent_delivered")
        return delivery

    def dispatch_role(self, role, command, state):
        action, args = command["action"], command.get("args", {})
        if action not in ALLOWED.get(role, set()):
            raise ValueError(f"Tool {action} is not available to {role}")
        if action in {"delegate", "handoff"}:
            message = args.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("Original message cannot be empty")
            target = "creator" if action == "delegate" else "director"
            self.team["actors"][target]["incoming"].append({"from": role, "turn": self.team["turn"] + 1, "message": message})
            self.team["active_role"] = target
            return {"delivered_to": target, "message_unchanged": True}
        if action == "write_visual_plan":
            return self.install_visual_plan(args["plan"], state)
        if action == "write_code":
            return self.install_source(args["source"], state)
        if action == "replace_code":
            return self.install_source(apply_edits((self.out / "candidate.py").read_text(), args["edits"]), state)
        if action == "render":
            result = self.render_silent(state)
        elif action == "inspect_segments":
            result = self.inspect_segments(args["ids"], state)
        elif action == "inspect_frames":
            video, duration = self.latest_video(state)
            times = args["times"]
            if (not isinstance(times, list) or not 1 <= len(times) <= 6
                    or any(type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t < duration for t in times)):
                raise ValueError("Select one to six in-range times")
            frames = self.frame_records(video, times, self.current_step / "detail")
            state.update(images=[f["path"] for f in frames], pending_cues=[])
            result = frames
        elif action == "request_review":
            return self.review_current(state)
        elif action == "write_narration":
            self.approval("visual")
            plan = narration_plan(args["plan"], pilot.read_json(self.out / "timeline.json"), pilot.read_json(self.out / "visual-events.json"))
            extracted = self.current_step / "extracted-narration.json"
            pilot.write_json(extracted, args["plan"])
            pilot.write_json(self.out / "narration-plan.json", plan)
            pilot.write_json(self.context / "narration-authorship.json", {
                "extracted_plan": str(extracted), "extracted_sha256": pilot.sha256(extracted),
                "narration_sha256": pilot.sha256(self.out / "narration-plan.json"),
                "writer": "mechanical extraction of the director's own plan", "consumers": ["verifier", "reviewer"],
                "lifecycle": "Current post-visual text draft", "invalidation": "Visual events, text or source changes"})
            self.team.update(narration_review=None, visual_phase="narration_draft")
            return plan
        elif action == "read_api":
            symbols = args["symbols"]
            if not isinstance(symbols, list) or not symbols or not all(isinstance(s, str) for s in symbols):
                raise ValueError("Provide public API symbols")
            rows = []
            for name in symbols:
                if name == "VisualLessonScene" or name.startswith("VisualLessonScene."):
                    from .visual_first_support import VisualLessonScene
                    parts = name.split(".")
                    if len(parts) > 2 or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", p) for p in parts):
                        raise ValueError("Only public visual helper methods")
                    obj = VisualLessonScene if len(parts) == 1 else getattr(VisualLessonScene, parts[1], None)
                    if obj is None or not (inspect.isclass(obj) or inspect.isfunction(obj)):
                        rows.append({"symbol": name, "error": "No public helper method"})
                    else:
                        rows.append({"symbol": name, "signature": str(inspect.signature(obj)), "source": inspect.getsource(obj)[:18000]})
                else:
                    rows.extend(api_reference([name]))
            return rows
        elif action == "finish":
            return self.release_silent(state)
        elif action == "stop":
            self.team.update(status="model_stopped", finished_at=now(), stop_reason=args)
            return args
        else:
            raise ValueError("Unknown action")
        self.team["actors"][role].update(images=list(state["images"]), pending_cues=list(state["pending_cues"]))
        return result


def launch(config):
    experiment = SolVisualFirst(config)
    experiment.initialize()
    lock = experiment.session / "launch.lock"
    with lock.open("x"):
        try:
            path = experiment.session / "launcher.json"
            if path.exists():
                try:
                    os.kill(pilot.read_json(path)["pid"], 0)
                except ProcessLookupError:
                    pass
                else:
                    raise ValueError("Existing runner is alive")
            state = pilot.read_json(experiment.team_path)
            if state.get("inflight") or (experiment.session / "team.lock").exists() or state["status"] != "ready":
                raise ValueError("Background startup requires a fresh unlocked ready checkpoint")
            args = ["/usr/bin/caffeinate", "-i", sys.executable, "-m", "manimind.experiments.sol_visual_first", "--config", str(config)]
            with (experiment.session / "runner.log").open("a") as log:
                process = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            receipt = {"pid": process.pid, "started_at": now(), "argv": args, "config_sha256": pilot.sha256(config),
                       "launcher_sha256": pilot.sha256(Path(__file__)), "writer": "visual-first launcher",
                       "consumers": ["operator", "duplicate guard"], "lifecycle": "Current process only",
                       "invalidation": "Process exit, unresolved request or frozen-source drift"}
            pilot.write_json(path, receipt)
            return receipt
        finally:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--resume-received-request", action="store_true")
    args = parser.parse_args()
    if args.background and (args.initialize_only or args.resume_received_request):
        parser.error("Background startup cannot resume or initialize only")
    preload_runtime()
    if args.background:
        print(json.dumps(launch(args.config.resolve())))
        return
    experiment = SolVisualFirst(args.config)
    experiment.initialize()
    bind_adapter(experiment)
    if args.initialize_only:
        return
    capture_baseline(experiment)
    with (experiment.session / "quota-observer.log").open("a") as log:
        observer = subprocess.Popen([sys.executable, "-m", "manimind.experiments.subscription_quota", "--project", experiment.id],
                                    stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
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
