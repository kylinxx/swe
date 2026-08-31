from __future__ import annotations

import unittest

from calculator import average, format_average


class CalculatorTests(unittest.TestCase):
    def test_average_three_numbers(self) -> None:
        self.assertAlmostEqual(average([1, 2, 3]), 2.0)

    def test_average_single_number(self) -> None:
        self.assertAlmostEqual(average([10]), 10.0)

    def test_format_average(self) -> None:
        self.assertEqual(format_average([2, 4]), "average=3.00")


if __name__ == "__main__":
    unittest.main()

