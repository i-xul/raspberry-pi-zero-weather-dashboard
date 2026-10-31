"""Load local, untracked dashboard configuration."""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.local.json"


def load_config():
    if not CONFIG_PATH.is_file():
        raise RuntimeError(
            "Missing config.local.json. Copy config.example.json "
            "and set the local values."
        )

    with CONFIG_PATH.open(encoding="utf-8-sig") as handle:
        config = json.load(handle)

    required = (
        "cosy_baro_url",
        "dht22_url",
        "dht22_cache_path",
        "waveshare_lib_path",
    )

    for key in required:
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"Missing or invalid configuration value: {key}")

    return config
