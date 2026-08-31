from __future__ import annotations

import unittest

from coding_agent.config import normalize_base_url


class ConfigTests(unittest.TestCase):
    def test_normalize_base_url_adds_v1_for_root_urls(self) -> None:
        self.assertEqual(normalize_base_url("https://api.openai.com"), "https://api.openai.com/v1")
        self.assertEqual(normalize_base_url("https://example.com/"), "https://example.com/v1")

    def test_normalize_base_url_keeps_explicit_path(self) -> None:
        self.assertEqual(normalize_base_url("https://example.com/v1"), "https://example.com/v1")
        self.assertEqual(normalize_base_url("https://example.com/custom/api"), "https://example.com/custom/api")


if __name__ == "__main__":
    unittest.main()

