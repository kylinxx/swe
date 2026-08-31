# 🤖 Coding Agent v1.0 — Build tasks with an agent

> 我从零实现了一个本地编程智能体：它会读代码、改文件、跑命令、做验证，并保存运行报告。目标是把“能分析、能动手、能复盘”的 agent 闭环做出来。

**GitHub**: `https://github.com/kylinxx/swe.git`

## ✨ Highlights
- **Agent loop** — model decision → tool execution → result feedback
- **Local tools** — read, write, search, replace, list, run commands
- **Safe workspace** — only works inside the configured project directory
- **Run reports** — saves traces for review and defense

## 🚀 Quick start
```bash
python -m coding_agent --plan --cwd demo_workspace/mini_buggy_app "请修复测试失败并说明原因"
```

## 🧪 Demo flow
1. 让 agent 先读取失败测试。
2. 自动定位 `calculator.py` 里的 bug。
3. 修改代码并重新运行测试。
4. 展示 `.coding-agent/runs/` 下的运行报告。

## 📁 Key files
- `coding_agent/agent.py` — main loop, planning mode, run artifacts
- `coding_agent/tools.py` — local tools and workspace protection
- `coding_agent/artifacts.py` — execution reports
- `coding_agent/cli.py` — command-line entry point
