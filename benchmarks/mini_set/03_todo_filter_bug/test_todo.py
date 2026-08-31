from __future__ import annotations

import unittest

from todo import completed_titles


class TodoFilterTests(unittest.TestCase):
    def test_completed_only(self) -> None:
        items = [
            {"title": "write tests", "done": True},
            {"title": "fix bug", "done": False},
            {"title": "push code", "done": True},
        ]
        self.assertEqual(completed_titles(items), ["write tests", "push code"])

    def test_empty_result(self) -> None:
        self.assertEqual(completed_titles([]), [])


if __name__ == "__main__":
    unittest.main()
