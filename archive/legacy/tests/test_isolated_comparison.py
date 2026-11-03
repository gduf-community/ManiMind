from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from manimind.experiments import isolated_comparison as comparison


def fixture():
    config = comparison.pilot.read_json(comparison.CONFIG)
    plan = comparison.pilot.read_json(comparison.ROOT / "configs/component-foundation.json")
    plan["id"] = "lesson"
    plan["provenance"] = {"kind": "model_output", "author": "candidate", "interventions": []}
    plan["shots"] += deepcopy(plan["shots"])
    for i, shot in enumerate(plan["shots"]):
        shot["id"] = f"shot-{i}"
        shot["duration"] = 18
    narration = [{"shot_id": s["id"], "text": "观察图中的参数变化，比较初始和最终的状态，思考图形与数值之间有什么关系，再用自己的话解释。"}
                 for s in plan["shots"]]
    return {"plan": plan, "narration": narration}, config


def test_contract_accepts_complete_lesson():
    obj, config = fixture()
    result, report = comparison.validate_answer(json.dumps(obj), config)
    assert result == obj
    assert report["duration"] == 108
    assert report["total_frames"] == 3240


@pytest.mark.parametrize("mutation", [
    lambda obj: obj.update(extra="bad"),
    lambda obj: obj["plan"].update(id="other"),
    lambda obj: obj["plan"]["provenance"].update(author="model-name"),
    lambda obj: obj["plan"]["shots"][0].update(duration=17),
    lambda obj: obj["narration"].pop(),
    lambda obj: obj["narration"][0].update(shot_id="wrong"),
    lambda obj: obj["narration"][0].update(text="too short"),
    lambda obj: obj["narration"][0].update(text="x" * 66),
])
def test_contract_rejects_mutations(mutation):
    obj, config = fixture()
    mutation(obj)
    with pytest.raises(ValueError):
        comparison.validate_answer(json.dumps(obj), config)


def test_duplicate_keys_not_silently_normalized():
    _, config = fixture()
    with pytest.raises(ValueError, match="Duplicate"):
        comparison.validate_answer('{"plan":1,"plan":2}', config)


def test_unknown_usage_is_not_free():
    _, config = fixture()
    result = comparison.cost_estimate({}, config["candidates"]["kimi"]["pricing"])
    assert result["upper"] is None


def test_cost_bounds_include_cache_write_uncertainty():
    _, config = fixture()
    result = comparison.cost_estimate(
        {"prompt_tokens": 10000, "completion_tokens": 20000,
         "prompt_tokens_details": {"cached_tokens": 5000}},
        config["candidates"]["kimi"]["pricing"])
    assert result["lower"] == 2.11
    assert result["upper"] == 2.21


def test_deepseek_peak_offpeak_bounds():
    _, config = fixture()
    result = comparison.cost_estimate(
        {"prompt_tokens": 10000, "completion_tokens": 20000,
         "prompt_cache_hit_tokens": 5000},
        config["candidates"]["deepseek"]["pricing"])
    assert result["lower"] == .0851
    assert result["upper"] == .1702


def test_known_zero_cache_writes_not_invented():
    _, config = fixture()
    result = comparison.cost_estimate(
        {"input_tokens": 10000, "output_tokens": 20000,
         "cached_input_tokens": 5000, "cache_write_input_tokens": 0},
        config["candidates"]["codex"]["pricing"])
    assert result["lower"] == result["upper"] == 1.055


def test_source_change_invalidates_frozen_protocol(tmp_path, monkeypatch):
    monkeypatch.setattr(comparison, "locations", lambda suite: (tmp_path, tmp_path, tmp_path))
    comparison.pilot.write_json(tmp_path / "protocol.json", {"source_hashes": {"old": "hash"}})
    monkeypatch.setattr(comparison, "sources", lambda: {"new": "hash"})
    with pytest.raises(ValueError, match="Frozen workflow changed"):
        comparison.load("example")


def test_total_deadline_interrupts_continuous_work():
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="wall-clock"):
        with comparison.deadline(.05):
            for _ in range(100):
                time.sleep(.01)
    assert time.monotonic() - started < .5


def test_report_preserves_interrupted_unknown_cost(tmp_path, monkeypatch):
    _, config = fixture()
    monkeypatch.setattr(comparison, "load", lambda suite: {
        "config": config, "packet_sha256": "packet"})
    monkeypatch.setattr(comparison, "locations", lambda suite: (tmp_path, tmp_path, tmp_path))
    comparison.pilot.write_json(tmp_path / "codex-r1/attempt-1/record.json", {
        "candidate": "codex", "repetition": 1, "attempt": 1, "status": "started"})
    comparison.report("example")
    report = comparison.pilot.read_json(tmp_path / "generation-report.json")
    assert report["candidate_summary"]["codex"]["unknown_cost_requests"] == 1
    assert report["candidate_summary"]["codex"]["unknown_duration_requests"] == 1


def test_non_primary_sample_cannot_enter_media(tmp_path, monkeypatch):
    _, config = fixture()
    monkeypatch.setattr(comparison, "load", lambda suite: {"config": config})
    monkeypatch.setattr(comparison, "locations", lambda suite: (tmp_path, tmp_path, tmp_path))
    with pytest.raises(ValueError, match="primary"):
        comparison.verify_selected_run(tmp_path / "codex-r2", "iso26-any")


@pytest.mark.skipif(os.environ.get("RUN_CODEX_TRANSPORT_TEST") != "1",
                    reason="Opt-in local CLI transport fault test, never calls a model")
def test_codex_500_is_not_implicitly_retried(tmp_path):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(self.path)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"intentional local test failure"}}')

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    home = tmp_path / "empty-auth-home"
    home.mkdir()
    command = [shutil.which("codex"), "exec", "--ignore-user-config", "--ephemeral",
               "--skip-git-repo-check", "--sandbox", "read-only", "--json",
               "-m", "gpt-6-astra", "-C", str(tmp_path)]
    options = {
        "model_provider": "fault-test",
        "model_providers.fault-test.name": "Local retry fault test",
        "model_providers.fault-test.base_url": f"http://127.0.0.1:{server.server_port}/v1",
        "model_providers.fault-test.requires_openai_auth": False,
        "model_providers.fault-test.request_max_retries": 0,
        "model_providers.fault-test.stream_max_retries": 0,
        "model_providers.fault-test.supports_websockets": False,
        "project_doc_max_bytes": 0, "features.unbounded_connection_retries": False,
        "features.memories": False, "features.plugins": False,
        "features.apps": False, "features.shell_tool": False,
        "features.system_proxy_fallback": False,
    }
    for key, value in options.items():
        command += ["-c", f"{key}={json.dumps(value)}"]
    command += ["Return OK"]
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "CODEX_HOME": str(home),
           "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
    try:
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=45)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert result.returncode != 0
    assert requests == ["/v1/responses"], (requests, result.stdout, result.stderr)
