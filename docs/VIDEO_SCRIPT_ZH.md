# 录制视频脚本（2 分钟以内）

## 0:00 - 0:15 开场
“这是我独立实现的一个 coding agent，不依赖 LangChain、AutoGen 这类框架，而是自己写了模型调用、工具执行、上下文管理和主循环。”

## 0:15 - 0:35 展示项目结构
打开仓库根目录，快速指出：
- `coding_agent/agent.py`：主循环和计划模式
- `coding_agent/tools.py`：本地工具
- `coding_agent/llm.py`：OpenAI 兼容请求
- `demo_workspace/mini_buggy_app`：演示任务

## 0:35 - 0:55 展示计划模式
运行：
`python -m coding_agent --cwd demo_workspace/mini_buggy_app --plan "修复这个小计算器项目的测试失败问题"`

口播：
“我先让它生成结构化计划，明确目标、步骤和注意事项。这样更像真实工程里的 task decomposition。”

## 0:55 - 1:25 展示执行闭环
口播：
“接下来它会读测试、搜索代码、修改文件、再执行测试。工具完全是本地实现的，所以它能真正操作文件系统和命令行。”

屏幕重点：
- 读 `test_calculator.py`
- 找到 `average()` 的错误
- 用 `replace_text` 修复
- 运行测试

## 1:25 - 1:45 展示报告
口播：
“每次成功运行后，项目会自动保存运行报告，包含计划、工具轨迹和最终结果，方便复盘和答辩。”

屏幕重点：
- `.coding-agent/runs/.../run.md`
- 看最终总结

## 1:45 - 2:00 收尾
“这个项目的重点不是把现成 agent 包起来，而是从底层把一个 coding agent 最核心的能力完整实现出来：规划、工具、本地执行、错误恢复和可复盘输出。”

