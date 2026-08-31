from __future__ import annotations

import unittest

from dedupe import unique_in_order


class DedupeTests(unittest.TestCase):
    def test_keeps_first_occurrence_order(self) -> None:
        self.assertEqual(unique_in_order(["b", "a", "b", "c", "a"]), ["b", "a", "c"])

    def test_empty_list(self) -> None:
        self.assertEqual(unique_in_order([]), [])


if __name__ == "__main__":
    unittest.main()
