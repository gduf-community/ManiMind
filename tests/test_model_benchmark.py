"""Offline tests; these never contact a paid model or execute model code."""

import json
import socket
import struct
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from manimind.experiments import model_benchmark as bench


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def fail_network(*args, **kwargs):
        pytest.fail("Network access is forbidden in benchmark unit tests")

    monkeypatch.setattr(socket.socket, "connect", fail_network)
    monkeypatch.setattr(socket, "create_connection", fail_network)


@pytest.mark.parametrize("output_budget", [None, 65536])
@pytest.mark.parametrize("with_design", [False, True])
@pytest.mark.parametrize("cue_ids", [None, ["half", "tenth", "approach"]])
@pytest.mark.parametrize("name,key_name,model,endpoint,token_param", [
    ("mimo-ezlook-fast", "MIMO_EZLOOK_API_KEY", "mimo-v2.6-pro", "https://mimo.ezlook.top/v1", "max_completion_tokens"),
    ("mimo-ezlook-pro", "MIMO_EZLOOK_API_KEY", "mimo-v2.6-pro", "https://mimo.ezlook.top/v1", "max_completion_tokens"),
    ("mimo-pro", "MIMO_API_KEY", "mimo-v2.6-pro", "https://api.xiaomimimo.com/v1", "max_completion_tokens"),
    ("glm-flash", "ZAI_API_KEY", "glm-5.3-flash", "https://api.z.ai/api/paas/v4/", "max_tokens"),
    ("kimi-fast", "OPENAI_API_KEY", "kimi-k2.6", "https://api.moonshot.cn/v1", "max_tokens"),
])
def test_generation_uses_profile_credentials_and_budget(
    monkeypatch, tmp_path, name, key_name, model, endpoint, token_param, output_budget, cue_ids, with_design
):
    from manimind.llm import client as llm

    sdk = MagicMock()
    sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
        model=model, usage=SimpleNamespace(prompt_tokens=100, completion_tokens=200, total_tokens=300),
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(
            content="class GeneratedLesson(BenchmarkScene):\n    pass\n"))],
    )
    monkeypatch.setattr(llm, "OpenAI", sdk)
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.moonshot.cn/v1")
    monkeypatch.setenv(key_name, "profile-test-secret")
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "BASELINE", tmp_path / "baseline")
    for attr, filename in [("SPEC", "spec.json"), ("CONFIG", "manimgl.yml"), ("SUPPORT", "support.py")]:
        path = tmp_path / filename
        path.write_text("{}")
        monkeypatch.setattr(bench, attr, path)
    cues = [{"id": cue, "start": i, "duration": 1, "speech_start": i + 0.3,
             "audio_path": f"old/{cue}.wav"} for i, cue in enumerate(["graph", "half", "tenth", "approach"])]
    bench.write_json(bench.SPEC, {"cues": cues})
    bench.write_json(bench.BASELINE / "timeline.json", {"spec_sha256": bench.sha256(bench.SPEC), "fps": 30, "duration": 4, "cues": cues})
    (bench.BASELINE / "audio").mkdir()
    with wave.open(str(bench.BASELINE / "audio/narration.wav"), "wb") as audio:
        audio.setparams((1, 2, 3000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 12000)

    design_path = tmp_path / "design.json"
    bench.write_json(design_path, {"layout_contract": {"bounds": [-6.3, 6.3, -2.5, 2.5], "required_labels": ["model"]}})
    bench.generate(name, "api-test", max_output_tokens=output_budget, cue_ids=cue_ids,
                   design_brief=design_path if with_design else None)

    request = sdk.return_value.chat.completions.create.call_args.kwargs
    settings = bench.read_json(bench.SETTINGS)
    sdk.assert_called_once_with(api_key="profile-test-secret", base_url=endpoint,
                               timeout=settings["profiles"][name].get("timeout", 600), max_retries=0)
    assert request["model"] == model
    expected_budget = settings["max_output_tokens"] if output_budget is None else output_budget
    assert request[token_param] == expected_budget
    assert {"max_tokens", "max_completion_tokens"}.intersection(request) == {token_param}
    assert request["extra_body"] == settings["profiles"][name]["extra_body"]
    assert "response_format" not in request
    out, context, session = bench.paths("api-test")
    snapshot = bench.read_json(context / "experiment.json")
    assert snapshot["design_brief"] == (bench.read_json(design_path) if with_design else None)
    if with_design:
        assert "GuardedBenchmarkScene" in request["messages"][0]["content"]
        assert bench.read_json(out / "design-brief.json") == snapshot["design_brief"]
    assert snapshot["profile"]["api_key_env"] == key_name
    if cue_ids:
        assert snapshot["excerpt"]["cue_ids"] == cue_ids
        assert snapshot["excerpt"]["baseline_audio_sha256"] == bench.sha256(bench.BASELINE / "audio/narration.wav")
        assert [c["id"] for c in snapshot["spec"]["cues"]] == cue_ids
        timeline = bench.read_json(out / "timeline.json")
        assert timeline["duration"] == 3
        assert [c["start"] for c in timeline["cues"]] == [0, 1, 2]
        assert timeline["cues"][0]["speech_start"] == pytest.approx(0.3)
        assert "audio_path" not in timeline["cues"][0]
        with wave.open(str(out / "narration.wav"), "rb") as audio:
            assert audio.getnframes() / audio.getframerate() == 3
    else:
        assert snapshot["excerpt"] is None
    for directory in (out, context, session):
        for path in directory.rglob("*.json"):
            assert "profile-test-secret" not in path.read_text()
    attempts = bench.read_json(session / "attempts.json")["attempts"]
    assert len(attempts) == 1
    assert attempts[0]["status"] == "generated"
    assert attempts[0]["max_output_tokens"] == expected_budget
    assert bench.read_json(out / "cost.json")["usage_complete"]
    assert not (context / "review.json").exists()
    assert not list(out.rglob("*.mp4"))
    feedback = session / "feedback.txt"
    feedback.write_text("Keep all selected cues.")
    changed_design = tmp_path / "changed-design.json"
    bench.write_json(changed_design, {"changed": True})
    with pytest.raises(ValueError, match="Design brief changed"):
        bench.generate(name, "api-test", feedback, design_brief=changed_design)
    with pytest.raises(ValueError, match="Cue selection changed"):
        bench.generate(name, "api-test", feedback, cue_ids=["graph"])
    assert sdk.return_value.chat.completions.create.call_count == 1
    bench.generate(name, "api-test", feedback)
    assert bench.read_json(context / "experiment.json") == snapshot
    changed_settings = tmp_path / "settings.json"
    bench.write_json(changed_settings, {**settings, "max_generations": 9, "max_requests": 9})
    monkeypatch.setattr(bench, "SETTINGS", changed_settings)
    with pytest.raises(ValueError, match="limit reached"):
        bench.generate(name, "api-test", feedback)
    approval = session / "repair-03.json"
    bench.write_json(approval, {
        "run_id": "api-test", "next_attempt": 3, "authorized_by": "user", "additional_requests": 1,
        "user_instruction": "One more repair", "max_output_tokens": 8192,
        "previous_attempts_sha256": bench.sha256(session / "attempts.json"),
        "experiment_sha256": bench.sha256(context / "experiment.json"), "feedback_sha256": bench.sha256(feedback),
    })
    before = bench.read_json(session / "attempts.json")["attempts"]
    bench.generate(name, "api-test", feedback, max_output_tokens=8192, repair_authorization=approval)
    after = bench.read_json(session / "attempts.json")["attempts"]
    assert after[:2] == before
    assert after[-1]["repair_authorization_sha256"] == bench.sha256(approval)
    assert sdk.return_value.chat.completions.create.call_count == 3
    with pytest.raises(ValueError, match="authorization"):
        bench.generate(name, "api-test", feedback, max_output_tokens=8192, repair_authorization=approval)
    with pytest.raises(ValueError, match="limit reached"):
        bench.generate(name, "api-test", feedback)
    assert sdk.return_value.chat.completions.create.call_count == 3
    bench.validate_inputs(after[-1], out, context)
    approval.write_text("{}")
    with pytest.raises(ValueError, match="repair authorization"):
        bench.validate_inputs(after[-1], out, context)


@pytest.mark.parametrize("field,value", [
    ("run_id", "other"), ("next_attempt", 4), ("authorized_by", "model"),
    ("additional_requests", 2), ("additional_requests", True),
    ("previous_attempts_sha256", "stale"), ("experiment_sha256", "stale"),
    ("feedback_sha256", "stale"), ("max_output_tokens", 100), ("user_instruction", ""),
])
def test_repair_authorization_rejects_mismatch(tmp_path, field, value):
    record, feedback, approval = tmp_path / "attempts.json", tmp_path / "feedback.txt", tmp_path / "approval.json"
    attempts = [{"status": "generation_failed"}, {"status": "generated"}]
    bench.write_json(record, {"attempts": attempts})
    bench.write_json(tmp_path / "experiment.json", {})
    feedback.write_text("Fix observed failure")
    data = {"run_id": "test", "next_attempt": 3, "authorized_by": "user", "additional_requests": 1,
            "user_instruction": "One more repair", "max_output_tokens": 8192,
            "previous_attempts_sha256": bench.sha256(record),
            "experiment_sha256": bench.sha256(tmp_path / "experiment.json"), "feedback_sha256": bench.sha256(feedback)}
    data[field] = value
    bench.write_json(approval, data)
    with pytest.raises(ValueError, match="authorization"):
        bench.repair_budget(approval, "test", attempts, {"max_generations": 2, "max_requests": 3},
                            record, tmp_path, feedback, 8192)


def test_extra_repair_requires_feedback_before_network_or_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setenv("MIMO_EZLOOK_API_KEY", "test-key")
    with pytest.raises(ValueError, match="requires feedback"):
        bench.generate("mimo-ezlook-fast", "example", repair_authorization=tmp_path / "approval.json")
    assert list(tmp_path.iterdir()) == []


def test_preflight_detects_literal_clock_reversal_and_multiple_fade_objects():
    code = """class GeneratedLesson(GuardedBenchmarkScene):
    def construct(self):
        with self.cue(0, 'test'):
            self.beat(0.6, FadeIn(a, b, shift=UP))
            self.beat(0.3)
"""
    issues = bench.preflight_code(code)
    assert any("monotonic" in issue for issue in issues)
    assert any("one object" in issue for issue in issues)
    assert bench.preflight_code(code.replace("0.6", "0.2").replace("FadeIn(a, b, shift=UP)", "FadeIn(a, shift=UP), FadeIn(b)")) == []


@pytest.mark.parametrize("budget", [0, -1, 65537, True, 1.5, "65536"])
def test_invalid_output_budget_rejected_before_writes(monkeypatch, tmp_path, budget):
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="max_output_tokens"):
        bench.generate("mimo-ezlook-pro", "api-test", max_output_tokens=budget)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name,key_name", [
    ("mimo-pro", "MIMO_API_KEY"), ("glm-flash", "ZAI_API_KEY"),
    ("mimo-ezlook-pro", "MIMO_EZLOOK_API_KEY"),
])
def test_new_api_profiles_require_their_own_key(name, key_name):
    settings = bench.read_json(bench.SETTINGS)
    with pytest.raises(ValueError, match=f"Missing {key_name}"):
        bench.resolve_profile(name, settings, {"OPENAI_API_KEY": "unrelated"})
    settings["profiles"][name]["base_url"] = settings["profiles"][name]["base_url"].replace("https:", "http:")
    with pytest.raises(ValueError, match="HTTPS"):
        bench.resolve_profile(name, settings, {key_name: "test-key"})


