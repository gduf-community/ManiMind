from pathlib import Path

import pytest

from manimind.experiments import isolated_render_repair as repair


@pytest.fixture
def context(tmp_path, monkeypatch):
    base = repair.base
    monkeypatch.setattr(base, "ROOT", tmp_path)
    cfg = base.pilot.read_json(base.CONFIG)
    protocol = {
        "config": cfg, "packet": "Frozen common packet", "system": base.SYSTEM,
        "packet_sha256": base.digest("Frozen common packet"), "source_hashes": {},
        "blind_project_ids": {"codex": "opaque-id", "deepseek": "opaque-ds", "kimi": "opaque-k"},
    }
    monkeypatch.setattr(base, "load", lambda suite: base.pilot.read_json(
        base.locations(suite)[0] / "protocol.json"))
    base.pilot.write_json(base.locations("parent")[0] / "protocol.json", protocol)
    source = tmp_path / "raw"
    source.mkdir()
    (source / "answer.txt").write_text("OWN ORIGINAL ANSWER")
    run = base.locations("parent")[2] / "codex-r1"
    base.pilot.write_json(run / "selection.json", {"selected": True})
    monkeypatch.setattr(base, "verify_selected_run", lambda *a: {
        "source": str(source), "record": {}, "answer": {"plan": {"id": "lesson"}}})
    monkeypatch.setattr(repair.pipeline, "frozen_plan", lambda *a: {"id": "opaque-id"})
    monkeypatch.setattr(repair.pipeline, "input_hashes", lambda *a: {"plan": "hash"})
    events = tmp_path / "runtime/sessions/opaque-id-components/events.json"
    base.pilot.write_json(events, {"events": [
        {"action": "render", "attempt": 1, "status": "started", "inputs": {"plan": "hash"}},
        {"action": "render", "attempt": 1, "status": "failed"}]})
    out = tmp_path / "outputs/opaque-id"
    folder = out / "renders/001"
    folder.mkdir(parents=True)
    wrapper = folder / "scene.py"
    wrapper.write_text(
        "from pathlib import Path\nfrom manimind.components.renderer import ComponentScene\n\n"
        "class ComponentDemo(ComponentScene):\n"
        f"    plan_path = Path({str(out / 'plan.json')!r})\n"
        f"    asset_dir = Path({str(folder)!r})\n")
    error = tmp_path / "runtime/sessions/opaque-id-components/render-001.json"
    base.pilot.write_json(error, {
        "success": False, "error": "manimgl_render_failed",
        "code_path": str(wrapper),
        "stderr_tail": "Exact\nValueError: original renderer error\n"})
    extension = repair.init("parent", "extension")
    return extension, error


def test_separate_protocol_retains_frozen_base(context):
    protocol = repair.load("extension")
    assert protocol["config"]["id"] == "isolated-20261020"
    assert protocol["extension"]["parent_suite"] == "parent"
    assert protocol["blind_project_ids"]["codex"] != "opaque-id"
    with pytest.raises(FileExistsError):
        repair.init("parent", "extension")


def test_feedback_contains_only_own_answer_and_exact_error(context):
    protocol, error = context
    packet, evidence = repair.feedback(protocol, "codex")
    assert "OWN ORIGINAL ANSWER" in packet
    stderr = repair.pilot.read_json(error)["stderr_tail"]
    assert stderr in packet
    assert evidence["stderr_sha256"] == repair.base.digest(stderr)
    assert evidence["render_error_sha256"] == repair.pilot.sha256(error)


@pytest.mark.parametrize("change", [
    {"success": True}, {"error": "timeout"}, {"stderr_tail": ""},
])
def test_non_render_failure_is_not_eligible(context, change):
    protocol, path = context
    error = repair.pilot.read_json(path)
    error.update(change)
    repair.pilot.write_json(path, error)
    with pytest.raises(ValueError):
        repair.feedback(protocol, "codex")


def test_changed_parent_invalidates_extension(context):
    path = repair.base.locations("parent")[0] / "protocol.json"
    data = repair.pilot.read_json(path)
    data["extra"] = True
    repair.pilot.write_json(path, data)
    with pytest.raises(ValueError, match="Parent protocol"):
        repair.load("extension")


def test_changed_extension_implementation_is_rejected(context):
    path = repair.base.locations("extension")[0] / "protocol.json"
    data = repair.pilot.read_json(path)
    data["extension"]["implementation_sha256"] = "changed"
    repair.pilot.write_json(path, data)
    with pytest.raises(ValueError, match="Extension protocol"):
        repair.load("extension")


def test_failure_uses_one_request_and_no_retry(context, monkeypatch):
    calls = []

    def fail(*args):
        calls.append(args)
        raise TimeoutError("No provider usage available")

    monkeypatch.setattr(repair.base, "codex_generate", fail)
    result = repair.generate("extension", "codex")
    assert len(calls) == 1
    assert result["status"] == "failed"
    assert result["cost_estimate"]["upper"] is None
    with pytest.raises(FileExistsError):
        repair.generate("extension", "codex")
    assert len(calls) == 1


def test_invalid_answer_does_not_get_another_repair(context, monkeypatch):
    monkeypatch.setattr(repair.base, "codex_generate", lambda *a: (
        "not JSON", {"usage": {}, "finish_reason": "stop"}))
    result = repair.generate("extension", "codex")
    assert result["status"] == "failed"
    assert "JSONDecodeError" in result["error"]
    assert not (repair.base.locations("extension")[2] / "codex-r1/selection.json").exists()


def test_same_authorization_cannot_create_another_suite(context):
    with pytest.raises(FileExistsError):
        repair.init("parent", "another-extension")


def test_cannot_chain_extensions(context):
    with pytest.raises(ValueError, match="chain"):
        repair.init("extension", "another-extension")


def test_error_change_after_freeze_is_rejected(context):
    protocol, path = context
    error = repair.pilot.read_json(path)
    error["stderr_tail"] = "Altered error"
    repair.pilot.write_json(path, error)
    with pytest.raises(ValueError, match="changed after"):
        repair.feedback(protocol, "codex")


def test_unrelated_render_input_is_rejected(context, monkeypatch):
    monkeypatch.setattr(repair.pipeline, "input_hashes", lambda *a: {"plan": "changed"})
    with pytest.raises(ValueError, match="render inputs"):
        repair.feedback(context[0], "codex")


def test_unrelated_plan_is_rejected(context, monkeypatch):
    monkeypatch.setattr(repair.pipeline, "frozen_plan", lambda *a: {"id": "other"})
    with pytest.raises(ValueError, match="render plan"):
        repair.feedback(context[0], "codex")
