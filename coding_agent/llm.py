from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, request


class LLMClientError(RuntimeError):
    pass


@dataclass
class OpenAICompatibleClient:
    api_key: str
    base_url: str
    timeout_seconds: int = 60

    def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temperature,
        }
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            hint = ""
            if exc.code == 404:
                hint = (
                    "\n提示：请检查 `base_url` 是否正确。"
                    "OpenAI 兼容接口通常使用 `https://api.openai.com/v1`，"
                    "DeepSeek 的 OpenAI 兼容基地址通常使用 `https://api.deepseek.com`。"
                )
            elif exc.code == 401:
                hint = "\n提示：请检查 `api_key` 是否有效，或是否已绑定到对应平台。"
            raise LLMClientError(f"LLM 请求失败：{exc.code} {exc.reason}\n{error_body}{hint}") from exc
        except error.URLError as exc:
            raise LLMClientError(
                f"无法连接到模型服务：{exc.reason}\n提示：请检查网络、`base_url` 和代理配置。"
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"模型返回了无效 JSON：{raw[:500]}") from exc