def test_gateway_cannot_borrow_official_key_or_claim_official_pricing():
    settings = bench.read_json(bench.SETTINGS)
    with pytest.raises(ValueError, match="Missing MIMO_EZLOOK_API_KEY"):
        bench.resolve_profile("mimo-ezlook-pro", settings, {"MIMO_API_KEY": "official-key"})
    profile, _ = bench.resolve_profile("mimo-ezlook-pro", settings, {"MIMO_EZLOOK_API_KEY": "gateway-key"})
    assert profile["pricing"] is None
    assert bench.cost_summary([{"prompt_tokens": 100, "completion_tokens": 200}], profile["pricing"])["estimated_model_cost"] is None
    settings["profiles"]["mimo-ezlook-pro"]["base_url"] = "https://other.example/v1"
    with pytest.raises(ValueError, match="destination mismatch"):
        bench.resolve_profile("mimo-ezlook-pro", settings, {"MIMO_EZLOOK_API_KEY": "gateway-key"})


def test_profile_does_not_send_key_to_different_host():
    settings = {"profiles": {"cloud": {"base_url_env": "URL", "api_key_env": "KEY", "model": "m", "allowed_hosts": ["expected.example"]}}}
    with pytest.raises(ValueError, match="destination mismatch"):
        bench.resolve_profile("cloud", settings, {"URL": "https://other.example/v1", "KEY": "secret"})


