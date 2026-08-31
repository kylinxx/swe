# 编程智能体项目（Coding Agent）

Git 仓库地址：
- `https://github.com/kylinxx/-.git`

项目简介：
- 这是一个从零实现的轻量级 coding agent。
- 它可以和大语言模型交互，自动读取 / 修改本地文件，执行命令，并在任务完成后输出运行报告。
- 项目不依赖现成 agent 框架，核心逻辑都由我自己实现。

运行方式：
1. 设置环境变量 `OPENAI_API_KEY`。
2. 如果使用兼容网关，再设置 `OPENAI_BASE_URL` 和 `OPENAI_MODEL`。
3. 在仓库根目录运行：

```bash
python -m coding_agent "请修复 demo_workspace/mini_buggy_app 里的测试失败"
```

常用参数：
- `--plan`：先生成结构化计划，再进入工具执行循环。
- `--cwd`：指定工作区目录，agent 只能在该目录内读写文件和执行命令。
- `--no-record`：关闭运行报告保存。
- `--report-dir`：自定义报告保存目录。

核心功能：
- 读取、写入、替换、搜索文件
- 浏览目录结构
- 执行本地命令并捕获 `stdout` / `stderr`
- 上下文管理与轮次控制
- 计划模式、事件钩子和运行报告

演示建议：
- 使用 `demo_workspace/mini_buggy_app` 作为固定演示目标。
- 先展示 `pytest` / `unittest` 失败，再让 agent 自动修复。
- 最后打开 `.coding-agent/runs/` 下的报告文件，说明它记录了计划、工具调用和最终结果。

验证命令：

```bash
python -m unittest discover -s tests
```

重点文件：
- `coding_agent/agent.py`：主循环、计划模式、事件记录、报告生成
- `coding_agent/tools.py`：本地工具层和工作区边界保护
- `coding_agent/llm.py`：OpenAI 兼容接口调用
- `coding_agent/artifacts.py`：运行报告输出
- `docs/TECHNICAL_OVERVIEW.md`：项目思路和技术讲解
