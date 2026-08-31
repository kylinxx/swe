from __future__ import annotations

import unittest

from coding_agent.memory import ConversationHistory


class ConversationHistoryTests(unittest.TestCase):
    def test_history_trims_from_front(self) -> None:
        history = ConversationHistory(max_context_tokens=40)
        history.append({"role": "system", "content": "system prompt"})
        history.append({"role": "user", "content": "first question"})
        history.append({"role": "assistant", "content": "first answer"})
        history.append({"role": "user", "content": "second question"})
        messages = history.build_for_model()
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1]["content"], "second question")


if __name__ == "__main__":
    unittest.main()