def test_profile_missing_key_does_not_borrow_openai_key():
    settings = {"profiles": {"local": {"base_url": "http://localhost:8000/v1", "api_key_env": "SCHOOL_KEY", "model": "qwen"}}}
    with pytest.raises(ValueError, match="Missing SCHOOL_KEY"):
        bench.resolve_profile("local", settings, {"OPENAI_API_KEY": "unrelated"})


def test_local_profile_override_and_no_key_in_snapshot():
    settings = {"profiles": {"local": {"base_url_env": "URL", "api_key_env": "KEY", "model": "qwen", "model_env": "MODEL"}}}
    profile, key = bench.resolve_profile("local", settings, {"URL": "http://127.0.0.1:8000/v1", "KEY": "local-secret", "MODEL": "qwen-fp8"})
    assert profile["model"] == "qwen-fp8"
    assert key == "local-secret"
    assert "local-secret" not in json.dumps(profile)


@pytest.mark.parametrize("run_id", ["../../escape", "x/y", "UpperCase", "", "a"*81])
def test_run_paths_are_bounded(run_id):
    with pytest.raises(ValueError):
        bench.paths(run_id)


def test_extract_code_only_removes_fences():
    source = "class GeneratedLesson(BenchmarkScene):\n    pass"
    assert bench.extract_code("```python\n"+source+"\n```") == source+"\n"
    assert bench.extract_code(source) == source+"\n"
    with pytest.raises(ValueError):
        bench.extract_code("```python\n"+source)


