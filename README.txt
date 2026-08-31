# 编程智能体项目（Coding Agent）

Git 仓库地址：
- `https://github.com/kylinxx/-.git`

这是一个从零实现的 coding agent。它能和大模型交互，自动读写本地文件、执行命令，并在任务结束后生成运行报告。

运行：
```bash
python -m coding_agent "请修复 demo_workspace/mini_buggy_app 里的测试失败"
```

常用参数：
- `--plan`：先生成计划，再执行。
- `--cwd`：指定工作区目录。
- `--no-record`：关闭运行报告保存。

特色：
- 自己实现 LLM 调用、工具层、上下文管理和主循环。
- 支持读写文件、目录浏览、全文搜索、精确替换、命令执行。
- 有工作区边界保护、命令超时、输出截断和运行报告。
- 适合演示“先分析、再修复、再验证”的完整 agent 流程。

演示建议：
- 用 `demo_workspace/mini_buggy_app`。
- 先让 agent 看测试失败，再自动修复。
- 最后展示 `.coding-agent/runs/` 下的报告。
