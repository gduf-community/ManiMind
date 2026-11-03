import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from manimind.experiments.freeform_agent import (
    AgentExperiment, apply_edits, check_agent_source,
)


def test_exact_edits_are_model_authored_and_unique():
    assert apply_edits("abc def", [{"old": "abc", "new": "xyz"}]) == "xyz def"
    with pytest.raises(ValueError):
        apply_edits("abc abc", [{"old": "abc", "new": "xyz"}])
    with pytest.raises(ValueError):
        apply_edits("abc", [{"old": "", "new": "xyz"}])
    with pytest.raises(ValueError):
        apply_edits("abc", [{"old": "def", "new": "xyz"}])


@pytest.mark.parametrize("source", [
    "import os", "from pathlib import Path", "np.load('/secret')",
    "self.out.read_text()", "manimlib.os.system('x')", "eval('x')",
])
def test_unavailable_capabilities(source):
    with pytest.raises(ValueError):
        check_agent_source(source)


def test_native_scene_is_allowed():
    check_agent_source(
        "from manimlib import *\nimport numpy as np\n"
        "from manimind.experiments.freeform_support import LessonScene\n"
        "class GeneratedLesson(LessonScene):\n"
        " def construct(self):\n  self.play(ShowCreation(Line(LEFT, RIGHT)))\n"
    )


def agent_fixture(tmp_path):
    agent = AgentExperiment.__new__(AgentExperiment)
    agent.out = tmp_path / "out"
    agent.out.mkdir()
    agent.session = tmp_path / "session"
    agent.session.mkdir()
    agent.context = tmp_path / "context"
    agent.context.mkdir()
    agent.spec_path = agent.out / "spec.json"
    agent.config = {"max_renders": 2}
    agent.current_step = agent.session / "step-001"
    agent.current_step.mkdir()
    return agent


def test_revision_invalidates_current_render_and_reviews(tmp_path):
    agent = agent_fixture(tmp_path)
    (agent.out / "render.json").write_text("{}")
    (agent.out / "review-input.json").write_text("{}")
    state = {"observed": ["a"], "latest_render": {"success": True}}
    agent.invalidate(state)
    assert state["observed"] == [] and state["latest_render"] is None
    assert not (agent.out / "render.json").exists()
    assert (agent.current_step / "before-render.json").exists()


def test_finish_requires_current_complete_review(tmp_path):
    agent = agent_fixture(tmp_path)
    (agent.out / "timeline.json").write_text(json.dumps({"cues": [{"id": "a"}]}))
    with pytest.raises(ValueError, match="Complete current render"):
        agent.dispatch({"action": "finish"}, {"latest_render": None})
    (agent.out / "review-input.json").write_text("{}")
    with pytest.raises(ValueError, match="observations missing"):
        agent.dispatch({"action": "finish"},
                       {"latest_render": {"success": True, "tool_success": True}, "observed": []})


def test_render_budget_checked_before_execution(tmp_path):
    agent = agent_fixture(tmp_path)
    with pytest.raises(ValueError, match="budget exhausted"):
        agent.dispatch({"action": "render"}, {"renders": 2})


def test_plan_tts_failure_invalidates_prior_evidence_first(tmp_path, monkeypatch):
    agent = agent_fixture(tmp_path)
    for name in ("spec.json", "timeline.json", "render.json", "review-input.json"):
        (agent.out / name).write_text("{}")
    state = {"observed": ["a"], "latest_render": {"success": True}}
    def fail(*args):
        raise TimeoutError("TTS")
    monkeypatch.setattr(agent, "install_plan", fail)
    with pytest.raises(TimeoutError):
        agent.dispatch({"action": "write_plan", "args": {"plan": {}}}, state)
    assert state["latest_render"] is None and state["observed"] == []
    assert not (agent.out / "review-input.json").exists()


def test_timeout_cannot_reuse_previous_success_receipt(tmp_path, monkeypatch):
    from manimind.experiments import freeform_agent as module
    agent = agent_fixture(tmp_path)
    (agent.out / "candidate.py").write_text("from manimlib import *\n")
    (agent.out / "review-input.json").write_text("{}")
    (agent.session / "render-001.json").write_text('{"success":true}')
    monkeypatch.setattr(module.media, "Production",
                        lambda _: SimpleNamespace(session=agent.session))
    def fail(*args):
        raise TimeoutError("render timed out")
    monkeypatch.setattr(agent, "render", fail)
    state = {"renders": 1, "observed": ["a"]}
    result = agent.dispatch({"action": "render"}, state)
    assert result["receipt"] is None and "timed out" in result["execution_error"]
    assert state["latest_render"] is None
    assert not (agent.out / "review-input.json").exists()


def test_inspection_failure_cannot_submit_successful_raw_render(tmp_path, monkeypatch):
    from manimind.experiments import freeform_agent as module
    agent = agent_fixture(tmp_path)
    (agent.out / "candidate.py").write_text("from manimlib import *\n")
    monkeypatch.setattr(module.media, "Production",
                        lambda _: SimpleNamespace(session=agent.session))
    def fail(*args):
        log = agent.session / "render-001.log"
        log.write_text("render succeeded; duration check failed")
        (agent.session / "render-001.json").write_text(
            json.dumps({"success": True, "log": str(log), "input_hashes": {}}))
        raise ValueError("Timeline drift")
    monkeypatch.setattr(agent, "render", fail)
    state = {"renders": 0, "observed": []}
    agent.dispatch({"action": "render"}, state)
    assert state["latest_render"]["success"]
    assert not state["latest_render"]["tool_success"]


def test_fresh_config_excludes_previous_candidates():
    path = Path(__file__).resolve().parents[1] / "configs/deepseek-autonomous-20261020.json"
    data = json.loads(path.read_text())
    assert data["model"] == "deepseek-flash"
    assert "parent_experiment" not in data
    assert data["max_cost_CNY"] == 10


def test_installed_api_lookup_is_content_free():
    from manimind.experiments.freeform_agent import api_reference
    rows = api_reference(["Line.put_start_and_end_on", "Group"])
    assert all("source" in row for row in rows)
    assert "error" in api_reference(["os.system"])[0]
    with pytest.raises(ValueError):
        api_reference(["Scene.__init__"])


def test_real_sandbox_allows_tex_but_blocks_private_reads_and_writes(tmp_path):
    from manimind.experiments.freeform_agent import ROOT
    from manimind.render.manim_renderer import _render_environment
    agent = agent_fixture(tmp_path)
    profile = agent.sandbox()
    env = _render_environment()
    env["MANIMIND_DISABLE_DOTENV"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    code = (
        "from pathlib import Path\n"
        "from manimlib import Tex\n"
        "assert Tex('x', template='basic_ctex').get_width() > 0\n"
        f"p=Path({str(ROOT / '.env')!r})\n"
        "try:\n p.read_bytes()\nexcept PermissionError:\n pass\n"
        "else:\n raise AssertionError('private read allowed')\n"
        f"p=Path({str(ROOT / 'runtime/agent-forbidden-write-probe')!r})\n"
        "try:\n p.write_text('must be denied')\nexcept PermissionError:\n pass\n"
        "else:\n p.unlink(); raise AssertionError('outside write allowed')\n"
    )
    result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-f", str(profile), str(ROOT / "manimgl_env/bin/python"), "-c", code],
        cwd=agent.out, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr[-4000:]
