# 🤖 Coding Agent v1.0

> 一个**从零实现**的本地编程智能体：能读写文件、执行命令、调用大模型，并把运行过程保存成报告，方便演示与答辩。

**GitHub**：`https://github.com/kylinxx/swe.git`

## ✨ 项目亮点
- **完整 agent 闭环**：任务理解 → 计划 → 工具调用 → 结果回写 → 最终回答
- **本地工具内置**：`read_file` / `write_file` / `search_text` / `replace_text` / `execute_command`
- **安全工作区**：只允许在指定目录内操作，避免越权读写
- **上下文压缩**：对话过长时自动保留关键系统信息并压缩历史
- **运行留痕**：每次执行可生成报告，便于展示思路和排查问题
- **双模型兼容**：OpenAI / DeepSeek 都可直接接入
- **Baseline 验证页**：Streamlit 中可直接查看 mini benchmark 的修复前/修复后效果

## 🚀 一步运行
1. 复制 `.env.example` 为 `.env`
2. 填入 `DEEPSEEK_API_KEY`
3. 运行：

```bash
python -m coding_agent --plan --cwd demo_workspace/mini_buggy_app "修复测试失败并说明原因"
```

## 🖥️ 可视化演示
```bash
streamlit run streamlit_app.py
```
这个页面只是**演示层**，不会替代核心 agent 逻辑；其中的 baseline 页可以直接展示 benchmark 的验证效果。

## 🔑 DeepSeek 推荐配置
```env
MODEL_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

## 🧪 我做了什么
- 搭建了一个可循环执行的 coding agent
- 做了本地文件与命令工具
- 加了上下文管理、报错兜底和运行报告
- 补了一个小 benchmark，方便衡量修复能力

## 📁 关键文件
- `coding_agent/cli.py`：命令行入口
- `coding_agent/agent.py`：主循环
- `coding_agent/tools.py`：本地工具层
- `coding_agent/memory.py`：上下文管理
- `scripts/run_mini_benchmark.py`：自动评估脚本
