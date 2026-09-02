from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from coding_agent.agent import CodingAgent
from coding_agent.config import (
    AgentConfig,
    default_llm_settings,
    load_dotenv_if_present,
    normalize_base_url,
    resolve_workspace_root,
)
from coding_agent.llm import LLMClientError, OpenAICompatibleClient
from coding_agent.tools import WorkspaceToolbox


REPO_ROOT = Path(__file__).resolve().parent
BENCHMARK_MANIFEST_PATH = REPO_ROOT / "benchmarks" / "mini_set" / "manifest.json"
BENCHMARK_REPORT_PATH = REPO_ROOT / "benchmarks" / "mini_set" / "results" / "latest.json"


load_dotenv_if_present(REPO_ROOT / ".env")
st.set_page_config(page_title="Coding Agent Demo", page_icon="🤖", layout="wide")


def default_provider() -> str:
    provider = os.getenv("MODEL_PROVIDER", "").strip().lower()
    if provider in {"openai", "deepseek"}:
        return provider
    if os.getenv("DEEPSEEK_API_KEY", "").strip() and not os.getenv("OPENAI_API_KEY", "").strip():
        return "deepseek"
    return "openai"


def resolve_credentials(provider: str, api_key: str, base_url: str, model: str) -> tuple[str, str, str]:
    provider = provider.strip().lower()
    if provider == "deepseek":
        base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    else:
        base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    return api_key.strip(), base_url.strip(), model.strip()


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def benchmark_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in report.get("tasks", []):
        rows.append(
            {
                "Task": task.get("task_id", ""),
                "Name": task.get("name", ""),
                "Category": task.get("category", ""),
                "Difficulty": task.get("difficulty", ""),
                "Baseline Pass": "Yes" if not task.get("initial_failed") else "No",
                "Final Pass": "Yes" if task.get("final_passed") else "No",
                "Score": task.get("score", 0),
            }
        )
    return rows


def summarize_report(report: dict[str, Any]) -> dict[str, float | int]:
    tasks = list(report.get("tasks", []))
    total = int(report.get("total_tasks", len(tasks)))
    final_passed = sum(1 for item in tasks if item.get("final_passed"))
    baseline_passed = sum(1 for item in tasks if not item.get("initial_failed"))
    retries = sum(int(item.get("retry_count", 0)) for item in tasks)
    return {
        "total": total,
        "baseline_passed": baseline_passed,
        "final_passed": final_passed,
        "baseline_failures": total - baseline_passed,
        "improvement": final_passed - baseline_passed,
        "success_rate": float(report.get("success_rate", final_passed / max(1, total))),
        "retries": retries,
    }


def run_benchmark(limit: int | None, use_plan: bool, report_path: Path) -> tuple[int, str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_mini_benchmark.py"),
        "--report-path",
        str(report_path),
    ]
    if limit is not None:
        command.extend(["--limit", str(limit)])
    if not use_plan:
        command.append("--no-plan")
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined_output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
    return completed.returncode, combined_output


def render_tool_trace(tool_events: list[dict[str, Any]]) -> None:
    if not tool_events:
        st.info("本次运行没有记录到工具调用。")
        return

    for index, event in enumerate(tool_events, start=1):
        attempts = int(event.get("attempts", 1))
        retry_count = int(event.get("retry_count", max(0, attempts - 1)))
        title = f"{index}. {event.get('name', 'tool')} · {'成功' if event.get('success') else '失败'} · {attempts} 次尝试"
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.write(f"Summary: {event.get('summary', '')}")
            st.write(f"Retries: {retry_count}")
            metadata = event.get("metadata") or {}
            st.caption(json.dumps(metadata, ensure_ascii=False, indent=2, default=str))
            content = str(event.get("content") or "")
            if "diff_preview" in metadata:
                st.subheader("Diff Preview")
                st.code(str(metadata.get("diff_preview") or content), language="text")
            else:
                st.code(content or "[empty]", language="text")


