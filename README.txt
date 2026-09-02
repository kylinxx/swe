# 🤖 Coding Agent v1.0 — 软件工程推免项目

> 本项目从零实现了一个**本地编程智能体**：能够读写文件、执行命令、调用大模型，并保存运行报告，方便演示和答辩。

**GitHub**：`https://github.com/kylinxx/swe.git`

## 项目亮点
- **完整 agent 闭环**：任务理解 → 规划 → 工具调用 → 结果回写 → 最终回答
- **本地工具内置**：`read_file` / `write_file` / `search_text` / `replace_text` / `execute_command`
- **安全工作区**：所有操作限制在指定目录内，避免越权读写
- **上下文管理**：对话过长时自动压缩历史，保留关键系统信息
- **运行留痕**：每次执行都会生成报告，便于展示思路与过程
- **双模型兼容**：支持 OpenAI 兼容接口，也支持 DeepSeek
- **Baseline 验证页**：`Streamlit` 页面可直接展示 mini benchmark 的修复前/修复后效果

## 如何运行
1. 复制 `.env.example` 为 `.env`
2. 填入 `DEEPSEEK_API_KEY`（推荐）或 `OPENAI_API_KEY`
3. 命令行运行：
```bash
python -m coding_agent --plan --cwd demo_workspace/mini_buggy_app "修复测试失败并说明原因"
```
4. 可视化演示：
```bash
streamlit run streamlit_app.py
```

## 关键文件
- `coding_agent/agent.py`：主循环与工具调用
- `coding_agent/tools.py`：本地文件和命令工具
- `coding_agent/memory.py`：上下文压缩与历史管理
- `scripts/run_mini_benchmark.py`：自动评估脚本
- `streamlit_app.py`：可视化演示与 baseline 展示
