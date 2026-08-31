# 使用与演示指南

## 运行项目

1. 设置环境变量：
   - `OPENAI_API_KEY`
   - 可选：`OPENAI_BASE_URL`
   - 可选：`OPENAI_MODEL`
2. 在仓库根目录执行：
   - `python -m coding_agent "你的编程任务"`
3. 如果任务较复杂，可加：
   - `--plan`
4. 若要切换工作区：
   - `python -m coding_agent --cwd demo_workspace/mini_buggy_app "请修复测试失败的问题"`

## 推荐演示流程

1. 先展示 `README.txt` 和项目结构。
2. 再让 agent 在 `demo_workspace/mini_buggy_app` 中运行测试。
3. 它会读 `calculator.py` 和 `test_calculator.py`，定位 `average()` 的 bug。
4. 修复后再次运行测试，展示全绿结果。
5. 如果要突出规划能力，可以先用 `--plan` 展示计划，再进入执行。

## 2 分钟视频节奏

- 0:00 - 0:20：项目目标与技术选型。
- 0:20 - 1:20：agent 读文件、搜索、修改、执行测试。
- 1:20 - 1:45：展示验证通过。
- 1:45 - 2:00：总结“无框架、本地工具、闭环执行”。

## 录制提醒

- 不要展示 API Key。
- 如果命令输出较长，可以适当加速。
- 尽量选择稳定、可重复的修复任务。
