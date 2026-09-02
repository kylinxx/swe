from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from paths import safe_join


class SafeJoinTests(unittest.TestCase):
    def test_normal_path_stays_inside_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            result = safe_join(base, "notes/today.txt")
            self.assertEqual(result, base / "notes" / "today.txt")

    def test_path_traversal_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            with self.assertRaises(ValueError):
                safe_join(base, "../escape.txt")


if __name__ == "__main__":
    unittest.main()
