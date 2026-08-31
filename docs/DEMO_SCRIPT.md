# 2 分钟演示脚本

下面这份脚本适合直接录屏，重点展示“计划模式 + 执行闭环”。

## 画面 1：项目介绍（0:00 - 0:20）

口播：
“这是我从零实现的一个 coding agent，不依赖 LangChain、AutoGen 这类框架，自己实现了 LLM 调用、上下文管理、本地工具和执行循环。”

屏幕：
- 打开仓库根目录
- 指出 `coding_agent/agent.py`、`coding_agent/tools.py`、`coding_agent/cli.py`

## 画面 2：展示计划模式（0:20 - 0:45）

命令：
`python -m coding_agent --cwd demo_workspace/mini_buggy_app --plan "修复这个小计算器项目的测试失败问题"`

口播：
“我先让智能体生成一个结构化计划。这个模式更适合复杂任务，像 Claude Code 一样先拆解步骤，再进入执行。”

屏幕：
- 展示 plan 输出
- 强调目标、步骤、注意事项

## 画面 3：展示执行闭环（0:45 - 1:30）

命令：
`python -m coding_agent --cwd demo_workspace/mini_buggy_app --plan "修复这个小计算器项目的测试失败问题"`

口播：
“接下来它会读测试、定位 bug、修改代码、再执行测试。工具是本地实现的，所以它能真正接触文件系统和命令行。”

屏幕：
- `read_file`
- `search_text`
- `replace_text`
- `execute_command`

## 画面 4：展示结果（1:30 - 1:50）

口播：
“修复完成后，测试重新通过。这个过程体现了 agent 的核心能力：理解任务、制定计划、执行动作、根据结果继续修正。”

屏幕：
- `python -m unittest discover -s tests`
- 或演示 demo 项目的测试通过

## 画面 5：总结（1:50 - 2:00）

口播：
“整体上，我做的是一个轻量但完整的 coding agent 原型：支持计划模式、本地工具、命令执行、上下文裁剪和错误恢复，适合真实编程任务。”

