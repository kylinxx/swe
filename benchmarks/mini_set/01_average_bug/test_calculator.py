from __future__ import annotations

import unittest

from calculator import average


class AverageTests(unittest.TestCase):
    def test_average_numbers(self) -> None:
        self.assertEqual(average([2, 4, 6]), 4)

    def test_average_single_value(self) -> None:
        self.assertEqual(average([5]), 5)

    def test_average_empty(self) -> None:
        self.assertEqual(average([]), 0)


if __name__ == "__main__":
    unittest.main()
