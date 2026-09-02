from __future__ import annotations

import unittest

from report import build_summary


class ReportSummaryTests(unittest.TestCase):
    def test_summary_counts_passed_and_failed_items(self) -> None:
        results = [
            {"name": "alpha", "passed": True},
            {"name": "beta", "passed": False},
            {"name": "gamma", "passed": True},
        ]
        summary = build_summary(results)
        self.assertEqual(summary["passed"], ["alpha", "gamma"])
        self.assertEqual(summary["failed"], ["beta"])
        self.assertAlmostEqual(summary["success_rate"], 2 / 3)

    def test_empty_results(self) -> None:
        summary = build_summary([])
        self.assertEqual(summary["passed"], [])
        self.assertEqual(summary["failed"], [])
        self.assertEqual(summary["success_rate"], 0)


if __name__ == "__main__":
    unittest.main()
