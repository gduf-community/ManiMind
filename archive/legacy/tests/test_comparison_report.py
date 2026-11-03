import pytest

from manimind.experiments.comparison_report import call_metrics, review_consistency, verify_sources, pilot


def test_pass_with_blockers_is_not_silently_normalized():
    answer = {"verdict": "acceptable_with_advisories", "findings": [{"severity": "blocker"}]}
    assert review_consistency(answer) == {"valid_shape": True, "pass_with_blockers": True}
    assert answer["verdict"] == "acceptable_with_advisories"


def test_valid_review_is_not_a_delivery_approval():
    assert review_consistency({"verdict": "blocked", "findings": [{"severity": "blocker"}]}) == {
        "valid_shape": True, "pass_with_blockers": False}
    assert not review_consistency({"verdict": "approved", "findings": []})["valid_shape"]
    assert not review_consistency({"verdict": "blocked", "findings": ["bad"]})["valid_shape"]


def test_cost_and_latency_preserve_unknown_usage():
    calls = [{"prompt_tokens": 10, "completion_tokens": 20, "elapsed_seconds": 2, "response_model": "rolling"},
             {"prompt_tokens": None, "completion_tokens": None, "elapsed_seconds": 4, "response_model": None}]
    result = call_metrics(calls, {"input_per_million": 2, "output_per_million": 8})
    assert not result["usage_complete"] and result["estimated_model_cost"] is None
    assert result["request_latency_seconds"] == {"min": 2, "max": 4, "mean": 3}
    assert result["response_models"] == ["rolling"]
    assert call_metrics([], None)["request_latency_seconds"] is None


@pytest.mark.parametrize("form", ["mapping", "entries"])
def test_source_manifest_validates_both_explicit_formats(tmp_path, form):
    path = tmp_path / "evidence.json"
    path.write_text("{}")
    digest = pilot.sha256(path)
    manifest = {str(path): digest} if form == "mapping" else [{"kind": "answer", "path": str(path), "sha256": digest}]
    verify_sources(manifest)
    path.write_text("changed")
    with pytest.raises(ValueError, match="Stale"):
        verify_sources(manifest)


@pytest.mark.parametrize("manifest", [{}, [], ["path"], [{"path": "missing_hash"}], "path"])
def test_invalid_source_manifest_is_not_silently_ignored(manifest):
    with pytest.raises(ValueError):
        verify_sources(manifest)
