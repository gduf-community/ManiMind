"""New Sol review adapter; historical visual-first executors remain frozen.

The existing creative tool surface and free scene design remain unchanged.
This adapter adds the v2 profile and evidence-backed editorial review checks,
not a lesson template or a new speech-before-animation constraint.
"""

from pathlib import Path

from .freeform_isolated import decode_object
from .sol_visual_first import SolVisualFirst
from manimind.postproduce import pilot
from manimind.review.learning_quality import QUALITY_FORMAT
from manimind.review.understanding_quality import REVIEW_FORMAT, validate_editorial_review


class SolUnderstandingFirst(SolVisualFirst):
    def frozen_paths(self):
        return [*super().frozen_paths(), Path(__file__),
                pilot.ROOT / "src/manimind/review/understanding_quality.py",
                pilot.ROOT / "src/manimind/review/semantic_focus.py"]

    def protocol(self):
        value = super().protocol()
        value.update(editorial_review_contract=REVIEW_FORMAT, entrypoint=__name__,
                     completion_scope="Silent visuals/text only; final full-utterance audio timing is a separate gate")
        return value

    def actor_context(self, role):
        return super().actor_context(role) + "\n" + REVIEW_FORMAT + "\nUse the current workflow_profile as guidance. Preserve creative freedom; technical passage alone is not editorial quality."

    def reviewer_request(self, stage, text, images):
        raw, directory = self.role_request("reviewer", stage, text + "\n" + QUALITY_FORMAT + "\n" + REVIEW_FORMAT, images)
        value = decode_object(raw)
        timeline = pilot.read_json(self.out / "timeline.json")
        validate_editorial_review(value, duration=timeline["duration"],
                                  stage="narration" if "narration" in stage else "visual")
        return value, directory

    def approval(self, kind):
        report = super().approval(kind)
        validate_editorial_review(report["judgment"]["review"],
                                  duration=pilot.read_json(self.out / "timeline.json")["duration"], stage=kind)
        return report


def main():
    import argparse
    from .learning_runtime import preload_runtime, bind_adapter
    from .sol_learning_workflow import capture_baseline

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--resume-received-request", action="store_true")
    args = parser.parse_args()
    preload_runtime()
    experiment = SolUnderstandingFirst(args.config)
    experiment.initialize()
    bind_adapter(experiment)
    if args.initialize_only:
        return
    capture_baseline(experiment)
    experiment.run_team(resume_received=args.resume_received_request)


if __name__ == "__main__":
    main()
