# Coding Agent v1.0

Git 仓库：`https://github.com/kylinxx/swe.git`

## 如何运行
1. 复制 `.env.example` 为 `.env`，填写 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`
2. 命令行演示：
```bash
python -m coding_agent --plan --cwd demo_workspace/mini_buggy_app "修复测试失败并说明原因"
```
3. 可视化演示：
```bash
python scripts/run_streamlit.py
```

## 特色功能
- 本地文件读写、目录检索、文本替换、命令执行
- 先规划、再执行的 coding agent 闭环
- 工具失败自动重试，JSON / schema 严格校验
- 流式输出与更细的 diff 预览
- 内置 mini benchmark 与 baseline 验证页
