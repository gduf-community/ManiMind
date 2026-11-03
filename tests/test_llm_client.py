"""LLM 客户端单元测试。"""

from __future__ import annotations

import json
import os
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, RateLimitError
from openai.types.chat import ChatCompletion

# Capture explicit opt-in before importing the client's optional dotenv loader.
_LIVE_TESTS_REQUESTED = os.getenv("MANIMIND_RUN_LIVE_TESTS") == "1"

from manimind.llm.client import LlmClient, LlmTruncationError


@pytest.fixture(autouse=True)
def block_non_live_network(request, monkeypatch):
    """A mistaken SDK call in a unit test must not reach a paid endpoint."""
    if request.node.name == "test_real_api_call":
        return

    def fail_network(*args, **kwargs):
        pytest.fail("Network access is forbidden in unit tests")

    monkeypatch.setattr(socket.socket, "connect", fail_network)
    monkeypatch.setattr(socket, "create_connection", fail_network)


def _make_response(content="测试响应", *, usage=None, finish_reason="stop"):
    return ChatCompletion(
        id="mock-completion",
        created=0,
        object="chat.completion",
        model="served-model-version",
        choices=[{
            "index": 0,
            "finish_reason": finish_reason,
            "message": {"role": "assistant", "content": content},
        }],
        usage=usage,
    )


def _invoke(client, method):
    if method == "chat":
        return client.chat("private-system-prompt", "private-user-message")
    return client.chat_structured(
        "private-system-prompt", "private-user-message", {"type": "object"}
    )


def _make_status_error(status_code, error_type=APIStatusError):
    response = MagicMock(status_code=status_code)
    return error_type("private-error-body", response=response, body={"private": "body"})


@pytest.fixture
def mock_sdk():
    with patch("manimind.llm.client.OpenAI") as constructor:
        yield constructor


@pytest.fixture(params=["chat", "chat_structured"])
def method(request):
    return request.param


@pytest.fixture
def usage():
    return {
        "prompt_tokens": 123,
        "completion_tokens": 45,
        "total_tokens": 168,
        "prompt_tokens_details": {"cached_tokens": 80},
        "completion_tokens_details": {"reasoning_tokens": 12},
    }


# ============================================================================
# Fixture: 模拟 OpenAI 响应
# ============================================================================


@pytest.fixture
def mock_openai_response():
    """创建一个模拟的 OpenAI 响应对象。"""
    return _make_response()


@pytest.fixture
def mock_openai_json_response():
    """创建一个模拟的 OpenAI JSON 响应对象。"""
    return _make_response(json.dumps({"key": "value", "number": 42}))


def _make_connection_error(message: str = "Connection failed"):
    """创建一个 APIConnectionError，兼容新版 openai 库的 request 参数。"""
    from openai import APIConnectionError

    mock_request = MagicMock()
    return APIConnectionError(message=message, request=mock_request)


# ============================================================================
# 初始化测试
# ============================================================================


def test_llm_client_init_with_env(mock_sdk):
    """测试从环境变量初始化 LLM 客户端。"""
    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test-key", "MANIMIND_MODEL": "gpt-4o"}, clear=True
    ):
        client = LlmClient()
        assert client.api_key == "test-key"
        assert client.model == "gpt-4o"  # 默认模型
        assert client.timeout == 180
        assert client.json_mode is True
        assert client.extra_body is None
        assert client.call_records == []
        mock_sdk.assert_called_once_with(api_key="test-key", timeout=180, max_retries=0)


def test_llm_client_init_with_custom_params(mock_sdk):
    """测试使用自定义参数初始化 LLM 客户端。"""
    client = LlmClient(
        api_key="custom-key",
        base_url="https://custom.api.com",
        model="gpt-3.5-turbo",
        max_retries=5,
        timeout=12.5,
        json_mode=False,
        extra_body={"enable_thinking": False},
    )
    assert client.api_key == "custom-key"
    assert client.base_url == "https://custom.api.com"
    assert client.model == "gpt-3.5-turbo"
    assert client.max_retries == 5
    assert client.json_mode is False
    mock_sdk.assert_called_once_with(
        api_key="custom-key", base_url="https://custom.api.com", timeout=12.5, max_retries=0
    )