def test_preflight_blocks_io_and_clock_override():
    source = "import os\nclass GeneratedLesson(BenchmarkScene):\n    def beat(self):\n        open('secret')\n"
    issues = bench.preflight_code(source)
    assert "Import outside the render contract" in issues
    assert "Forbidden name: open" in issues
    assert "Must not override clock/support method: beat" in issues


def test_preflight_accepts_scoped_scene():
    assert bench.preflight_code("from manimlib import *\nfrom manimind.experiments.scene_support import BenchmarkScene\nclass GeneratedLesson(BenchmarkScene):\n    def construct(self):\n        pass\n") == []


def test_preflight_rejects_observed_support_api_errors():
    source = '''class GeneratedLesson(BenchmarkScene):
    def construct(self):
        self.cue(0, "title")
        self.beat(0.5, run_time=1)
        self.add_updater_to(group, updater)
'''
    assert bench.preflight_code(source) == sorted([
        "self.cue must be entered with a with block",
        "self.beat does not accept run_time",
        "Unknown Scene.add_updater_to; use mobject.add_updater",
    ])


def test_preflight_accepts_cue_context_and_native_updater():
    source = '''class GeneratedLesson(BenchmarkScene):
    def construct(self):
        with self.cue(0, "title"):
            group.add_updater(updater)
            self.beat(0.5, animation)
'''
    assert bench.preflight_code(source) == []


def test_cost_includes_failed_requests_when_usage_known():
    records = [{"prompt_tokens": 100, "completion_tokens": 200, "success": False},
               {"prompt_tokens": 200, "completion_tokens": 400, "success": True}]
    cost = bench.cost_summary(records, {"input_per_million": 6.5, "output_per_million": 27, "currency": "CNY"})
    assert cost["usage_complete"]
    assert cost["estimated_model_cost"] == pytest.approx(0.01815)


