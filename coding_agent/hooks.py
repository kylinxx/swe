from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentEvent:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    canceled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "data": self.data,
            "canceled": self.canceled,
        }


HookHandler = Callable[[AgentEvent], Any]


class HookBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[HookHandler]] = {}

    def on(self, event_name: str, handler: HookHandler) -> None:
        self._listeners.setdefault(event_name, []).append(handler)

    def emit(self, event_name: str, **data: Any) -> AgentEvent:
        event = AgentEvent(event_name, dict(data))
        for handler in self._listeners.get(event_name, []):
            result = handler(event)
            if isinstance(result, dict):
                event.data.update(result)
            if result is False:
                event.canceled = True
            if event.canceled:
                break
        return event