def test_llm_client_init_without_api_key():
    """测试缺少 API Key 时抛出异常。"""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
            LlmClient()


@pytest.mark.parametrize("param", ["max_tokens", "max_completion_tokens"])
def test_token_budget_uses_selected_field(mock_sdk, method, param):
    create = mock_sdk.return_value.chat.completions.create
    create.return_value = _make_response('{"ok": true}')
    client = LlmClient(api_key="test-key", token_limit_param=param)
    _invoke(client, method)
    kwargs = create.call_args.kwargs
    assert kwargs[param] == (4096 if method == "chat" else 8192)
    assert {"max_tokens", "max_completion_tokens"}.intersection(kwargs) == {param}


@pytest.mark.parametrize("param", ["max_output_tokens", "", None, 1, []])
def test_invalid_token_budget_field_fails_before_sdk(mock_sdk, param):
    with pytest.raises(ValueError, match="token_limit_param"):
        LlmClient(api_key="test-key", token_limit_param=param)
    mock_sdk.assert_not_called()


# ============================================================================
# chat 方法测试
# ============================================================================


def test_chat_success(mock_openai_response):
    """测试普通聊天成功。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_openai_response
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key")
        result = client.chat(system_prompt="系统提示", user_message="用户消息")

        assert result == "测试响应"
        mock_instance.chat.completions.create.assert_called_once()


def test_chat_with_temperature_and_max_tokens(mock_openai_response):
    """测试聊天时使用自定义温度和最大 token。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_openai_response
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key")
        result = client.chat(
            system_prompt="系统提示",
            user_message="用户消息",
            temperature=0.7,
            max_tokens=2048,
        )

        call_kwargs = mock_instance.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 2048


