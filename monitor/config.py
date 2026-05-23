from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_config(config_path: str) -> Dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        config = json.load(fh)

    if "keywords" not in config or not isinstance(config["keywords"], list):
        raise ValueError("Config must define a keywords list.")

    if "source" not in config or not isinstance(config["source"], dict):
        raise ValueError("Config must define a source object.")

    categories = config.get("categories", [])
    if categories is None:
        categories = []
    if not isinstance(categories, list):
        raise ValueError("Config field 'categories' must be a list when provided.")

    config.setdefault("poll_interval_seconds", 30)
    config["categories"] = categories
    config.setdefault("notifiers", {"console": True})
    return config
