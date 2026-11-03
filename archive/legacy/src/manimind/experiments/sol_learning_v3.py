"""Batch current-media inspection; retain two independent whole-film gates."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from .freeform_agent import api_reference
from .freeform_review_cycle import ReviewCycleExperiment
from .freeform_team import ALLOWED
from .learning_runtime import preload_runtime, bind_adapter
from .learning_workflow import prepare_case, freeze_holdout
from .sol_learning_v2 import SolLearningV2
from .sol_learning_workflow import capture_baseline
from manimind.postproduce import freeform_pilot as media, pilot
from manimind.review.learning_quality import validate_learning_review


class SolLearningV3(SolLearningV2):
    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__)]

    def protocol(self):
        if self.profile.get("execution_mode") != "batch-evidence-dual-whole-review-v3":
            raise ValueError("This entry point requires the batched evidence profile")
        return {**super().protocol(),
                "inspection_transport": "Any distinct current cue ids in one tool call; successful render supplies actual inspection images automatically",
                "api_transport": "Public symbols are queried in local groups of four, returned in one role turn",
                "independent_review": "Separate fresh whole-film pixel and source/timing reviews; each covers every cue and must pass the unchanged rubric",
                "review_tradeoff": "Fewer separate reviews, not fewer supplied pixels; real production regression must test missed defects"}

    def inspect_segments(self, ids, state):
        timeline = pilot.read_json(self.out / "timeline.json")
        known = {c["id"] for c in timeline["cues"]}
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
            return [row for offset in range(0, len(names), 4) for row in api_reference(names[offset:offset + 4])]
        if action == "inspect_segments":
            result = self.inspect_segments(args["ids"], state)
        else:
            result = super().dispatch_role(role, command, state)
            if action != "render" or not (state.get("latest_render") or {}).get("tool_success"):
                return result
            ids = [c["id"] for c in pilot.read_json(self.out / "timeline.json")["cues"]]
            result = {**result, "automatic_inspection": self.inspect_segments(ids, state)}
        actor = self.team["actors"][role]
        actor.update(images=list(state["images"]), pending_cues=list(state["pending_cues"]))
        return result

    def independent_review(self, cycle):
        self.verify()
        state = pilot.read_json(self.state_path)
        video, _ = self.latest_video(state)
        production = media.Production(self.spec_path)
        evidence = pilot.read_json(self.out / "review-input.json")
        if evidence["hashes"] != production.hashes(video) or not state["latest_render"]["tool_success"]:
            raise ValueError("Independent review requires current complete rendered evidence")
        directory = self.review_session / f"cycle-{cycle:02d}"
        directory.mkdir()
        pilot.write_json(directory / "evidence.json", evidence)
        context = self.reviewer_context()
        (directory / "candidate-context.json").write_text(context)
        ids, frames = evidence["cue_ids"], evidence["frames"]
        images = [Path(f["path"]) for f in frames]
        cold = self.review_batch(f"cycle-{cycle:02d}-whole", context, ids, frames, images, state)
        pilot.write_json(directory / "cold-whole.json", cold)
        source_context = ReviewCycleExperiment.reviewer_context(self)
        source_context += "\nSOURCE/TIMING AUDIT: independently check current facts, narration and visible states."
        audit = self.review_batch(f"cycle-{cycle:02d}-source-audit", source_context, ids, frames, images, state)
        pilot.write_json(directory / "source-audit.json", audit)
        for judgment in (cold, audit):
            validate_learning_review(judgment["review"], whole=True)
        if evidence["hashes"] != production.hashes(video):
            raise ValueError("Media changed during independent review")
        passed = (all(j["review"]["status"] == "pass" for j in (cold, audit))
                  and not evidence["subtitle_audit"]["blockers"])
        report = {
            "cycle": cycle, "status": "pass" if passed else "revise", "hashes": evidence["hashes"],
            "evidence_sha256": pilot.sha256(directory / "evidence.json"), "segments": [cold], "whole": audit,
            "inspected_frames": [f["path"] for f in frames],
            "workflow_profile_sha256": pilot.sha256(self.profile_path),
            "review_modes": ["cold_view_without_author_source_or_script", "source_and_narration_timing_audit"],
            "limitations": ["Fresh-context same-model review, not independent model-family agreement",
                            "Whole-film reviews replace separate two-cue requests; quality impact needs actual validation",
                            "Sampled real frames, not continuous viewing or audio listening", "No student comprehension study"],
        }
        path = directory / "report.json"
        pilot.write_json(path, report)
        return path, report


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
    experiment = SolLearningV3(path)
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
