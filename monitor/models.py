from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Post:
    source_id: str
    title: str
    content: str
    url: str
    created_at: str
    category: str = ""
    miniapp_code_data_url: str = ""

    @property
    def search_text(self) -> str:
        return f"{self.category}\n{self.title}\n{self.content}".strip()
