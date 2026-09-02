from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from coding_agent.config import load_dotenv_if_present, resolve_llm_runtime_config

load_dotenv_if_present(REPO_ROOT / ".env")


@dataclass
class StepResult:
    returncode: int
    seconds: float
    stdout: str
    stderr: str


def clip_text(text: str, max_chars: int = 2500) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[output clipped at {len(text)} characters]"


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(command: list[str], cwd: Path, timeout_seconds: int) -> StepResult:
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        return StepResult(
            returncode=completed.returncode,
            seconds=perf_counter() - started,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return StepResult(
            returncode=-1,
            seconds=perf_counter() - started,
            stdout=exc.stdout or "",
            stderr=exc.stderr or f"Timed out after {timeout_seconds}s",
        )


def discover_tests_command() -> list[str]:
    return [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]


def build_agent_command(task_dir: Path, prompt: str, *, use_plan: bool) -> list[str]:
    command = [sys.executable, "-m", "coding_agent", "--cwd", str(task_dir)]
    if use_plan:
        command.append("--plan")
    command.append(prompt)
    return command


def ensure_runtime_config() -> tuple[str, str]:
    try:
        runtime = resolve_llm_runtime_config()
    except ValueError as exc:
        raise SystemExit(
            "缺少可用的模型凭据。请先在 `.env` 中配置 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`。"
        ) from exc
    return runtime.provider, runtime.model


def prepare_task_workspace(source_dir: Path, temp_root: Path, task_id: str) -> Path:
    target_dir = temp_root / task_id
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    return target_dir


def run_benchmark(
    *,
    manifest_path: Path,
    task_filter: set[str] | None,
    limit: int | None,
    dry_run: bool,
    use_plan: bool,
    timeout_seconds: int,
    report_path: Path | None,
) -> int:
    manifest = load_manifest(manifest_path)
    tasks = list(manifest.get("tasks", []))
    if task_filter:
        tasks = [task for task in tasks if str(task.get("id")) in task_filter]
    if limit is not None:
        tasks = tasks[:limit]

    print(f"Loaded {len(tasks)} tasks from {manifest_path}")
    for task in tasks:
        category = task.get("category", "")
        category_suffix = f" [{category}]" if category else ""
        print(f"- {task['id']}: {task['name']} ({task['difficulty']}){category_suffix}")

    if dry_run:
        return 0

    provider, model = ensure_runtime_config()
    print(f"Using provider: {provider} | model: {model}")

    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="coding-agent-benchmark-") as tmp_dir_name:
        temp_root = Path(tmp_dir_name)
        for index, task in enumerate(tasks, start=1):
            task_id = str(task["id"])
            source_dir = (REPO_ROOT / str(task["workspace"])).resolve()
            task_dir = prepare_task_workspace(source_dir, temp_root, task_id)
            print(f"\n[{index}/{len(tasks)}] Running {task_id} in {task_dir}")

            initial_test = run_command(discover_tests_command(), task_dir, timeout_seconds)
            agent_command = build_agent_command(task_dir, str(task["prompt"]), use_plan=use_plan)
            agent_run = run_command(agent_command, REPO_ROOT, timeout_seconds)
            final_test = run_command(discover_tests_command(), task_dir, timeout_seconds)

            initial_failed = initial_test.returncode != 0
            final_passed = final_test.returncode == 0

            results.append(
                {
                    "task_id": task_id,
                    "name": task["name"],
                    "category": task.get("category", ""),
                    "difficulty": task["difficulty"],
                    "initial_test": {
                        "returncode": initial_test.returncode,
                        "seconds": initial_test.seconds,
                        "stdout": clip_text(initial_test.stdout),
                        "stderr": clip_text(initial_test.stderr),
                    },
                    "agent_run": {
                        "returncode": agent_run.returncode,
                        "seconds": agent_run.seconds,
                        "stdout": clip_text(agent_run.stdout),
                        "stderr": clip_text(agent_run.stderr),
                    },
                    "final_test": {
                        "returncode": final_test.returncode,
                        "seconds": final_test.seconds,
                        "stdout": clip_text(final_test.stdout),
                        "stderr": clip_text(final_test.stderr),
                    },
                    "initial_failed": initial_failed,
                    "final_passed": final_passed,
                    "score": 1 if final_passed else 0,
                }
            )

            status = "PASS" if final_passed else "FAIL"
            print(
                f"  initial={'FAIL' if initial_failed else 'PASS'} "
                f"agent={agent_run.returncode} final={status} "
                f"({final_test.seconds:.2f}s)"
            )

        summary = {
            "tasks": results,
            "success_rate": sum(1 for item in results if item["final_passed"]) / max(1, len(results)),
            "total_tasks": len(results),
            "initial_pass_rate": sum(1 for item in results if not item["initial_failed"]) / max(1, len(results)),
            "provider": provider,
            "model": model,
            "category_counts": {
                category: sum(1 for item in results if item["category"] == category)
                for category in sorted({str(item["category"]) for item in results if item.get("category")})
            },
        }

        print("\nSummary")
        print(f"- Tasks: {summary['total_tasks']}")
        print(f"- Success rate: {summary['success_rate']:.0%}")
        print(f"- Initial pass rate: {summary['initial_pass_rate']:.0%}")

        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"- Report saved to: {report_path}")

    return 0 if all(item["final_passed"] for item in results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the mini coding-agent benchmark.")
    parser.add_argument(
        "--manifest",
        default="benchmarks/mini_set/manifest.json",
        help="Path to the benchmark manifest.",
    )
    parser.add_argument(
        "--task-id",
        action="append",
        dest="task_ids",
        help="Only run selected task IDs. Can be passed multiple times.",
    )
    parser.add_argument("--limit", type=int, help="Limit how many tasks to run.")
    parser.add_argument("--dry-run", action="store_true", help="Only list tasks without running them.")
    parser.add_argument("--no-plan", action="store_true", help="Disable agent planning mode.")
    parser.add_argument("--timeout-seconds", type=int, default=600, help="Per-step timeout.")
    parser.add_argument(
        "--report-path",
        default="benchmarks/mini_set/results/latest.json",
        help="Where to write the summary JSON report.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (REPO_ROOT / manifest_path).resolve()
    report_path = Path(args.report_path) if args.report_path else None
    if report_path is not None and not report_path.is_absolute():
        report_path = (REPO_ROOT / report_path).resolve()
    task_filter = set(args.task_ids) if args.task_ids else None
    return run_benchmark(
        manifest_path=manifest_path,
        task_filter=task_filter,
        limit=args.limit,
        dry_run=args.dry_run,
        use_plan=not args.no_plan,
        timeout_seconds=args.timeout_seconds,
        report_path=report_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
