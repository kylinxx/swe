from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from coding_agent.agent import CodingAgent
from coding_agent.config import AgentConfig
from coding_agent.tools import WorkspaceToolbox


class FakeLLMClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls = 0

    def chat_completion(self, **kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response


class CodingAgentTests(unittest.TestCase):
    def test_agent_runs_tool_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            (workspace_root / "hello.txt").write_text("hello world", encoding="utf-8")
            config = AgentConfig(
                api_key="test",
                model="test-model",
                base_url="https://example.invalid/v1",
                workspace_root=workspace_root,
                max_steps=3,
                max_context_tokens=4000,
            )
            fake_client = FakeLLMClient(
                [
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {
                                                "name": "read_file",
                                                "arguments": '{"path":"hello.txt","start_line":1,"max_lines":20}',
                                            },
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "我已经读到了文件内容。",
                                }
                            }
                        ]
                    },
                ]
            )
            agent = CodingAgent(config, llm_client=fake_client, toolbox=WorkspaceToolbox(workspace_root))
            observed_events: list[str] = []
            agent.on("before_tool_call", lambda event: observed_events.append(event.name))
            result = agent.run("读取 hello.txt")
            self.assertEqual(result.final_answer, "我已经读到了文件内容。")
            self.assertEqual(fake_client.calls, 2)
            self.assertIsNotNone(result.artifacts)
            self.assertTrue(result.artifacts.json_path.exists())
            self.assertTrue(result.artifacts.markdown_path.exists())
            self.assertIn("session_start", [event["name"] for event in result.events])
            self.assertIn("session_end", [event["name"] for event in result.events])
            self.assertIn("before_tool_call", observed_events)
            self.assertIn("## Event Log", result.artifacts.markdown_path.read_text(encoding="utf-8"))

    def test_plan_mode_generates_plan_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            (workspace_root / "hello.txt").write_text("hello world", encoding="utf-8")
            config = AgentConfig(
                api_key="test",
                model="test-model",
                base_url="https://example.invalid/v1",
                workspace_root=workspace_root,
                plan_mode=True,
                max_steps=3,
                max_context_tokens=4000,
            )
            fake_client = FakeLLMClient(
                [
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": """{"goal":"读取文件并回复","summary":"先读文件再总结","steps":[{"id":1,"task":"读取 hello.txt","reason":"确认文件内容"},{"id":2,"task":"给出简短回应","reason":"完成任务"}],"notes":["这是一个最小演示计划"]}""",
                                }
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {
                                                "name": "read_file",
                                                "arguments": '{"path":"hello.txt","start_line":1,"max_lines":20}',
                                            },
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "计划模式下完成了读取与回复。",
                                }
                            }
                        ]
                    },
                ]
            )
            agent = CodingAgent(config, llm_client=fake_client, toolbox=WorkspaceToolbox(workspace_root))
            result = agent.run("读取 hello.txt")
            self.assertIsNotNone(result.plan)
            self.assertEqual(result.plan.goal, "读取文件并回复")
            self.assertEqual(len(result.plan.steps), 2)
            self.assertEqual(result.final_answer, "计划模式下完成了读取与回复。")
            self.assertEqual(fake_client.calls, 3)
            self.assertIsNotNone(result.artifacts)
            self.assertTrue(result.artifacts.markdown_path.exists())
            self.assertIn("plan_created", [event["name"] for event in result.events])


if __name__ == "__main__":
    unittest.main()
