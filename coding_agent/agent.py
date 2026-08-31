from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
import re
import traceback
from typing import Any

from .artifacts import ArtifactWriter, RunArtifacts
from .config import AgentConfig
from .hooks import AgentEvent, HookBus
from .llm import LLMClientError, OpenAICompatibleClient
from .memory import ConversationHistory
from .prompts import build_planning_prompt, build_system_prompt
from .tools import ToolResult, WorkspaceToolbox


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

    def run(self, task: str) -> AgentRunResult:
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
                        events=list(self.event_log),
                    )

            raise RuntimeError(f"超过最大循环步数 {self.config.max_steps}，未能完成任务。")
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
        response = self.llm_client.chat_completion(
            model=self.config.model,
            messages=[
                {
                    "role": "system",
                    "content": build_planning_prompt(self.config.workspace_root, task),
                }
            ],
            tools=[],
            temperature=0.1,
        )
        raw_text = self._extract_text_content(response)
        plan_data = self._parse_plan_json(raw_text)
        steps = [
            PlanStep(
                id=int(item.get("id", index + 1)),
                task=str(item.get("task", "")).strip(),
                reason=str(item.get("reason", "")).strip(),
            )
            for index, item in enumerate(plan_data.get("steps", []))
            if isinstance(item, dict)
        ]
        if not steps:
            raise LLMClientError(f"规划器未返回有效步骤：{raw_text}")
        return ExecutionPlan(
            goal=str(plan_data.get("goal", "")).strip() or "未命名目标",
            summary=str(plan_data.get("summary", "")).strip(),
            steps=steps,
            notes=[str(item).strip() for item in plan_data.get("notes", []) if str(item).strip()],
        )

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
                result = ToolResult(False, f"工具调用被 hook 取消：{name}", {"tool": name, "canceled": True})
            else:
                arguments = before_tool.data.get("arguments", arguments)
                result = self._execute_tool(name, arguments)
            self._record_event(
                self.hooks.emit(
                    "after_tool_call",
                    name=name,
                    arguments=arguments,
                    tool_call_id=tool_call_id,
                    result=result,
                )
            )
            self.tool_events.append(
                {
                    "name": name,
                    "success": result.success,
                    "summary": result.content.splitlines()[0] if result.content else "",
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

    def _parse_tool_arguments(self, raw_arguments: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_arguments) if raw_arguments else {}
            if isinstance(parsed, dict):
                return parsed
            return {"_raw": parsed}
        except json.JSONDecodeError:
            return {"_raw": raw_arguments, "_error": "工具参数不是有效 JSON"}

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if arguments.get("_error"):
            return ToolResult(
                False,
                f"工具参数解析失败：{arguments['_error']}，原始参数：{arguments.get('_raw', '')}",
                {"tool": name},
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