st.title("🤖 Coding Agent Demo")
st.caption("一个可在本地读写文件、执行命令、调用模型并自动修复代码的编程智能体。")

with st.sidebar:
    st.header("运行配置")
    provider = st.selectbox("模型提供方", ["deepseek", "openai"], index=0 if default_provider() == "deepseek" else 1)
    api_key_default = os.getenv("DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY", "")
    api_key = st.text_input("API Key", value=api_key_default, type="password")
    base_url_default, model_default = default_llm_settings(provider)
    base_url = st.text_input("Base URL", value=base_url_default)
    model = st.text_input("Model", value=model_default)
    cwd = st.text_input("工作目录", value="demo_workspace/mini_buggy_app")
    plan_mode = st.checkbox("先生成计划", value=True)
    record_runs = st.checkbox("保存运行报告", value=True)
    max_steps = st.slider("最大步数", min_value=4, max_value=20, value=12)
    max_context_tokens = st.slider("上下文预算", min_value=2000, max_value=32000, value=12000, step=1000)
    temperature = st.slider("温度", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    timeout_seconds = st.slider("超时秒数", min_value=20, max_value=180, value=60, step=5)

tab_agent, tab_benchmark = st.tabs(["Agent Demo", "Baseline Validation"])

with tab_agent:
    st.subheader("任务")
    task = st.text_area(
        "把你想让 agent 完成的编程任务写在这里。",
        value="修复 demo_workspace/mini_buggy_app 里的测试失败，并说明原因和修改点。",
        height=140,
    )

    run_clicked = st.button("开始运行", type="primary")

    if run_clicked:
        if not api_key.strip():
            st.error("请先填写 API Key。")
        else:
            try:
                resolved_api_key, resolved_base_url, resolved_model = resolve_credentials(provider, api_key, base_url, model)
                workspace_root = resolve_workspace_root(Path(cwd))
                config = AgentConfig(
                    api_key=resolved_api_key,
                    model=resolved_model,
                    base_url=normalize_base_url(resolved_base_url, provider),
                    workspace_root=workspace_root,
                    plan_mode=plan_mode,
                    record_runs=record_runs,
                    max_steps=max_steps,
                    max_context_tokens=max_context_tokens,
                    temperature=temperature,
                    timeout_seconds=timeout_seconds,
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

                stream_placeholder = st.empty()
                stream_chunks: list[str] = []

                def on_stream(chunk: str) -> None:
                    stream_chunks.append(chunk)
                    stream_placeholder.markdown("**实时输出**\n\n" + "".join(stream_chunks) + "▌")

                with st.spinner("Agent 正在思考和执行..."):
                    result = agent.run(task, stream_callback=on_stream)
                if stream_chunks:
                    stream_placeholder.markdown("**实时输出**\n\n" + "".join(stream_chunks))
                else:
                    stream_placeholder.markdown("**实时输出**\n\n[无文本输出]")
                st.session_state["last_result"] = result
                st.session_state["last_error"] = None
                st.success("运行完成。")
            except (LLMClientError, RuntimeError, ValueError, OSError) as exc:
                st.session_state["last_error"] = str(exc)
                st.session_state["last_result"] = None
                st.error(str(exc))

    result = st.session_state.get("last_result")
    last_error = st.session_state.get("last_error")

    if result is not None:
        st.divider()
        left, right = st.columns([2, 1])
        with left:
            st.subheader("最终结果")
            st.write(result.final_answer)
        with right:
            st.subheader("运行概况")
            st.metric("步数", result.steps)
            st.metric("历史消息", len(result.history))
            st.metric("工具调用", len(result.tool_events))
            st.metric("重试次数", sum(int(item.get("retry_count", 0)) for item in result.tool_events))
            if result.artifacts is not None:
                st.caption(f"报告：{result.artifacts.markdown_path}")

        if result.plan is not None:
            with st.expander("执行计划", expanded=True):
                st.markdown(f"**目标**：{result.plan.goal}")
                if result.plan.summary:
                    st.markdown(f"**路线**：{result.plan.summary}")
                if result.plan.notes:
                    st.markdown("**注意事项**")
                    for note in result.plan.notes:
                        st.write(f"- {note}")
                if result.plan.steps:
                    st.markdown("**步骤**")
                    for step in result.plan.steps:
                        st.write(f"{step.id}. {step.task}（原因：{step.reason}）")

        st.subheader("工具轨迹")
        render_tool_trace(result.tool_events)

        with st.expander("对话历史", expanded=False):
            st.code(json.dumps(result.history, ensure_ascii=False, indent=2, default=str), language="json")

        with st.expander("运行事件", expanded=False):
            st.code(json.dumps(result.events, ensure_ascii=False, indent=2, default=str), language="json")

        with st.expander("运行报告", expanded=False):
            if result.artifacts is not None:
                st.code(str(result.artifacts.markdown_path), language="text")
            else:
                st.info("当前没有保存报告。")

    if last_error and result is None:
        st.info("先修正左侧配置，再点击开始运行。")

with tab_benchmark:
    st.subheader("Baseline 验证")
    st.write(
        "这里展示 mini benchmark 的验证结果：**Baseline** 是原始带 bug 的代码，"
        "**Final** 是 agent 修复后的结果。"
    )

    manifest = load_json_file(BENCHMARK_MANIFEST_PATH)
    report = load_json_file(BENCHMARK_REPORT_PATH)

    if manifest is not None:
        task_count = len(manifest.get("tasks", []))
        st.caption(f"Benchmark manifest: {BENCHMARK_MANIFEST_PATH}")
        st.dataframe(
            [
                {
                    "Task": task["id"],
                    "Name": task["name"],
                    "Category": task.get("category", ""),
                    "Difficulty": task["difficulty"],
                }
                for task in manifest.get("tasks", [])
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        task_count = 1
        st.warning("没有找到 benchmark manifest。")

    benchmark_limit = st.slider("运行任务数", min_value=1, max_value=max(1, task_count), value=max(1, task_count))
    benchmark_plan_mode = st.checkbox("Benchmark 使用 plan mode", value=True)
    run_benchmark_clicked = st.button("运行 mini benchmark", type="primary")

    benchmark_output_key = "benchmark_output"
    benchmark_status_key = "benchmark_status"

    if run_benchmark_clicked:
        with st.spinner("正在运行 benchmark..."):
            returncode, output = run_benchmark(benchmark_limit, benchmark_plan_mode, BENCHMARK_REPORT_PATH)
        st.session_state[benchmark_output_key] = output
        st.session_state[benchmark_status_key] = returncode
        report = load_json_file(BENCHMARK_REPORT_PATH)
        if returncode == 0:
            st.success(f"Benchmark 已完成并保存到 {BENCHMARK_REPORT_PATH}")
        else:
            st.warning("Benchmark 运行完成，但有任务未通过。")

    if report is not None:
        summary = summarize_report(report)
        left, middle, right = st.columns(3)
        left.metric("Baseline 通过数", summary["baseline_passed"])
        middle.metric("Final 通过数", summary["final_passed"], delta=summary["improvement"])
        right.metric("Success Rate", f"{summary['success_rate']:.0%}")

        st.progress(min(1.0, float(summary["success_rate"])))
        st.write(
            f"Baseline 未通过任务数：**{summary['baseline_failures']}**；"
            f"Final 相比 Baseline 提升：**{summary['improvement']}** 个任务。"
        )

        st.dataframe(benchmark_rows(report), use_container_width=True, hide_index=True)

        with st.expander("Benchmark 原始输出", expanded=False):
            st.code(st.session_state.get(benchmark_output_key, ""), language="text")
    else:
        st.info(
            "还没有 benchmark 报告。你可以先点上面的按钮跑一次，"
            "生成 `benchmarks/mini_set/results/latest.json` 后这里会自动展示。"
        )
