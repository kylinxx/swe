from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import time
import traceback
from typing import Any, Callable

from .artifacts import ArtifactWriter, RunArtifacts
from .config import AgentConfig
from .hooks import AgentEvent, HookBus
from .llm import LLMClientError, OpenAICompatibleClient
from .memory import ConversationHistory
from .prompts import build_planning_prompt, build_system_prompt
from .tools import ToolResult, WorkspaceToolbox
from .validation import SchemaValidationError, validate_json_schema


PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["goal", "summary", "steps"],
    "properties": {
        "goal": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "minLength": 1},
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "task", "reason"],
                "properties": {
                    "id": {"type": "integer", "minimum": 1},
                    "task": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                },
            },
        },
        "notes": {
            "type": "array",
            "default": [],
            "items": {"type": "string", "minLength": 1},
        },
    },
}


@dataclass
class PlanStep:
    id: int
    task: str
    reason: str


@dataclass
class ExecutionPlan:
    goal: str
    summary: str
    steps: list[PlanStep]
    notes: list[str]


@dataclass
class AgentRunResult:
    final_answer: str
    steps: int
    history: list[dict[str, Any]]
    plan: ExecutionPlan | None = None
    artifacts: RunArtifacts | None = None
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


class CodingAgent:
    def __init__(
        self,
        config: AgentConfig,
        *,
        llm_client: OpenAICompatibleClient,
        toolbox: WorkspaceToolbox,
    ) -> None:
        self.config = config
        self.llm_client = llm_client
        self.toolbox = toolbox
        self.hooks = HookBus()
        self.history = ConversationHistory(max_context_tokens=config.max_context_tokens)
        self.tool_events: list[dict[str, Any]] = []
        self.event_log: list[dict[str, Any]] = []
        self.artifact_writer = ArtifactWriter(config.workspace_root, config.report_dir) if config.record_runs else None
        self.history.append(
            {
                "role": "system",
                "content": build_system_prompt(config.workspace_root, plan_mode=config.plan_mode),
            }
        )

    def on(self, event_name: str, handler) -> None:
        self.hooks.on(event_name, handler)

    def run(
        self,
        task: str,
        *,
        stream_callback: Callable[[str], None] | None = None,
    ) -> AgentRunResult:
        self._record_event(self.hooks.emit("session_start", task=task, workspace_root=str(self.config.workspace_root)))
        self.history.append({"role": "user", "content": task})
        plan: ExecutionPlan | None = None

        try:
            plan = self._generate_plan(task) if self.config.plan_mode else None
            if plan is not None:
                self.history.append({"role": "system", "content": self._format_plan(plan)})
                self._record_event(self.hooks.emit("plan_created", plan=plan))

            for step in range(1, self.config.max_steps + 1):
                before_call = self.hooks.emit(
                    "before_model_call",
                    step=step,
                    model=self.config.model,
                    temperature=self.config.temperature,
                    messages=self.history.build_for_model(),
                )
                self._record_event(before_call)
                if before_call.canceled:
                    raise RuntimeError("模型调用被 hook 取消。")

                response = self.llm_client.chat_completion(
                    model=self.config.model,
                    messages=before_call.data.get("messages", self.history.build_for_model()),
                    tools=self.toolbox.tool_schemas(),
                    temperature=before_call.data.get("temperature", self.config.temperature),
                    stream=stream_callback is not None,
                    on_delta=stream_callback,
                )
                self._record_event(self.hooks.emit("after_model_call", step=step, response=response))
                assistant_message = self._extract_assistant_message(response)
                self.history.append(assistant_message)

                tool_calls = assistant_message.get("tool_calls") or []
                if tool_calls:
                    self._handle_tool_calls(tool_calls)
                    continue

                final_text = str(assistant_message.get("content") or "").strip()
                if final_text:
                    self._record_event(
                        self.hooks.emit(
                            "session_end",
                            status="success",
                            final_answer=final_text,
                            steps=step,
                        )
                    )
                    artifacts = self._write_run_artifacts(task, plan, final_text, step)
                    return AgentRunResult(
                        final_text,
                        step,
                        self.history.as_messages(),
                        plan=plan,
                        artifacts=artifacts,
                        tool_events=list(self.tool_events),
                        events=list(self.event_log),
                    )

            raise RuntimeError(f"超过最大循环步数 {self.config.max_steps}，仍未完成任务。")
        except Exception as exc:
            self._record_event(self.hooks.emit("error", error=str(exc), exception_type=type(exc).__name__))
            self._record_event(
                self.hooks.emit(
                    "session_end",
                    status="failed",
                    error=str(exc),
                    exception_type=type(exc).__name__,
                )
            )
            self._write_failure_artifact(task, plan, exc)
            raise

    def _generate_plan(self, task: str) -> ExecutionPlan:
        max_attempts = max(1, int(self.config.json_retry_attempts))
        base_prompt = build_planning_prompt(self.config.workspace_root, task)
        messages: list[dict[str, Any]] = [{"role": "system", "content": base_prompt}]
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            response = self.llm_client.chat_completion(
                model=self.config.model,
                messages=messages,
                tools=[],
                temperature=0.1,
            )
            raw_text = self._extract_text_content(response)
            try:
                plan_data = self._parse_plan_json(raw_text)
                validated = validate_json_schema(plan_data, PLAN_SCHEMA, path="plan")
                steps = [
                    PlanStep(
                        id=int(item["id"]),
                        task=str(item["task"]).strip(),
                        reason=str(item["reason"]).strip(),
                    )
                    for item in validated["steps"]
                ]
                return ExecutionPlan(
                    goal=str(validated["goal"]).strip(),
                    summary=str(validated["summary"]).strip(),
                    steps=steps,
                    notes=[str(item).strip() for item in validated.get("notes", []) if str(item).strip()],
                )
            except (LLMClientError, SchemaValidationError, KeyError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                messages = [
                    {"role": "system", "content": base_prompt},
                    {
                        "role": "system",
                        "content": (
                            f"上一轮规划输出未通过校验：{exc}。"
                            "请只输出符合 JSON schema 的纯 JSON，不要添加解释。"
                        ),
                    },
                ]

        raise LLMClientError(f"规划器未返回有效 JSON：{last_error}") from last_error

    def _extract_assistant_message(self, response: dict[str, Any]) -> dict[str, Any]:
        message = self._extract_message(response)
        content = message.get("content")
        if isinstance(content, list):
            message["content"] = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        elif content is None:
            message["content"] = ""
        return message

    def _extract_text_content(self, response: dict[str, Any]) -> str:
        message = self._extract_message(response)
        content = message.get("content")
        if isinstance(content, list):
            return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        if content is None:
            return ""
        return str(content)

    def _extract_message(self, response: dict[str, Any]) -> dict[str, Any]:
        try:
            choice = response["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"模型响应结构不正确：{response}") from exc
        return message

    def _handle_tool_calls(self, tool_calls: list[dict[str, Any]]) -> None:
        for tool_call in tool_calls:
            name = tool_call.get("function", {}).get("name", "")
            raw_arguments = tool_call.get("function", {}).get("arguments", "{}")
            tool_call_id = tool_call.get("id", "")
            arguments = self._parse_tool_arguments(raw_arguments)
            before_tool = self.hooks.emit("before_tool_call", name=name, arguments=arguments, tool_call_id=tool_call_id)
            self._record_event(before_tool)
            if before_tool.canceled:
                result = ToolResult(False, f"工具调用被 hook 取消：{name}", {"tool": name, "canceled": True, "retryable": False})
                attempts = 0
            else:
                arguments = before_tool.data.get("arguments", arguments)
                result, attempts = self._execute_tool_with_retry(name, arguments, tool_call_id)

            self._record_event(
                self.hooks.emit(
                    "after_tool_call",
                    name=name,
                    arguments=arguments,
                    tool_call_id=tool_call_id,
                    result=result,
                    attempts=attempts,
                )
            )
            self.tool_events.append(
                {
                    "name": name,
                    "attempts": attempts,
                    "retry_count": max(0, attempts - 1),
                    "success": result.success,
                    "summary": result.content.splitlines()[0] if result.content else "",
                    "content": result.content,
                    "metadata": result.metadata,
                }
            )
            self.history.append(
                {
                    "role": "tool",
                    "name": name,
                    "tool_call_id": tool_call_id,
                    "content": f"[{'success' if result.success else 'error'}] {result.content}",
                }
            )

    def _execute_tool_with_retry(self, name: str, arguments: dict[str, Any], tool_call_id: str) -> tuple[ToolResult, int]:
        max_attempts = max(1, int(self.config.tool_retry_attempts))
        last_result: ToolResult | None = None
        for attempt in range(1, max_attempts + 1):
            result = self._execute_tool(name, arguments)
            last_result = result
            if result.success or not result.metadata.get("retryable") or attempt >= max_attempts:
                return result, attempt
            self._record_event(
                self.hooks.emit(
                    "tool_retry",
                    name=name,
                    tool_call_id=tool_call_id,
                    attempt=attempt,
                    result=result,
                )
            )
            time.sleep(min(0.5, 0.15 * attempt))

        assert last_result is not None
        return last_result, max_attempts

    def _parse_tool_arguments(self, raw_arguments: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_arguments) if raw_arguments else {}
        except json.JSONDecodeError:
            return {"_raw": raw_arguments, "_error": "工具参数不是有效 JSON"}

        if isinstance(parsed, dict):
            return parsed
        return {"_raw": raw_arguments, "_error": "工具参数必须是 JSON 对象"}

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if arguments.get("_error"):
            return ToolResult(
                False,
                f"工具参数解析失败：{arguments['_error']}；原始参数：{arguments.get('_raw', '')}",
                {"tool": name, "error_type": "InvalidToolArguments", "retryable": False},
            )
        return self.toolbox.call(name, arguments)

    def _parse_plan_json(self, raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if not text:
            raise LLMClientError("规划器没有返回任何内容。")

        fenced = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()
        else:
            first_brace = text.find("{")
            last_brace = text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                text = text[first_brace : last_brace + 1]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"规划器输出不是有效 JSON：{raw_text}") from exc
        if not isinstance(parsed, dict):
            raise LLMClientError(f"规划器输出结构不正确：{raw_text}")
        return parsed

    def _format_plan(self, plan: ExecutionPlan) -> str:
        lines = [
            "已生成执行计划：",
            f"目标：{plan.goal}",
        ]
        if plan.summary:
            lines.append(f"路线：{plan.summary}")
        if plan.notes:
            lines.append("注意事项：")
            lines.extend([f"- {note}" for note in plan.notes])
        lines.append("步骤：")
        lines.extend([f"{step.id}. {step.task}（原因：{step.reason}）" for step in plan.steps])
        return "\n".join(lines)

    def _write_run_artifacts(
        self,
        task: str,
        plan: ExecutionPlan | None,
        final_answer: str,
        steps: int,
    ) -> RunArtifacts | None:
        if self.artifact_writer is None:
            return None
        return self.artifact_writer.write_report(
            task=task,
            plan=plan,
            final_answer=final_answer,
            steps=steps,
            history=self.history.as_messages(),
            tool_events=self.tool_events,
            event_log=self.event_log,
        )

    def _write_failure_artifact(
        self,
        task: str,
        plan: ExecutionPlan | None,
        exc: Exception,
    ) -> RunArtifacts | None:
        if self.artifact_writer is None:
            return None
        error_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return self.artifact_writer.write_report(
            task=task,
            plan=plan,
            final_answer=str(exc),
            steps=len(self.tool_events),
            history=self.history.as_messages(),
            tool_events=self.tool_events,
            event_log=self.event_log,
            status="failed",
            error=error_text,
        )

    def _record_event(self, event: AgentEvent) -> None:
        self.event_log.append(event.to_dict())
