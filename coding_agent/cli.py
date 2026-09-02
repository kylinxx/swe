from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent import CodingAgent
from .config import (
    AgentConfig,
    default_llm_settings,
    load_dotenv_if_present,
    normalize_base_url,
    resolve_llm_runtime_config,
    resolve_workspace_root,
)
from .llm import LLMClientError, OpenAICompatibleClient
from .tools import WorkspaceToolbox


def build_argument_parser() -> argparse.ArgumentParser:
    default_provider = os.getenv("MODEL_PROVIDER", "").strip().lower()
    if default_provider not in {"openai", "deepseek"}:
        default_provider = None
    default_base_url, default_model = default_llm_settings(default_provider)

    parser = argparse.ArgumentParser(description="Run the coding agent on a local programming task.")
    parser.add_argument("task", nargs="*", help="要交给智能体的编程任务。")
    parser.add_argument("--cwd", default=".", help="工作目录，默认为当前目录。")
    parser.add_argument("--model", default=default_model, help="模型名称。")
    parser.add_argument("--base-url", default=default_base_url, help="OpenAI 兼容接口地址。")
    parser.add_argument("--max-steps", type=int, default=12, help="最大推理循环次数。")
    parser.add_argument("--max-context-tokens", type=int, default=12000, help="上下文预算（近似 token）。")
    parser.add_argument("--temperature", type=float, default=0.2, help="采样温度。")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="单次请求与命令超时。")
    parser.add_argument("--plan", action="store_true", help="先生成执行计划，再进入执行循环。")
    parser.add_argument("--no-record", action="store_true", help="不保存运行报告。")
    parser.add_argument("--report-dir", default=".coding-agent/runs", help="运行报告输出目录。")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式输出。")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv_if_present(Path(__file__).resolve().parents[1] / ".env")
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    task = " ".join(args.task).strip()
    if not task:
        task = sys.stdin.read().strip()
    if not task:
        parser.error("请提供一个编程任务，或者通过标准输入传入任务说明。")

    try:
        llm_runtime = resolve_llm_runtime_config()
    except ValueError as exc:
        parser.error(str(exc))

    workspace_root = resolve_workspace_root(Path(args.cwd))
    config = AgentConfig(
        api_key=llm_runtime.api_key,
        model=args.model,
        base_url=normalize_base_url(args.base_url, llm_runtime.provider),
        workspace_root=workspace_root,
        plan_mode=bool(args.plan),
        record_runs=not bool(args.no_record),
        report_dir=str(args.report_dir),
        max_steps=args.max_steps,
        max_context_tokens=args.max_context_tokens,
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
    )

    agent = CodingAgent(
        config,
        llm_client=OpenAICompatibleClient(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
        ),
        toolbox=WorkspaceToolbox(config.workspace_root),
    )

    stream_enabled = not bool(args.no_stream)
    stream_buffer: list[str] = []

    def on_stream(chunk: str) -> None:
        if not stream_enabled:
            return
        stream_buffer.append(chunk)
        print(chunk, end="", flush=True)

    try:
        result = agent.run(task, stream_callback=on_stream if stream_enabled else None)
    except (LLMClientError, RuntimeError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if stream_enabled and stream_buffer:
        print()

    if result.plan is not None:
        print("=== PLAN ===")
        print(f"目标：{result.plan.goal}")
        if result.plan.summary:
            print(f"路线：{result.plan.summary}")
        if result.plan.notes:
            print("注意事项：")
            for note in result.plan.notes:
                print(f"- {note}")
        print("步骤：")
        for step in result.plan.steps:
            print(f"{step.id}. {step.task}（原因：{step.reason}）")
        print("=== RESULT ===")

    if not stream_enabled:
        print(result.final_answer)
    if result.artifacts is not None:
        print(f"[saved report] {result.artifacts.markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
