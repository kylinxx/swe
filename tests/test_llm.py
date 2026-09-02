from __future__ import annotations

from unittest.mock import patch
import unittest

from coding_agent.llm import OpenAICompatibleClient


class FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.encode("utf-8") for line in lines]

    def __enter__(self) -> "FakeStreamResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)


class LLMClientTests(unittest.TestCase):
    def test_streaming_completion_collects_deltas(self) -> None:
        client = OpenAICompatibleClient(api_key="test", base_url="https://example.invalid/v1")
        chunks: list[str] = []
        fake_lines = [
            'data: {"choices":[{"delta":{"content":"Hello "}}]}\n',
            'data: {"choices":[{"delta":{"content":"world"}}]}\n',
            "data: [DONE]\n",
        ]
        with patch("coding_agent.llm.request.urlopen", return_value=FakeStreamResponse(fake_lines)):
            response = client.chat_completion(
                model="test-model",
                messages=[],
                tools=[],
                stream=True,
                on_delta=chunks.append,
            )

        self.assertEqual(chunks, ["Hello ", "world"])
        self.assertEqual(response["choices"][0]["message"]["content"], "Hello world")


if __name__ == "__main__":
    unittest.main()
