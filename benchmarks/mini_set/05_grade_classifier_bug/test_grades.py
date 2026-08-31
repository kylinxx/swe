from __future__ import annotations

import unittest

from grades import letter_grade


class GradeClassifierTests(unittest.TestCase):
    def test_boundaries(self) -> None:
        self.assertEqual(letter_grade(90), "A")
        self.assertEqual(letter_grade(80), "B")
        self.assertEqual(letter_grade(70), "C")
        self.assertEqual(letter_grade(60), "D")

    def test_high_and_low_scores(self) -> None:
        self.assertEqual(letter_grade(100), "A")
        self.assertEqual(letter_grade(0), "F")


if __name__ == "__main__":
    unittest.main()
