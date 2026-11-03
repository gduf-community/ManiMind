"""LLM 客户端 — OpenAI 兼容接口封装。

支持通过 .env 配置 OPENAI_API_KEY / OPENAI_BASE_URL / MANIMIND_MODEL。
提供普通聊天和结构化输出两种模式。
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any

# 自动加载项目根目录的 .env 文件
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    if os.environ.get("MANIMIND_DISABLE_DOTENV") != "1" and _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

try:
    from openai import OpenAI, APIError, APIConnectionError, APIStatusError, RateLimitError
except ImportError:
    raise ImportError(
        "openai package is required. Install with: pip install openai"
    )


class LlmTruncationError(RuntimeError):
    """The model exhausted its output budget; the response is incomplete."""


class LlmClient:
    """基于 .env 配置的 LLM 客户端。

    环境变量:
        - OPENAI_API_KEY: API 密钥（必需）
        - OPENAI_BASE_URL: API 基础 URL（可选，默认使用 OpenAI 官方）
        - MANIMIND_MODEL: 模型名称（可选，默认 gpt-4o）

    用法:
        client = LlmClient()
        response = client.chat(system_prompt="...", user_message="...")
        structured = client.chat_structured(..., output_schema={...})

    call_records 是实例级临时状态，由每次请求写入，供调用方统计用量与失败。
    仅保留元数据，不持久化；drain_call_records() 消费并清空，实例销毁后失效。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 180,
        json_mode: bool = True,
        extra_body: dict | None = None,
        token_limit_param: str = "max_tokens",
    ):
        """初始化 LLM 客户端。

        Args:
            api_key: OpenAI API Key，默认从 .env 读取 OPENAI_API_KEY
            base_url: API 基础 URL，默认从 .env 读取 OPENAI_BASE_URL
            model: 模型名称，默认从 .env 读取 MANIMIND_MODEL， fallback 到 gpt-4o
            max_retries: 最大请求尝试次数（含首次请求，至少为 1）
            retry_delay: 重试间隔（秒）
            timeout: 单次请求超时（有限正数，秒）
            json_mode: 结构化输出是否发送 response_format
            extra_body: 转发给兼容服务的额外请求体参数
            token_limit_param: 输出预算字段，支持 max_tokens 或 max_completion_tokens
        """
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a finite positive number")
        if (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or max_retries < 1
        ):
            raise ValueError("max_retries must be an integer >= 1")
        if token_limit_param not in ("max_tokens", "max_completion_tokens"):
            raise ValueError("token_limit_param must be max_tokens or max_completion_tokens")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model or os.getenv("MANIMIND_MODEL", "gpt-4o")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.json_mode = json_mode
        self.extra_body = extra_body
        self.token_limit_param = token_limit_param
        self.call_records: list[dict] = []

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Please configure it in .env file "
                "or pass it explicitly to LlmClient()."
            )

        # 初始化 OpenAI 客户端
        client_kwargs = {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": 0,
        }
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self._client = OpenAI(**client_kwargs)

    def drain_call_records(self) -> list[dict]:
        """返回自上次消费以来的请求元数据，并清空实例缓冲区。"""
        records = self.call_records.copy()
        self.call_records.clear()
        return records

    def chat(
        self,
        system_prompt: str,
        user_message: str | list[dict[str, Any]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """发送普通聊天请求。

        Args:
            system_prompt: 系统提示词
            user_message: 用户文字或兼容服务支持的文字/图片内容块；图片能力须实际验证
            temperature: 温度参数（0.0-2.0），越低越确定
            max_tokens: 最大生成 token 数

        Returns:
            LLM 返回的文本响应

        Raises:
            RuntimeError: 当 LLM 调用失败且重试耗尽时
        """
        return self._request(
            system_prompt, user_message, temperature, max_tokens, structured=False
        )

    def chat_structured(
        self,
        system_prompt: str,
        user_message: str,
        output_schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        """发送结构化输出请求（强制 JSON 格式）。

        使用 OpenAI 的 response_format 或 prompt engineering 确保输出为合法 JSON。

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            output_schema: JSON Schema 定义期望的输出结构

        Returns:
            解析后的字典对象

        Raises:
            RuntimeError: 当 LLM 调用失败或返回无效 JSON 时
        """
        # 在系统提示中强调 JSON 输出要求
        enhanced_system_prompt = (
            f"{system_prompt}\n\n"
            "IMPORTANT: You MUST respond with valid JSON only. "
            "Do not include any explanatory text before or after the JSON. "
            "The JSON must conform to this schema:\n"
            f"{json.dumps(output_schema, ensure_ascii=False, indent=2)}"
        )

        enhanced_user_message = (
            f"{user_message}\n\n"
            "Please respond with ONLY a valid JSON object. No markdown, no explanation."
        )

        return self._request(
            enhanced_system_prompt,
            enhanced_user_message,
            temperature,
            max_tokens,
            structured=True,
        )

    def _request(
        self,
        system_prompt: str,
        user_message: str | list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        *,
        structured: bool,
    ) -> str | dict[str, Any]:
        request_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            self.token_limit_param: max_tokens,
        }
        if structured and self.json_mode:
            request_kwargs["response_format"] = {"type": "json_object"}
        if self.extra_body is not None:
            request_kwargs["extra_body"] = self.extra_body

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            record = {
                "requested_model": self.model,
                "response_model": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "elapsed_seconds": None,
                "attempt": attempt,
                "finish_reason": None,
                "success": False,
                "error_type": None,
                "status_code": None,
            }
            started = time.perf_counter()
            try:
                response = self._client.chat.completions.create(**request_kwargs)
                record["response_model"] = getattr(response, "model", None)
                usage = getattr(response, "usage", None)
                if usage is not None:
                    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        record[name] = getattr(usage, name, None)
                    for detail_name, token_name in (
                        ("prompt_tokens_details", "cached_tokens"),
                        ("completion_tokens_details", "reasoning_tokens"),
                    ):
                        value = getattr(getattr(usage, detail_name, None), token_name, None)
                        if value is not None:
                            record[token_name] = value

                choice = response.choices[0]
                record["finish_reason"] = choice.finish_reason
                if choice.finish_reason == "length":
                    raise LlmTruncationError(
                        "LLM response truncated (finish_reason=length)"
                    )

                content = choice.message.content
                if content is None:
                    raise RuntimeError("LLM returned empty response")

                result = content
                if structured:
                    try:
                        result = json.loads(content)
                    except (json.JSONDecodeError, ValueError) as e:
                        raise RuntimeError("Failed to parse LLM response as JSON") from e
                    if not isinstance(result, dict):
                        raise RuntimeError(f"Expected dict, got {type(result).__name__}")

            except Exception as e:
                record["error_type"] = type(e).__name__
                record["status_code"] = getattr(e, "status_code", None)
                retryable = isinstance(e, (APIConnectionError, RateLimitError)) or (
                    isinstance(e, APIStatusError)
                    and (e.status_code == 429 or 500 <= e.status_code < 600)
                )
                if not retryable:
                    if isinstance(e, APIError):
                        raise RuntimeError(f"LLM API error: {type(e).__name__}") from e
                    raise
                last_error = e
            else:
                record["success"] = True
                return result
            finally:
                record["elapsed_seconds"] = time.perf_counter() - started
                self.call_records.append(record)

            # Backoff is not part of the actual request's elapsed time.
            if attempt < self.max_retries:
                time.sleep(self.retry_delay * (2 ** (attempt - 1)))

        raise RuntimeError(
            f"{'Structured LLM' if structured else 'LLM'} call failed after "
            f"{self.max_retries} retries. Last error type: {type(last_error).__name__}"
        ) from last_error
