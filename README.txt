# 🤖 Coding Agent v1.0

**Git 仓库地址**：`https://github.com/kylinxx/swe.git`

## 如何运行
1. 复制 `.env.example` 为 `.env`，填写 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`
2. 命令行运行：
```bash
python -m coding_agent --plan --cwd demo_workspace/mini_buggy_app "修复测试失败并说明原因"
```
3. 可视化界面：
```bash
python scripts/run_streamlit.py
```

## 特色功能
- **完整 agent 闭环**：任务理解 → 规划 → 工具调用 → 结果回写 → 最终回答
- **本地工具**：`read_file` / `write_file` / `search_text` / `replace_text` / `execute_command`
- **安全工作区**：限制在指定目录内操作
- **上下文管理**：自动压缩历史，保留关键信息
- **可视化展示**：Streamlit 页面展示运行过程和 baseline 验证效果
