from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class SessionStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def get_cookie(self, name: str) -> str:
        data = self._load()
        cookies = data.get("cookies", {})
        value = cookies.get(name, "")
        return "" if value is None else str(value)

    def set_cookie(self, name: str, value: str) -> None:
        data = self._load()
        cookies = data.setdefault("cookies", {})
        cookies[name] = value
        self._save(data)

    def _load(self) -> Dict[str, object]:
        if not self.path.exists():
            return {"cookies": {}}

        with self.path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, data: Dict[str, object]) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