def test_unknown_usage_and_unknown_price_are_not_zero_cost():
    records = [{"prompt_tokens": 100, "completion_tokens": 200}, {"prompt_tokens": None, "completion_tokens": None}]
    result = bench.cost_summary(records, {"input_per_million": 1, "output_per_million": 2})
    assert result["estimated_model_cost"] is None
    assert not result["usage_complete"]
    assert bench.cost_summary(records[:1], None)["estimated_model_cost"] is None
    assert not bench.cost_summary([], None)["usage_complete"]


def test_execution_requires_explicit_review_ack():
    with pytest.raises(ValueError, match="Inspect source first"):
        bench.render("example", "h", False)


def test_scoped_render_environment_is_restored(monkeypatch, tmp_path):
    monkeypatch.setenv("MANIMIND_BENCHMARK_DIR", "original")
    with pytest.raises(RuntimeError):
        with bench.render_scope(tmp_path):
            assert bench.os.environ["MANIMIND_BENCHMARK_DIR"] == str(tmp_path)
            raise RuntimeError()
    assert bench.os.environ["MANIMIND_BENCHMARK_DIR"] == "original"


def test_assemble_rejects_missing_independent_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(bench, "latest", lambda _: (tmp_path, tmp_path, tmp_path, {"index": 1}, Path("scene.py")))
    monkeypatch.setattr(bench, "read_json", lambda path: {"run_id": "example", "attempt": 1, "video_path": "test.mp4", "frames": []} if path.name == "review-input.json" else {})
    monkeypatch.setattr(bench, "hashes", lambda *args: {})
    monkeypatch.setattr(bench, "requires_zoom", lambda _: False)
    with pytest.raises(ValueError, match="reviewer identity"):
        bench.assemble("example")


@pytest.mark.parametrize("selection", [[], ["half", "half"], ["unknown"], ["half", "graph"], ["graph", "approach"]])
def test_excerpt_rejects_invalid_or_noncontiguous_selection(selection):
    timeline = {"cues": [{"id": c} for c in ["graph", "half", "tenth", "approach"]]}
    with pytest.raises(ValueError):
        bench.select_excerpt({}, timeline, selection)


def test_narration_slice_is_lossless_and_rejects_out_of_bounds(tmp_path):
    source, target = tmp_path / "source.wav", tmp_path / "slice.wav"
    samples = struct.pack("<12000h", *range(12000))
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, 3000, 0, "NONE", "not compressed"))
        audio.writeframes(samples)
    bench.slice_narration(source, target, {"start_frame": 30, "end_frame": 90, "fps": 30})
    with wave.open(str(target), "rb") as audio:
        assert audio.getnframes() == 6000
        assert audio.readframes(6000) == samples[6000:18000]
    with pytest.raises(ValueError, match="outside baseline"):
        bench.slice_narration(source, target, {"start_frame": 30, "end_frame": 121, "fps": 30})


def test_zoom_requirement_comes_from_frozen_selected_cues(tmp_path):
    bench.write_json(tmp_path / "experiment.json", {"spec": {"cues": [{"id": "half"}]}})
    assert not bench.requires_zoom(tmp_path)
    bench.write_json(tmp_path / "experiment.json", {"spec": {"cues": [{"id": "zoom"}]}})
    assert bench.requires_zoom(tmp_path)


def test_excerpt_review_still_requires_all_applicable_checks():
    review = {"reviewer_role": "reviewer", "reviewer_id": "independent", "status": "approved", "blockers": [],
              "hashes": {}, "inspected_frames": ["sample.png"],
              "checks": {name: "pass" for name in ["mathematics", "visual_layout", "narrative", "cue_timing"]}}
    bench.validate_review(review, {}, require_zoom=False)
    with pytest.raises(ValueError, match="required checks"):
        bench.validate_review(review, {})
    review["checks"]["visual_layout"] = "fail"
    with pytest.raises(ValueError, match="required checks"):
        bench.validate_review(review, {}, require_zoom=False)


def test_settings_are_credential_free():
    settings = bench.read_json(bench.SETTINGS)
    assert settings["max_generations"] == 2
    for profile in settings["profiles"].values():
        assert "api_key" not in profile
        assert profile["api_key_env"].endswith("KEY")


