from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from monitor.models import Post


class SeenStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_posts (
                    fingerprint TEXT PRIMARY KEY,
                    source_id TEXT,
                    title TEXT,
                    url TEXT,
                    created_at TEXT,
                    notified_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _fingerprint(self, post: Post) -> str:
        if post.source_id:
            return f"id:{post.source_id}"
        raw = "||".join([post.title, post.content, post.url])
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"hash:{digest}"

    def has_seen(self, post: Post) -> bool:
        fingerprint = self._fingerprint(post)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_posts WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return row is not None

    def mark_seen(self, post: Post) -> None:
        fingerprint = self._fingerprint(post)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO seen_posts
                (fingerprint, source_id, title, url, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (fingerprint, post.source_id, post.title, post.url, post.created_at),
            )
            conn.commit()
