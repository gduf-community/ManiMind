from manimind.experiments.subscription_quota import summarize


def test_same_window_delta_is_account_wide():
    result = summarize([{"used_percent": 10, "resets_at": 100}, {"used_percent": 12, "resets_at": 100}])
    assert result["account_interval_percentage_points"] == 2
    assert not result["single_job_attribution"]


def test_reset_prevents_misleading_subtraction():
    for last in [{"used_percent": 2, "resets_at": 200}, {"used_percent": 2, "resets_at": 100}]:
        result = summarize([{"used_percent": 90, "resets_at": 100}, last])
        assert result["reset_or_window_change_observed"]
        assert result["account_interval_percentage_points"] is None


def test_missing_samples_are_not_zero_usage():
    result = summarize([{"error": "unavailable"}])
    assert result["latest_used_percent"] is None
    assert result["account_interval_percentage_points"] is None
