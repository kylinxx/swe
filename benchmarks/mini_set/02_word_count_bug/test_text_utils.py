from __future__ import annotations

import unittest

from text_utils import count_words


class WordCountTests(unittest.TestCase):
    def test_basic_sentence(self) -> None:
        self.assertEqual(count_words("hello world"), 2)

    def test_multiple_spaces(self) -> None:
        self.assertEqual(count_words("hello   world   from   agent"), 4)

    def test_empty_text(self) -> None:
        self.assertEqual(count_words("   "), 0)


if __name__ == "__main__":
    unittest.main()
