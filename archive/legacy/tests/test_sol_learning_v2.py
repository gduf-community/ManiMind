import json
import pytest

from manimind.experiments import codex_cli_team, freeform_review_cycle
from manimind.experiments import sol_learning_v2 as module
from manimind.experiments.sol_learning_v3 import SolLearningV3
from manimind.postproduce import pilot
from manimind.review.learning_quality import DIMENSIONS


def test_v2_entry_point_rejects_an_old_mislabelled_profile():
    value = module.SolLearningV2.__new__(module.SolLearningV2)
    value.config = {"workflow_profile": str(pilot.ROOT / "configs/learning-workflow-v1.json")}
    with pytest.raises(ValueError, match="no-subtitle-prose"):
        value.protocol()


def test_diagnostics_never_forward_full_prose_or_other_cues():
    audit = {"rows": [{"text": "AUTHOR_SCRIPT_SENTINEL"}], "timeline_sha256": "timeline",
             "blockers": [{"cue": "a", "problem": "Orphan punctuation", "lines": ["SCRIPT_LINE_SENTINEL"]},
                          {"cue": "later", "problem": "FUTURE_DIAGNOSTIC_SENTINEL"}],
             "advisories": [{"cue": "a", "problem": "Long subtitle", "characters": 48}]}
    result = module.subtitle_diagnostics(audit, ["a"])
    assert "SENTINEL" not in json.dumps(result)
    assert result["advisories"][0]["characters"] == 48
    assert result["blockers"][0]["problem"] == "Orphan punctuation"


@pytest.mark.parametrize("stage", ["cycle-01-batch-01", "cycle-01-whole"])
@pytest.mark.parametrize("workflow_type", [module.SolLearningV2, SolLearningV3])
def test_final_native_reviewer_input_has_no_narration_or_source(tmp_path, monkeypatch, stage, workflow_type):
    monkeypatch.setattr(freeform_review_cycle, "ROOT", tmp_path)
    value = workflow_type.__new__(workflow_type)
    value.id = "test-cold-boundary"
    value.out = tmp_path
    profile = "learning-workflow-v3.json" if workflow_type is SolLearningV3 else "learning-workflow-v2.json"
    value.config = {"workflow_profile": str(pilot.ROOT / "configs" / profile),
                    "brief": {"audience": "Learners", "goal": "Understand a mechanism"}}
    pilot.write_json(tmp_path / "timeline.json", {"duration": 10, "cues": [{
        "id": "a", "start": 0, "duration": 10, "spoken": "AUTHOR_SCRIPT_SENTINEL"}]})
    (tmp_path / "candidate.py").write_text("AUTHOR_SOURCE_SENTINEL")
    pilot.write_json(tmp_path / "review-input.json", {
        "temporal_evidence": [{"cue": "a", "frames": [{"time": .5}], "sheets": [{"path": str(tmp_path / "sheet.jpg"), "sha256": "image"}]},
                              {"cue": "later", "frames": [], "sheets": [{"path": "FUTURE_SHEET_SENTINEL"}]}],
        "subtitle_audit": {"rows": [{"text": "AUTHOR_SCRIPT_SENTINEL"}],
                           "blockers": [], "advisories": []}})
    seen = []

    def native(self, role, label, text, images):
        seen.append((text, images))
        answer = {"action": "review", "status": "pass", "checks": {k: "pass" for k in
                  ("mathematics", "visual_layout", "narrative", "cue_timing")},
                  "inspected_cues": [{"id": "a", "observations": [{"time": .5, "detail": "Actual supplied frame"}]}],
                  "issues": [], "limitations": ["Test transport"],
                  "viewer_test": {"can_explain": "A relationship", "missing_links": [],
                                  "transfer_question": "What changes?", "supported_answer": "Shown relation"},
                  "quality": {k: {"rating": 4, "evidence": "Frame at 0.5s"} for k in DIMENSIONS}}
        directory = tmp_path / "native-request"
        directory.mkdir()
        (directory / "answer.txt").write_text(json.dumps(answer))
        pilot.write_json(directory / "input.json", {"text": text, "images": [str(p) for p in images]})
        return json.dumps(answer), directory

    monkeypatch.setattr(codex_cli_team.CodexTeamExperiment, "role_request", native)
    value.review_batch(stage, value.reviewer_context(), ["a"], [{"cue": "a", "time": .5}], [], {})
    actual = (tmp_path / "native-request/input.json").read_text()
    assert "SENTINEL" not in actual
    assert "Understand a mechanism" in actual and "viewer_test" in actual
    assert str(tmp_path / "sheet.jpg") in actual
    assert len(seen) == 1
