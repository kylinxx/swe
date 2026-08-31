from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
from typing import Any


def estimate_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_message_tokens(message: dict[str, Any]) -> int:
    token_count = 8
    token_count += estimate_token_count(str(message.get("role", "")))
    token_count += estimate_token_count(str(message.get("content", "")))
    tool_calls = message.get("tool_calls")
    if tool_calls:
        token_count += estimate_token_count(json.dumps(tool_calls, ensure_ascii=False))
    if message.get("tool_call_id"):
        token_count += estimate_token_count(str(message["tool_call_id"]))
    return token_count


def clip_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars]
    return f"{clipped}\n\n[输出已截断，原始长度 {len(text)} 字符]"


@dataclass
class ConversationHistory:
    max_context_tokens: int
    messages: list[dict[str, Any]] = field(default_factory=list)

    def append(self, message: dict[str, Any]) -> None:
        self.messages.append(deepcopy(message))

    def as_messages(self) -> list[dict[str, Any]]:
        return deepcopy(self.messages)

    def build_for_model(self) -> list[dict[str, Any]]:
        if not self.messages:
            return []

        prefix: list[dict[str, Any]] = []
        index = 0
        while index < len(self.messages) and self.messages[index].get("role") in {"system", "developer"}:
            prefix.append(deepcopy(self.messages[index]))
            index += 1

        body = self.messages[index:]
        total_budget = self.max_context_tokens
        selected: list[dict[str, Any]] = []
        used_tokens = sum(estimate_message_tokens(message) for message in prefix)

        for message in reversed(body):
            message_tokens = estimate_message_tokens(message)
            if selected and used_tokens + message_tokens > total_budget:
                break
            selected.append(deepcopy(message))
            used_tokens += message_tokens

        if not selected and body:
            selected.append(deepcopy(body[-1]))

        return prefix + list(reversed(selected))

