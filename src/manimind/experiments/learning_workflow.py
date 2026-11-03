"""Versioned learning-video workflow; adds review evidence, not lesson templates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .freeform_team import TeamExperiment
from .freeform_agent import AgentExperiment
from .freeform_review_cycle import ReviewCycleExperiment
from manimind.postproduce import pilot
from manimind.postproduce.playback_package import package_playback
from manimind.review import learning_quality as quality

ROOT = pilot.ROOT


class LearningWorkflow(TeamExperiment):
    @property
    def profile_path(self):
        return (ROOT / self.config["workflow_profile"]).resolve()

    @property
    def profile(self):
        return pilot.read_json(self.profile_path)

    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__), Path(quality.__file__),
                self.profile_path, ROOT / "src/manimind/postproduce/playback_package.py"]

    def protocol(self):
        expected = {"version": "learning-rubric-1", "minimum_total": 80,
                    "rating_scale": [0, 1, 2, 3, 4], "weights": quality.DIMENSIONS,
                    "critical_minimum": {k: 3 for k in quality.CRITICAL}}
        if any(self.profile["evaluation"].get(k) != v for k, v in expected.items()):
            raise ValueError("The study scoring rubric is fixed across workflow versions")
        return {**super().protocol(), "workflow_profile": self.profile,
                "workflow_profile_sha256": pilot.sha256(self.profile_path),
                "quality_format": quality.QUALITY_FORMAT,
                "review_boundary": "Cold-view public goal and actual frames first; source/timing audit in a separate request",
                "workflow_changes": "Generic review and tool improvements, not previous-candidate content feedback"}

    def actor_context(self, role):
        return super().actor_context(role) + "\nFROZEN GENERIC WORKFLOW GUIDANCE:\n" + json.dumps(self.profile, ensure_ascii=False)

    def role_request(self, role, stage, text, images):
        if role == "reviewer":
            text += "\nFROZEN GENERIC WORKFLOW GUIDANCE:\n" + json.dumps(self.profile, ensure_ascii=False)
            text += "\n" + quality.QUALITY_FORMAT + "\nReview stage: " + stage
        return super().role_request(role, stage, text, images)

    def reviewer_request(self, stage, text, images):
        value, directory = super().reviewer_request(stage, text, images)
        quality.validate_learning_review(value, whole="whole" in stage or "source-audit" in stage)
        return value, directory

    def reviewer_context(self):
        timeline = pilot.read_json(self.out / "timeline.json")
        return json.dumps({
            "review_mode": "Cold-view: no author source, narration script, visual plan or director notes",
            "audience": self.config["brief"]["audience"], "learning_goal": self.config["brief"]["goal"],
            "duration": timeline["duration"],
            "cue_boundaries": [{"id": c["id"], "start": c["start"], "duration": c["duration"]}
                               for c in timeline["cues"]],
            "instruction": "Assess what the supplied pixels actually explain; do not fill gaps using your knowledge. Burned captions are part of the visible evidence.",
        }, ensure_ascii=False)

    def render(self, quality="h"):
        super().render(quality)
        self.collect_motion_evidence()

    def collect_motion_evidence(self):
        from PIL import Image, ImageDraw
        timeline = pilot.read_json(self.out / "timeline.json")
        evidence_path = self.out / "review-input.json"
        evidence = pilot.read_json(evidence_path)
        video = Path(evidence["video_path"])
        version = pilot.read_json(self.out / "render.json")["version"]
        folder = self.out / f"temporal-v{version:03d}"
        folder.mkdir()
        temporal = []
        for cue in timeline["cues"]:
            end = cue["start"] + cue["duration"]
            times = [round(cue["start"] + .05 + i * .5, 3)
                     for i in range(int(cue["duration"] * 2) + 1)
                     if cue["start"] + .05 + i * .5 < end - 1 / timeline["fps"]]
            records = self.frame_records(video, times, folder / cue["id"])
            sheets = []
            for offset in range(0, len(records), 16):
                sheet = Image.new("RGB", (1920, 4 * 294), "#202226")
                draw = ImageDraw.Draw(sheet)
                for j, record in enumerate(records[offset:offset + 16]):
                    with Image.open(record["path"]) as frame:
                        frame = frame.resize((480, 270))
                        x, y = j % 4 * 480, j // 4 * 294
                        sheet.paste(frame, (x, y + 24))
                        draw.text((x + 8, y + 5), f"{cue['id']} / {record['time']:.3f}s", fill="white")
                path = folder / f"{cue['id']}-{offset // 16 + 1:02d}.jpg"
                sheet.save(path, quality=95)
                sheets.append({"path": str(path), "sha256": pilot.sha256(path)})
            temporal.append({"cue": cue["id"], "frames": records, "sheets": sheets})
        audit = quality.subtitle_audit(timeline, quality.font_width())
        audit["timeline_sha256"] = pilot.sha256(self.out / "timeline.json")
        pilot.write_json(self.out / "subtitle-audit.json", audit)
        evidence.update(temporal_evidence=temporal, subtitle_audit=audit,
                        workflow_profile_sha256=pilot.sha256(self.profile_path))
        pilot.write_json(evidence_path, evidence)

    def inspect_segments(self, ids, state):
        result = super().inspect_segments(ids, state)
        evidence = pilot.read_json(self.out / "review-input.json")
        for item in result:
            entry = next(t for t in evidence["temporal_evidence"] if t["cue"] == item["cue"]["id"])
            item["temporal_sheets"] = entry["sheets"]
            state["images"].extend(s["path"] for s in entry["sheets"])
        return result

    def review_batch(self, label, context, ids, frames, images, state):
        evidence = pilot.read_json(self.out / "review-input.json")
        temporal = [t for t in evidence["temporal_evidence"] if t["cue"] in ids]
        images = list(images) + [Path(s["path"]) for t in temporal for s in t["sheets"]]
        context += "\nActual temporal sheets at 0.5s intervals; labels give video seconds:\n"
        context += json.dumps([{**t, "frames": [{"time": f["time"]} for f in t["frames"]]}
                               for t in temporal], ensure_ascii=False)
        context += "\nMechanical subtitle audit (not a semantic judgment):\n"
        context += json.dumps(evidence["subtitle_audit"], ensure_ascii=False)
        return super().review_batch(label, context, ids, frames, images, state)

    def independent_review(self, cycle):
        path, report = super().independent_review(cycle)
        evidence = pilot.read_json(self.out / "review-input.json")
        state = pilot.read_json(self.state_path)
        # A second context checks facts and narration, without replacing the cold-view verdict.
        context = ReviewCycleExperiment.reviewer_context(self)
        context += "\nSOURCE/TIMING AUDIT: independently check visible states, actual narration and facts."
        audit = self.review_batch(f"cycle-{cycle:02d}-source-audit", context, evidence["cue_ids"],
                                  evidence["frames"], [Path(f["path"]) for f in evidence["frames"]], state)
        report["segments"].append(report["whole"])
        report["whole"] = audit
        report["status"] = "pass" if all(j["review"]["status"] == "pass" for j in
            [*report["segments"], report["whole"]]) and not evidence["subtitle_audit"]["blockers"] else "revise"
        report["workflow_profile_sha256"] = pilot.sha256(self.profile_path)
        report["review_modes"] = ["cold_view_without_author_source_or_script", "source_and_narration_timing_audit"]
        pilot.write_json(path, report)
        return path, report

    def release(self):
        evidence = pilot.read_json(self.out / "review-input.json")
        if evidence["workflow_profile_sha256"] != pilot.sha256(self.profile_path):
            raise ValueError("Workflow profile changed after review")
        if evidence["subtitle_audit"]["blockers"]:
            raise ValueError("Mechanical subtitle blockers remain")
        for temporal in evidence["temporal_evidence"]:
            for item in [*temporal["frames"], *temporal["sheets"]]:
                if pilot.sha256(Path(item["path"])) != item["sha256"]:
                    raise ValueError("Temporal review pixels changed")
        report = pilot.read_json(Path(self.team["review_path"]))
        for judgment in [*report["segments"], report["whole"]]:
            quality.validate_learning_review(judgment["review"], whole="quality" in judgment["review"])
        result = super().release()
        package_playback({"lesson": self.out / "delivery.json"}, self.out / "playback")
        return {**result, "playback": str(self.out / "playback/lesson.mp4")}


def prepare_case(study_path: Path, case_id: str, profile_path: Path) -> Path:
    study = pilot.read_json(study_path)
    profile = pilot.read_json(profile_path)
    case = next(c for c in study["cases"] if c["id"] == case_id)
    context = ROOT / "runtime/projects" / study["study_id"]
    context.mkdir(parents=True, exist_ok=True)
    frozen_study = context / "protocol.json"
    protocol = {"study": study, "sha256": pilot.sha256(study_path),
                "writer": "study coordinator", "consumers": ["case runner", "auditor"],
                "lifecycle": "Frozen study; changing cases or evaluation rules requires new study id",
                "invalidation": "Study input or fixed scoring policy changes"}
    if frozen_study.exists() and pilot.read_json(frozen_study) != protocol:
        raise ValueError("Frozen study changed")
    if not frozen_study.exists():
        pilot.write_json(frozen_study, protocol)
    if case["split"] == "holdout":
        freeze = pilot.read_json(context / "holdout-freeze.json")
        if freeze["profile_sha256"] != pilot.sha256(profile_path):
            raise ValueError("Holdout must use the already frozen profile")
        for item in freeze["development_assessments"]:
            if pilot.sha256(Path(item["path"])) != item["sha256"]:
                raise ValueError("Development evidence changed after holdout freeze")
        if freeze["study_sha256"] != pilot.sha256(study_path):
            raise ValueError("Holdout study changed after freeze")
    project_id = f"{study['study_id']}-{profile['version']}-{case_id}"
    path = context / "run-configs" / f"{project_id}.json"
    config = pilot.read_json(ROOT / study["provider_config"])
    config.update(project_id=project_id, workflow_profile=str(profile_path.resolve().relative_to(ROOT)),
                  brief=case["brief"], study_id=study["study_id"], study_case=case_id, study_split=case["split"])
    if path.exists() and pilot.read_json(path) != config:
        raise ValueError("Run configuration is frozen; create a new workflow version")
    if not path.exists():
        pilot.write_json(path, config)
    return path


def freeze_holdout(study_path: Path, profile_path: Path) -> Path:
    study, profile = pilot.read_json(study_path), pilot.read_json(profile_path)
    context = ROOT / "runtime/projects" / study["study_id"]
    assessments = []
    for case in study["cases"]:
        if case["split"] != "development":
            continue
        path = context / "assessments" / f"{profile['version']}-{case['id']}.json"
        assessment = pilot.read_json(path)
        config_path = context / "run-configs" / f"{study['study_id']}-{profile['version']}-{case['id']}.json"
        config = pilot.read_json(config_path)
        delivery = pilot.read_json(ROOT / "outputs" / config["project_id"] / "delivery.json")
        if (assessment.get("case_id") != case["id"] or assessment.get("verdict") != "pass"
                or assessment.get("profile_sha256") != pilot.sha256(profile_path)
                or assessment.get("video_sha256") != delivery["sha256"]
                or pilot.sha256(Path(delivery["video"])) != delivery["sha256"]
                or assessment.get("blockers") != []):
            raise ValueError("Holdout requires passed, version-bound external development assessments")
        quality.validate_learning_review(assessment["review"], whole=True)
        if assessment["review"].get("status") != "pass":
            raise ValueError("Development assessment has not passed the fixed rubric")
        assessments.append({"path": str(path), "sha256": pilot.sha256(path)})
    if len(assessments) < 2:
        raise ValueError("At least two development domains are required before holdout")
    path = context / "holdout-freeze.json"
    value = {"profile": str(profile_path), "profile_sha256": pilot.sha256(profile_path),
             "study_sha256": pilot.sha256(study_path), "development_assessments": assessments,
             "writer": "study coordinator after external development review", "consumers": ["holdout runner", "auditor"],
             "lifecycle": "One-way holdout release, not a reusable tuning dataset",
             "invalidation": "Any bound profile, study or development assessment change"}
    if path.exists() and pilot.read_json(path) != value:
        raise ValueError("Holdout freeze is immutable; start a new study for further tuning")
    if not path.exists():
        pilot.write_json(path, value)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--case")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--resume-received-request", action="store_true")
    parser.add_argument("--freeze-holdout", action="store_true")
    args = parser.parse_args()
    if args.freeze_holdout:
        print(freeze_holdout(args.study.resolve(), args.profile.resolve()))
        return
    if not args.case:
        parser.error("--case is required when not freezing the holdout")
    path = prepare_case(args.study.resolve(), args.case, args.profile.resolve())
    experiment = LearningWorkflow(path)
    if args.initialize_only:
        experiment.initialize()
    else:
        experiment.run_team(resume_received=args.resume_received_request)


if __name__ == "__main__":
    main()
