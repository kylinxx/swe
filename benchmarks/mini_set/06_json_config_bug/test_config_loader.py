from __future__ import annotations

import unittest

from config_loader import load_config


class ConfigLoaderTests(unittest.TestCase):
    def test_empty_input_uses_defaults(self) -> None:
        self.assertEqual(load_config(""), {"timeout": 30, "mode": "fast", "retries": 2})

    def test_explicit_values_are_preserved(self) -> None:
        payload = '{"timeout": 10, "mode": "safe", "retries": 4}'
        self.assertEqual(load_config(payload), {"timeout": 10, "mode": "safe", "retries": 4})

    def test_partial_input_fills_missing_values(self) -> None:
        payload = '{"mode": "slow"}'
        self.assertEqual(load_config(payload), {"timeout": 30, "mode": "slow", "retries": 2})


if __name__ == "__main__":
    unittest.main()
