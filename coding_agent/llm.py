from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable
from urllib import error, request


class LLMClientError(RuntimeError):
    pass


@dataclass
class OpenAICompatibleClient:
    api_key: str
    base_url: str
    timeout_seconds: int = 60
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5

    def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.2,
        stream: bool = False,
        on_delta: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temperature,
        }
        if stream or on_delta is not None:
            payload["stream"] = True
            return self._chat_completion_stream(payload, on_delta=on_delta)
        return self._chat_completion_json(payload)

    def _chat_completion_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        http_request = request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw)
            except error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (attempt + 1))
                    last_error = exc
                    continue
                raise self._format_http_error(exc, error_body) from exc
            except error.URLError as exc:
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (attempt + 1))
                    last_error = exc
                    continue
                raise LLMClientError(
                    f"Unable to connect to model service: {exc.reason}\n"
                    "Check your network, proxy settings, and base_url."
                ) from exc
            except json.JSONDecodeError as exc:
                raise LLMClientError("Model returned invalid JSON.") from exc

        assert last_error is not None
        raise LLMClientError(f"Failed to call LLM after retries: {last_error}") from last_error

    def _chat_completion_stream(
        self,
        payload: dict[str, Any],
        *,
        on_delta: Callable[[str], None] | None,
    ) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        http_request = request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                return self._consume_stream(response, on_delta=on_delta)
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise self._format_http_error(exc, error_body) from exc
        except error.URLError as exc:
            raise LLMClientError(
                f"Unable to connect to model service: {exc.reason}\n"
                "Check your network, proxy settings, and base_url."
            ) from exc

    def _consume_stream(self, response, *, on_delta: Callable[[str], None] | None) -> dict[str, Any]:
        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        last_event: dict[str, Any] | None = None

        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue

            data = line[len("data:") :].strip()
            if data == "[DONE]":
                break

            try:
                event = json.loads(data)
            except json.JSONDecodeError as exc:
                raise LLMClientError(f"Invalid stream chunk: {data}") from exc
            last_event = event
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}

            content_piece = delta.get("content")
            if isinstance(content_piece, str) and content_piece:
                content_parts.append(content_piece)
                if on_delta is not None:
                    on_delta(content_piece)

            for tool_delta in delta.get("tool_calls") or []:
                index = int(tool_delta.get("index", len(tool_calls)))
                bucket = tool_calls.setdefault(index, {"function": {"arguments": ""}})
                if "id" in tool_delta:
                    bucket["id"] = tool_delta["id"]
                if "type" in tool_delta:
                    bucket["type"] = tool_delta["type"]
                function_delta = tool_delta.get("function") or {}
                bucket_function = bucket.setdefault("function", {"arguments": ""})
                if "name" in function_delta and function_delta["name"] is not None:
                    bucket_function["name"] = function_delta["name"]
                if "arguments" in function_delta and function_delta["arguments"] is not None:
                    bucket_function["arguments"] = bucket_function.get("arguments", "") + str(function_delta["arguments"])

        message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(content_parts),
        }
        ordered_tool_calls = [tool_calls[index] for index in sorted(tool_calls)]
        if ordered_tool_calls:
            message["tool_calls"] = ordered_tool_calls

        finish_reason = None
        if last_event:
            last_choices = last_event.get("choices") or []
            if last_choices:
                finish_reason = last_choices[0].get("finish_reason")

        response_payload: dict[str, Any] = {
            "choices": [
                {
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ]
        }
        if last_event:
            for key in ("id", "model", "created", "usage"):
                if key in last_event:
                    response_payload[key] = last_event[key]
        return response_payload

    def _format_http_error(self, exc: error.HTTPError, error_body: str) -> LLMClientError:
        hint = ""
        if exc.code == 404:
            hint = (
                "\nTip: check whether base_url is correct. "
                "OpenAI-compatible endpoints usually use `https://api.openai.com/v1`, "
                "and DeepSeek usually uses `https://api.deepseek.com`."
            )
        elif exc.code == 401:
            hint = "\nTip: check whether your api_key is valid and has the right access."
        return LLMClientError(f"LLM request failed: {exc.code} {exc.reason}\n{error_body}{hint}")
