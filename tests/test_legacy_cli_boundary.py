"""Offline isolation tests; no model, renderer, media or native state is used."""

import json
import sys
from types import SimpleNamespace

import pytest

from manimind import main as cli


@pytest.mark.parametrize("command", ["assemble-video", "pipeline-run"])
def test_legacy_commands_stop_before_inputs(monkeypatch, command):
    monkeypatch.setattr(sys, "argv", ["manimind", command, "missing.json"])
    monkeypatch.setattr(cli, "_build_plan_model_from_manifest", lambda *args: pytest.fail("manifest read"))
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2


@pytest.mark.parametrize("verdict,execution,expected", [
    ("block", True, False), (None, True, False), ("pass", False, False), ("pass", True, True),
])
def test_legacy_summary_requires_explicit_review(monkeypatch, capsys, verdict, execution, expected):
    from manimind.agents import orchestrator

    result = SimpleNamespace(success=execution, project_id="offline", session_id="offline",
                             stage_count=1, error_count=0, stage_results=[],
                             outputs={"review": {"verdict": verdict}})
    monkeypatch.setattr(sys, "argv", ["manimind", "pipeline-run", "missing.json", "--legacy-experiment"])
    monkeypatch.setattr(cli, "_build_plan_model_from_manifest", lambda *a: object())
    monkeypatch.setattr(cli, "_get_llm_client", lambda *a: None)
    monkeypatch.setattr(cli, "_get_code_llm_client", lambda: None)
    monkeypatch.setattr(orchestrator.Orchestrator, "run", lambda *a, **kw: result)
    if expected:
        cli.main()
    else:
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["success"] is expected
    assert output["execution_completed"] is execution
    assert output["scope"] == "legacy_experiment_not_release"


@pytest.mark.parametrize("outputs", [{}, {"review": None}, {"review": []},
                                    {"review": "pass"}, {"review": False}, None, []])
def test_missing_or_malformed_review_has_explainable_failure(monkeypatch, capsys, outputs):
    from manimind.agents import orchestrator

    result = SimpleNamespace(success=True, project_id="offline", session_id="offline",
                             stage_count=1, error_count=0, stage_results=[], outputs=outputs)
    monkeypatch.setattr(sys, "argv", ["manimind", "pipeline-run", "missing.json", "--legacy-experiment"])
    monkeypatch.setattr(cli, "_build_plan_model_from_manifest", lambda *a: object())
    monkeypatch.setattr(cli, "_get_llm_client", lambda *a: None)
    monkeypatch.setattr(cli, "_get_code_llm_client", lambda: None)
    monkeypatch.setattr(orchestrator.Orchestrator, "run", lambda *a, **kw: result)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["success"] is False
    assert output["review_check"] == "missing_or_invalid"
