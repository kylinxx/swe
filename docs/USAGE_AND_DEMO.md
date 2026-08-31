# 使用与演示指南

## 运行项目

1. 设置环境变量：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=...
```

2. 在仓库根目录运行：

```bash
python -m coding_agent "请完成一个编程任务"
```

3. 如果要先看计划，再执行：

```bash
python -m coding_agent --plan "请修复 demo_workspace/mini_buggy_app 里的测试失败"
```

4. 如果要指定工作区：

```bash
python -m coding_agent --cwd demo_workspace/mini_buggy_app "请修复测试失败"
```

## 推荐演示流程

1. 展示仓库结构。
2. 展示 `docs/TECHNICAL_OVERVIEW.md` 中的架构图。
3. 运行 agent，先生成计划。
4. 展示它读取文件、搜索代码、修改文件、执行测试。
5. 展示测试通过。
6. 打开 `.coding-agent/runs/` 下的报告，说明它记录了全过程。

## 安全提示

- 不要在视频里展示 API key。
- 不要把 `.env` 内容录进去。
- 演示任务要尽量稳定、短小、可重复。
- 如果模型响应慢，可以提前录一遍，再剪辑成最终版。
