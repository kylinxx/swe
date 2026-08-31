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


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


@dataclass
class ConversationHistory:
    max_context_tokens: int
    messages: list[dict[str, Any]] = field(default_factory=list)

    def append(self, message: dict[str, Any]) -> None:
        self.messages.append(deepcopy(message))

    def as_messages(self) -> list[dict[str, Any]]:
        return deepcopy(self.messages)

    def compact_to_budget(self, *, keep_recent_messages: int = 8) -> bool:
        if not self.messages:
            return False
        if sum(estimate_message_tokens(message) for message in self.messages) <= self.max_context_tokens:
            return False

        prefix = self._leading_system_messages()
        body = self.messages[len(prefix) :]
        if not body:
            return False

        for recent_count in range(min(keep_recent_messages, len(body)), 0, -1):
            dropped = body[:-recent_count]
            recent = body[-recent_count:]
            candidate = list(prefix)
            summary_text = self._build_summary(dropped)
            if summary_text:
                candidate.append({"role": "system", "content": summary_text})
            candidate.extend(deepcopy(recent))
            if sum(estimate_message_tokens(message) for message in candidate) <= self.max_context_tokens:
                self.messages = candidate
                return True

        recent = [deepcopy(body[-1])]
        candidate = list(prefix)
        summary_text = self._build_summary(body[:-1])
        if summary_text:
            candidate.append({"role": "system", "content": summary_text})
        candidate.extend(recent)
        self.messages = candidate
        return True

    def build_for_model(self) -> list[dict[str, Any]]:
        if not self.messages:
            return []

        self.compact_to_budget()

        prefix = self._leading_system_messages()
        index = len(prefix)

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

    def _leading_system_messages(self) -> list[dict[str, Any]]:
        prefix: list[dict[str, Any]] = []
        for message in self.messages:
            if message.get("role") not in {"system", "developer"}:
                break
            prefix.append(deepcopy(message))
        return prefix

    def _build_summary(self, messages: list[dict[str, Any]]) -> str:
        if not messages:
            return ""

        bullets: list[str] = []
        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            if isinstance(content, list):
                content_text = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
            else:
                content_text = str(content)

            snippet = _first_nonempty_line(content_text)
            if not snippet:
                continue

            if role == "user":
                bullets.append(f"- 用户：{clip_text(snippet, 140)}")
            elif role == "assistant":
                bullets.append(f"- 助手：{clip_text(snippet, 140)}")
            elif role == "tool":
                name = str(message.get("name") or "tool")
                bullets.append(f"- 工具 {name}：{clip_text(snippet, 140)}")

            if len(bullets) >= 8:
                break

        if not bullets:
            return ""

        summary = ["【上下文压缩摘要】", f"已压缩 {len(messages)} 条历史消息："]
        summary.extend(bullets)
        return clip_text("\n".join(summary), 2000)