def test_chat_preserves_multimodal_content_blocks(mock_sdk):
    mock_sdk.return_value.chat.completions.create.return_value = _make_response()
    client = LlmClient(api_key="test-key")
    blocks = [{"type": "text", "text": "Inspect frame"},
              {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,dGVzdA=="}}]
    client.chat("system", blocks)
    assert mock_sdk.return_value.chat.completions.create.call_args.kwargs["messages"][1]["content"] == blocks


def test_chat_retry_on_connection_error(mock_openai_response):
    """测试连接错误时的重试机制。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        # 前两次失败，第三次成功
        mock_instance.chat.completions.create.side_effect = [
            _make_connection_error("Connection failed"),
            _make_connection_error("Connection failed"),
            mock_openai_response,
        ]
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key", max_retries=3, retry_delay=0.01)
        result = client.chat(system_prompt="系统提示", user_message="用户消息")

        assert result == "测试响应"
        assert mock_instance.chat.completions.create.call_count == 3


def test_chat_empty_response():
    """测试空响应时抛出异常。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = _make_response(None)
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key")

        with pytest.raises(RuntimeError, match="empty response"):
            client.chat(system_prompt="系统提示", user_message="用户消息")


# ============================================================================
# chat_structured 方法测试
# ============================================================================


def test_chat_structured_success(mock_openai_json_response):
    """测试结构化输出成功。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_openai_json_response
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key")
        schema = {"type": "object", "properties": {"key": {"type": "string"}}}
        result = client.chat_structured(
            system_prompt="系统提示",
            user_message="用户消息",
            output_schema=schema,
        )

        assert result == {"key": "value", "number": 42}
        assert isinstance(result, dict)


def test_chat_structured_invalid_json():
    """测试无效 JSON 响应时抛出异常。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = _make_response("这不是 JSON")
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key")
        schema = {"type": "object"}

        with pytest.raises(RuntimeError, match="Failed to parse"):
            client.chat_structured(
                system_prompt="系统提示",
                user_message="用户消息",
                output_schema=schema,
            )


def test_chat_structured_non_dict_response():
    """测试非字典类型的 JSON 响应时抛出异常。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = _make_response("[1, 2, 3]")
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key")
        schema = {"type": "object"}

        with pytest.raises(RuntimeError, match="Expected dict"):
            client.chat_structured(
                system_prompt="系统提示",
                user_message="用户消息",
                output_schema=schema,
            )


def test_chat_structured_uses_low_temperature(mock_openai_json_response):
    """测试结构化输出使用低温度。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_openai_json_response
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key")
        schema = {"type": "object"}
        client.chat_structured(
            system_prompt="系统提示",
            user_message="用户消息",
            output_schema=schema,
        )

        call_kwargs = mock_instance.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.1


def test_chat_structured_uses_json_object_format(mock_openai_json_response):
    """测试结构化输出使用 json_object 格式。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.return_value = mock_openai_json_response
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key")
        schema = {"type": "object"}
        client.chat_structured(
            system_prompt="系统提示",
            user_message="用户消息",
            output_schema=schema,
        )

        call_kwargs = mock_instance.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}


# ============================================================================
# 重试机制测试
# ============================================================================


def test_max_retries_exhausted():
    """测试重试次数耗尽时抛出异常。"""
    with patch("manimind.llm.client.OpenAI") as MockOpenAI:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create.side_effect = _make_connection_error("Always fails")
        MockOpenAI.return_value = mock_instance

        client = LlmClient(api_key="test-key", max_retries=2, retry_delay=0.01)

        with pytest.raises(RuntimeError, match="failed after 2 retries"):
            client.chat(system_prompt="系统提示", user_message="用户消息")


# ============================================================================
# 请求记录、兼容参数与重试边界
# ============================================================================


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), -float("inf"), True, None, "30"])
def test_invalid_timeout(timeout, mock_sdk):
    with pytest.raises(ValueError, match="timeout"):
        LlmClient(api_key="test-key", timeout=timeout)
    mock_sdk.assert_not_called()


@pytest.mark.parametrize("max_retries", [0, -1, 1.5, True, None, "3"])
def test_invalid_max_retries(max_retries, mock_sdk):
    with pytest.raises(ValueError, match="max_retries"):
        LlmClient(api_key="test-key", max_retries=max_retries)
    mock_sdk.assert_not_called()


def test_records_real_sdk_usage(method, usage, mock_sdk):
    mock_sdk.return_value.chat.completions.create.return_value = _make_response("{}", usage=usage)
    client = LlmClient(api_key="test-key", model="requested-model")
    with patch("manimind.llm.client.time.perf_counter", side_effect=[10.0, 12.5]):
        _invoke(client, method)

    assert client.call_records == [{
        "requested_model": "requested-model",
        "response_model": "served-model-version",
        "prompt_tokens": 123,
        "completion_tokens": 45,
        "total_tokens": 168,
        "cached_tokens": 80,
        "reasoning_tokens": 12,
        "elapsed_seconds": 2.5,
        "attempt": 1,
        "finish_reason": "stop",
        "success": True,
        "error_type": None,
        "status_code": None,
    }]


@pytest.mark.parametrize("omit_usage", [False, True])
def test_missing_usage_is_unknown_not_zero(method, omit_usage, mock_sdk):
    response = _make_response("{}")
    if omit_usage:
        response = SimpleNamespace(model=response.model, choices=response.choices)
    mock_sdk.return_value.chat.completions.create.return_value = response
    client = LlmClient(api_key="test-key")
    _invoke(client, method)

    record = client.call_records[0]
    assert record["success"] is True
    assert all(record[name] is None for name in ("prompt_tokens", "completion_tokens", "total_tokens"))
    assert record.get("cached_tokens") is None
    assert record.get("reasoning_tokens") is None


@pytest.mark.parametrize("include_details", [False, True])
def test_zero_usage_is_preserved(method, include_details, mock_sdk):
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if include_details:
        usage.update({
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0},
        })
    mock_sdk.return_value.chat.completions.create.return_value = _make_response("{}", usage=usage)
    client = LlmClient(api_key="test-key")
    _invoke(client, method)
    record = client.call_records[0]

    assert all(record[name] == 0 for name in ("prompt_tokens", "completion_tokens", "total_tokens"))
    for name in ("cached_tokens", "reasoning_tokens"):
        assert record.get(name) == (0 if include_details else None)


def test_partial_usage_does_not_invent_totals(method, mock_sdk):
    response = _make_response("{}")
    mock_sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
        choices=response.choices, usage=SimpleNamespace(prompt_tokens=10)
    )
    client = LlmClient(api_key="test-key")
    _invoke(client, method)
    record = client.call_records[0]
    assert record["response_model"] is None
    assert record["prompt_tokens"] == 10
    assert record["completion_tokens"] is None
    assert record["total_tokens"] is None


@pytest.mark.parametrize("content", ['{"partial":', "{}", None])
def test_truncation_raises_without_retry_and_keeps_usage(method, content, usage, mock_sdk):
    create = mock_sdk.return_value.chat.completions.create
    create.return_value = _make_response(content, usage=usage, finish_reason="length")
    client = LlmClient(api_key="test-key")
    with patch("manimind.llm.client.time.sleep") as sleep:
        with pytest.raises(LlmTruncationError, match="truncated.*finish_reason=length"):
            _invoke(client, method)

    create.assert_called_once()
    sleep.assert_not_called()
    assert len(client.call_records) == 1
    record = client.call_records[0]
    assert record["success"] is False
    assert record["error_type"] == "LlmTruncationError"
    assert record["finish_reason"] == "length"
    assert record["prompt_tokens"] == 123
    assert record["completion_tokens"] == 45
    assert record["total_tokens"] == 168
    assert record["cached_tokens"] == 80
    assert record["reasoning_tokens"] == 12


@pytest.mark.parametrize("json_mode", [False, True])
def test_json_mode_only_controls_structured_response_format(method, json_mode, mock_sdk):
    create = mock_sdk.return_value.chat.completions.create
    create.return_value = _make_response("{}")
    client = LlmClient(api_key="test-key", json_mode=json_mode)
    _invoke(client, method)
    kwargs = create.call_args.kwargs
    if method == "chat_structured" and json_mode:
        assert kwargs["response_format"] == {"type": "json_object"}
    else:
        assert "response_format" not in kwargs
    if method == "chat_structured":
        system, user = kwargs["messages"]
        assert "valid JSON only" in system["content"]
        assert json.dumps({"type": "object"}, indent=2) in system["content"]
        assert "ONLY a valid JSON object" in user["content"]
    else:
        assert kwargs["messages"] == [
            {"role": "system", "content": "private-system-prompt"},
            {"role": "user", "content": "private-user-message"},
        ]


@pytest.mark.parametrize("extra_body", [None, {}, {"enable_thinking": False, "options": {"seed": 7}}])
def test_extra_body_forwarding(method, extra_body, mock_sdk):
    create = mock_sdk.return_value.chat.completions.create
    create.return_value = _make_response("{}")
    original = json.dumps(extra_body)
    client = LlmClient(api_key="test-key", extra_body=extra_body)
    _invoke(client, method)
    kwargs = create.call_args.kwargs
    if extra_body is None:
        assert "extra_body" not in kwargs
    else:
        assert kwargs["extra_body"] == extra_body
    assert json.dumps(extra_body) == original


def test_structured_positional_signature_is_compatible(mock_sdk):
    create = mock_sdk.return_value.chat.completions.create
    create.return_value = _make_response("{}")
    client = LlmClient("test-key", "https://example.invalid/v1", "model", 1, 0)
    assert client.chat_structured("system", "user", {"type": "object"}, 0.2, 1234) == {}
    assert create.call_args.kwargs["temperature"] == 0.2
    assert create.call_args.kwargs["max_tokens"] == 1234


def test_all_attempts_recorded_before_backoff(method, usage, mock_sdk):
    create = mock_sdk.return_value.chat.completions.create
    create.side_effect = [
        _make_connection_error("private-error-body"),
        _make_status_error(429, RateLimitError),
        _make_status_error(503),
        _make_response("{}", usage=usage),
    ]
    client = LlmClient(api_key="private-key", max_retries=4, retry_delay=0.5)

    def check_record_before_sleep(delay):
        assert len(client.call_records) == create.call_count
        assert client.call_records[-1]["elapsed_seconds"] == create.call_count

    with (
        patch("manimind.llm.client.time.sleep", side_effect=check_record_before_sleep) as sleep,
        patch("manimind.llm.client.time.perf_counter", side_effect=[0, 1, 10, 12, 30, 33, 70, 74]),
    ):
        _invoke(client, method)

    assert create.call_count == 4
    assert sleep.call_args_list == [call(0.5), call(1.0), call(2.0)]
    assert [r["attempt"] for r in client.call_records] == [1, 2, 3, 4]
    assert [r["elapsed_seconds"] for r in client.call_records] == [1, 2, 3, 4]
    assert [r["success"] for r in client.call_records] == [False, False, False, True]
    assert [r["status_code"] for r in client.call_records] == [None, 429, 503, None]
    assert [r["error_type"] for r in client.call_records] == [
        "APIConnectionError", "RateLimitError", "APIStatusError", None,
    ]
    for record in client.call_records[:-1]:
        assert all(record[name] is None for name in (
            "response_model", "prompt_tokens", "completion_tokens", "total_tokens", "finish_reason"
        ))


@pytest.mark.parametrize("error_kind", ["connection", "timeout", "rate_limit", 429, 500, 503, 599])
@pytest.mark.parametrize("max_retries", [1, 3])
def test_retry_exhaustion_is_bounded(method, error_kind, max_retries, mock_sdk):
    if error_kind == "connection":
        error = _make_connection_error("private-error-body")
    elif error_kind == "timeout":
        error = APITimeoutError(request=MagicMock())
    elif error_kind == "rate_limit":
        error = _make_status_error(429, RateLimitError)
    else:
        error = _make_status_error(error_kind)
    create = mock_sdk.return_value.chat.completions.create
    create.side_effect = error
    client = LlmClient(api_key="test-key", max_retries=max_retries)
    with patch("manimind.llm.client.time.sleep") as sleep:
        with pytest.raises(RuntimeError, match=f"failed after {max_retries} retries") as exc:
            _invoke(client, method)

    assert exc.value.__cause__ is error
    assert create.call_count == max_retries
    assert sleep.call_count == max_retries - 1
    assert len(client.call_records) == max_retries
    assert [r["attempt"] for r in client.call_records] == list(range(1, max_retries + 1))
    assert all(r["success"] is False for r in client.call_records)
    assert all(r["error_type"] == type(error).__name__ for r in client.call_records)


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 408, 409, 422, 499, 600])
def test_other_status_errors_are_not_retried(method, status_code, mock_sdk):
    create = mock_sdk.return_value.chat.completions.create
    create.side_effect = _make_status_error(status_code)
    client = LlmClient(api_key="test-key")
    with patch("manimind.llm.client.time.sleep") as sleep:
        with pytest.raises(RuntimeError, match="LLM API error"):
            _invoke(client, method)
    create.assert_called_once()
    sleep.assert_not_called()
    assert len(client.call_records) == 1
    assert client.call_records[0]["success"] is False
    assert client.call_records[0]["status_code"] == status_code


@pytest.mark.parametrize("api_error", [False, True])
def test_other_errors_are_recorded_without_retry(method, api_error, mock_sdk):
    error = (
        APIError("private-error-body", request=MagicMock(), body=None)
        if api_error else ValueError("private-error-body")
    )
    create = mock_sdk.return_value.chat.completions.create
    create.side_effect = error
    client = LlmClient(api_key="test-key")
    with patch("manimind.llm.client.time.sleep") as sleep:
        with pytest.raises(RuntimeError if api_error else ValueError):
            _invoke(client, method)
    create.assert_called_once()
    sleep.assert_not_called()
    assert len(client.call_records) == 1
    assert client.call_records[0]["error_type"] == type(error).__name__
    assert client.call_records[0]["success"] is False


@pytest.mark.parametrize(("method", "content", "message"), [
    ("chat", None, "empty response"),
    ("chat_structured", None, "empty response"),
    ("chat_structured", "private-response-body", "Failed to parse"),
    ("chat_structured", "[1, 2, 3]", "Expected dict"),
])
def test_response_validation_failure_keeps_usage(method, content, message, usage, mock_sdk):
    create = mock_sdk.return_value.chat.completions.create
    create.return_value = _make_response(content, usage=usage)
    client = LlmClient(api_key="test-key")
    with pytest.raises(RuntimeError, match=message):
        _invoke(client, method)
    create.assert_called_once()
    assert len(client.call_records) == 1
    record = client.call_records[0]
    assert record["success"] is False
    assert record["error_type"] == "RuntimeError"
    assert record["finish_reason"] == "stop"
    assert record["total_tokens"] == 168


def test_records_are_metadata_only(method, mock_sdk):
    create = mock_sdk.return_value.chat.completions.create
    create.side_effect = [
        _make_status_error(503),
        _make_response('{"private-response-body": "private-key"}'),
    ]
    client = LlmClient(api_key="private-key", retry_delay=0)
    _invoke(client, method)
    encoded = json.dumps(client.call_records)
    for secret in ("private-key", "private-system-prompt", "private-user-message",
                   "private-response-body", "private-error-body"):
        assert secret not in encoded
    allowed = {
        "requested_model", "response_model", "prompt_tokens", "completion_tokens",
        "total_tokens", "cached_tokens", "reasoning_tokens", "elapsed_seconds", "attempt",
        "finish_reason", "success", "error_type", "status_code",
    }
    assert all(set(record) <= allowed for record in client.call_records)


def test_drain_clears_only_this_clients_pending_records(mock_sdk):
    mock_sdk.return_value.chat.completions.create.return_value = _make_response("{}")
    client = LlmClient(api_key="test-key")
    other = LlmClient(api_key="test-key")
    assert client.drain_call_records() == []
    client.chat("system", "user")
    client.chat_structured("system", "user", {"type": "object"})
    other.chat("system", "user")
    records = client.drain_call_records()
    assert [r["attempt"] for r in records] == [1, 1]
    assert client.call_records == []
    assert client.drain_call_records() == []
    assert len(other.call_records) == 1
    client.chat("system", "user")
    assert len(client.call_records) == 1
    assert len(records) == 2


# ============================================================================
# 集成测试（必须显式开启且有 API Key）
# ============================================================================


@pytest.mark.skipif(
    not (_LIVE_TESTS_REQUESTED and os.getenv("OPENAI_API_KEY")),
    reason="Requires explicit MANIMIND_RUN_LIVE_TESTS=1 and OPENAI_API_KEY",
)
def test_real_api_call():
    """仅在显式启用且存在 API Key 时执行付费测试。"""
    if os.getenv("MANIMIND_RUN_LIVE_TESTS") != "1" or not os.getenv("OPENAI_API_KEY"):
        pytest.skip("Live API tests require explicit opt-in and an API key")
    client = LlmClient()
    result = client.chat(
        system_prompt="你是一个助手。",
        user_message="请回复'测试成功'。",
        temperature=0.1,
        max_tokens=50,
    )
    assert isinstance(result, str)
    assert len(result) > 0