def test_transport_rejection_does_not_hide_request_or_consume_source_repair():
    settings = {"max_requests": 3, "max_generations": 2}
    rejected = {"calls": [{"status_code": 429}]}
    generated = {"calls": [{"status_code": None, "success": True}]}
    bench.check_budget([rejected, generated], settings)
    with pytest.raises(ValueError):
        bench.check_budget([rejected, generated, generated], settings)
    with pytest.raises(ValueError):
        bench.check_budget([generated, generated], settings)
    with pytest.raises(ValueError):
        bench.check_budget([rejected, rejected, rejected], settings)


def test_timeout_and_inflight_attempt_count_toward_generation_budget():
    with pytest.raises(ValueError):
        bench.check_budget([{"calls": [{"error_type": "APITimeoutError"}]}, {"status": "requested"}], {"max_requests": 3, "max_generations": 2})


def test_unsettled_attempt_prevents_complete_cost_claim():
    records = bench.attempt_records([{"status": "requested"}, {"calls": [{"prompt_tokens": 10, "completion_tokens": 20}]}])
    result = bench.cost_summary(records, {"input_per_million": 1, "output_per_million": 2})
    assert result["requests"] == 2
    assert not result["usage_complete"]
    assert result["estimated_model_cost"] is None
    assert result["estimated_known_usage_cost"] == pytest.approx(0.00005)


def test_cli_lock_excludes_same_run_and_releases_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(bench, "paths", lambda _: (tmp_path, tmp_path, tmp_path))
    with pytest.raises(RuntimeError):
        with bench.exclusive_run("example"):
            with pytest.raises(FileExistsError):
                with bench.exclusive_run("example"):
                    pytest.fail("Second owner entered")
            raise RuntimeError("test")
    assert not (tmp_path / "command.lock").exists()


def test_frozen_inputs_and_original_reply_are_checked(monkeypatch, tmp_path):
    monkeypatch.setattr(bench, "SUPPORT", tmp_path / "support.py")
    files = {"support": "support.py", "timeline": "timeline.json", "audio": "narration.wav", "config": "manimgl.yml", "prompt": "prompt-01.json", "experiment": "experiment.json"}
    for name in files.values():
        (tmp_path / name).write_text("original")
    source = tmp_path / "scene.py"
    source.write_text("class GeneratedLesson:\n    pass\n")
    reply = tmp_path / "reply-01.txt"
    reply.write_text(source.read_text())
    entry = {"status": "generated", "index": 1, "code_path": str(source), "code_sha256": bench.sha256(source), "prompt_path": str(tmp_path / files["prompt"])}
    entry.update({f"{key}_sha256": bench.sha256(tmp_path / value) for key, value in files.items()})
    bench.validate_inputs(entry, tmp_path, tmp_path)
    reply.write_text("class GeneratedLesson:\n    changed = True\n")
    with pytest.raises(ValueError, match="original model response"):
        bench.validate_inputs(entry, tmp_path, tmp_path)
    reply.write_text(source.read_text())
    (tmp_path / "experiment.json").write_text("changed")
    with pytest.raises(ValueError, match="experiment"):
        bench.validate_inputs(entry, tmp_path, tmp_path)


def test_failed_render_is_saved_then_raises(monkeypatch, tmp_path):
    source = tmp_path / "scene.py"
    source.write_text("class GeneratedLesson:\n    pass\n")
    entry = {"index": 1, "code_sha256": bench.sha256(source)}
    monkeypatch.setattr(bench, "latest", lambda _: (tmp_path, tmp_path, tmp_path, entry, source))
    result = SimpleNamespace(code_path=str(source), success=False, error="render_failed")
    result.to_dict = lambda: {"success": result.success, "error": result.error}
    monkeypatch.setattr(bench, "render_manim_scene", lambda **_: result)
    with pytest.raises(RuntimeError, match="Render failed"):
        bench.render("example", "h", True)
    assert not bench.read_json(tmp_path / "render.json")["success"]


def test_assembly_rejects_evidence_from_another_attempt(monkeypatch, tmp_path):
    monkeypatch.setattr(bench, "latest", lambda _: (tmp_path, tmp_path, tmp_path, {"index": 2}, Path("scene.py")))
    monkeypatch.setattr(bench, "read_json", lambda _: {"run_id": "example", "attempt": 1})
    with pytest.raises(ValueError, match="another run or attempt"):
        bench.assemble("example")
