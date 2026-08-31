# 编程智能体项目（Coding Agent）

Git 仓库地址：`https://github.com/kylinxx/swe.git`

## 项目简介
这是一个我个人独立实现的轻量级 coding agent。它可以和大模型交互，自动读取 / 修改本地文件、执行命令，并在任务完成后生成运行报告。项目不依赖现成 agent 框架，核心逻辑由我自己完成。

## 我做了什么
- 实现了 OpenAI 兼容的模型调用
- 自己写了本地工具层：读文件、写文件、目录浏览、全文搜索、精确替换、命令执行
- 自己实现了上下文管理，控制对话长度
- 自己实现了主循环：模型决策 → 工具执行 → 结果回传 → 继续迭代
- 增加了工作区边界保护、命令超时、输出截断和运行报告

## 运行方式
```bash
python -m coding_agent "请修复 demo_workspace/mini_buggy_app 里的测试失败"
```

常用参数：
- `--plan`：先生成计划，再执行
- `--cwd`：指定工作区目录
- `--no-record`：关闭运行报告保存

## 演示建议
建议直接使用 `demo_workspace/mini_buggy_app`。先让 agent 读取测试失败信息，再自动修复代码，最后展示 `.coding-agent/runs/` 下生成的报告。
