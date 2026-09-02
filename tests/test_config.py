from __future__ import annotations

import unittest
from unittest.mock import patch

from coding_agent.config import default_llm_settings, infer_model_provider, normalize_base_url, resolve_llm_runtime_config


class ConfigTests(unittest.TestCase):
    def test_normalize_base_url_handles_openai_and_deepseek_differently(self) -> None:
        self.assertEqual(normalize_base_url("https://api.openai.com", "openai"), "https://api.openai.com/v1")
        self.assertEqual(normalize_base_url("https://api.openai.com/v1/", "openai"), "https://api.openai.com/v1")
        self.assertEqual(normalize_base_url("https://api.deepseek.com/", "deepseek"), "https://api.deepseek.com")

    def test_default_llm_settings_prefers_openai_by_default(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "openai-key",
            },
            clear=True,
        ):
            self.assertEqual(infer_model_provider(), "openai")
            base_url, model = default_llm_settings()
            self.assertEqual(base_url, "https://api.openai.com/v1")
            self.assertEqual(model, "gpt-4.1-mini")

    def test_resolve_llm_runtime_config_prefers_deepseek_when_requested(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "MODEL_PROVIDER": "deepseek",
                "DEEPSEEK_API_KEY": "deepseek-key",
            },
            clear=True,
        ):
            runtime = resolve_llm_runtime_config()
            self.assertEqual(runtime.provider, "deepseek")
            self.assertEqual(runtime.api_key, "deepseek-key")
            self.assertEqual(runtime.base_url, "https://api.deepseek.com")
            self.assertEqual(runtime.model, "deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()
