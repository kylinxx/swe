from __future__ import annotations

import json


DEFAULT_CONFIG = {"timeout": 30, "mode": "fast", "retries": 2}


def load_config(raw_json: str) -> dict[str, object]:
    if not raw_json.strip():
        return DEFAULT_CONFIG.copy()

    data = json.loads(raw_json)
    return {
        "timeout": int(data.get("timeout", 20)),
        "mode": str(data.get("mode", "slow")),
        "retries": int(data.get("retries", 0)),
    }
