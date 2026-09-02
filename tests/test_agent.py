from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from coding_agent.agent import CodingAgent
from coding_agent.config import AgentConfig
from coding_agent.tools import ToolResult, WorkspaceToolbox


class FakeLLMClient:
    def __init__(
        self,
        responses: list[dict],
        *,
        stream_chunks_by_call: dict[int, list[str]] | None = None,
    ) -> None:
        self.responses = responses
        self.stream_chunks_by_call = stream_chunks_by_call or {}
        self.calls = 0

    def chat_completion(self, **kwargs):
        response_index = self.calls
        self.calls += 1
        on_delta = kwargs.get("on_delta")
        if callable(on_delta):
            for chunk in self.stream_chunks_by_call.get(response_index, []):
                on_delta(chunk)
        return self.responses[response_index]


class RetryingToolbox:
    def __init__(self) -> None:
        self.calls = 0

    def tool_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Test tool",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "command": {"type": "string"},
                        },
                        "required": ["command"],
                    },
                },
            }
        ]

    def call(self, name: str, arguments: dict) -> ToolResult:
        self.calls += 1
        if self.calls == 1:
            return ToolResult(False, "temporary failure", {"retryable": True, "tool": name})
        return ToolResult(True, "recovered successfully", {"retryable": False, "tool": name})


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
                                    "content": "I have read the file.",
                                }
                            }
                        ]
                    },
                ]
            )
            agent = CodingAgent(config, llm_client=fake_client, toolbox=WorkspaceToolbox(workspace_root))
            observed_events: list[str] = []
            agent.on("before_tool_call", lambda event: observed_events.append(event.name))
            result = agent.run("Read hello.txt")
            self.assertEqual(result.final_answer, "I have read the file.")
            self.assertEqual(fake_client.calls, 2)
            self.assertIsNotNone(result.artifacts)
            self.assertTrue(result.artifacts.json_path.exists())
            self.assertTrue(result.artifacts.markdown_path.exists())
            self.assertIn("session_start", [event["name"] for event in result.events])
            self.assertIn("session_end", [event["name"] for event in result.events])
            self.assertIn("before_tool_call", observed_events)
            self.assertIn("## Event Log", result.artifacts.markdown_path.read_text(encoding="utf-8"))

    def test_agent_streams_output(self) -> None:
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
                                    "content": "I have finished.",
                                }
                            }
                        ]
                    },
                ],
                stream_chunks_by_call={1: ["I have ", "finished."]},
            )
            agent = CodingAgent(config, llm_client=fake_client, toolbox=WorkspaceToolbox(workspace_root))
            streamed: list[str] = []
            result = agent.run("Read hello.txt", stream_callback=streamed.append)
            self.assertEqual(result.final_answer, "I have finished.")
            self.assertEqual("".join(streamed), "I have finished.")
            self.assertEqual(fake_client.calls, 2)

    def test_agent_retries_retryable_tool_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            config = AgentConfig(
                api_key="test",
                model="test-model",
                base_url="https://example.invalid/v1",
                workspace_root=workspace_root,
                max_steps=3,
                max_context_tokens=4000,
                tool_retry_attempts=3,
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
                                                "name": "execute_command",
                                                "arguments": '{"command":"python -c \\"print(1)\\""}',
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
                                    "content": "Command recovered.",
                                }
                            }
                        ]
                    },
                ]
            )
            agent = CodingAgent(config, llm_client=fake_client, toolbox=RetryingToolbox())
            result = agent.run("Run a command")
            self.assertEqual(result.final_answer, "Command recovered.")
            self.assertEqual(result.tool_events[0]["attempts"], 2)
            self.assertEqual(result.tool_events[0]["retry_count"], 1)

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
                                    "content": (
                                        '{"goal":"Read and summarize the file",'
                                        '"summary":"Inspect the file then respond with the result",'
                                        '"steps":[{"id":1,"task":"Read hello.txt","reason":"Need the file content"},'
                                        '{"id":2,"task":"Reply with a summary","reason":"Finish the task"}],'
                                        '"notes":["Keep the change minimal"]}'
                                    ),
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
                                    "content": "Plan mode completed the read and summary.",
                                }
                            }
                        ]
                    },
                ]
            )
            agent = CodingAgent(config, llm_client=fake_client, toolbox=WorkspaceToolbox(workspace_root))
            result = agent.run("Read hello.txt")
            self.assertIsNotNone(result.plan)
            self.assertEqual(result.plan.goal, "Read and summarize the file")
            self.assertEqual(len(result.plan.steps), 2)
            self.assertEqual(result.final_answer, "Plan mode completed the read and summary.")
            self.assertEqual(fake_client.calls, 3)
            self.assertIsNotNone(result.artifacts)
            self.assertTrue(result.artifacts.markdown_path.exists())
            self.assertIn("plan_created", [event["name"] for event in result.events])


if __name__ == "__main__":
    unittest.main()
