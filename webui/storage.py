from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from monitor.config import load_config
from monitor.models import Post
from monitor.notifier import _build_summary, _extract_contact


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AppStorage:
    def __init__(self, db_path: str = "data/app.db", fallback_config_path: str = "config.miniprogram.json") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.fallback_config_path = fallback_config_path
        self._init_db()
        self._ensure_settings()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    config_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    total_posts INTEGER NOT NULL DEFAULT 0,
                    matched_count INTEGER NOT NULL DEFAULT 0,
                    category_skipped INTEGER NOT NULL DEFAULT 0,
                    detail_checked INTEGER NOT NULL DEFAULT 0,
                    keyword_skipped INTEGER NOT NULL DEFAULT 0,
                    seen_skipped INTEGER NOT NULL DEFAULT 0,
                    matched_post_ids_json TEXT NOT NULL DEFAULT '[]',
                    error_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hit_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    matched_keywords_json TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    contact TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    captured_at TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()

    def _ensure_settings(self) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM settings WHERE id = 1").fetchone()
        if row is not None:
            return

        initial = load_config(self.fallback_config_path)
        self.save_settings(initial, enabled=True)

    def get_settings(self) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT config_json, enabled, updated_at FROM settings WHERE id = 1").fetchone()
        if row is None:
            raise RuntimeError("Settings row is missing.")
        config = json.loads(row["config_json"])
        config["_meta"] = {
            "enabled": bool(row["enabled"]),
            "updated_at": row["updated_at"],
        }
        return config

    def save_settings(self, config: Dict[str, Any], *, enabled: bool) -> Dict[str, Any]:
        payload = dict(config)
        payload.pop("_meta", None)
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (id, config_json, enabled, updated_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    config_json = excluded.config_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (json.dumps(payload, ensure_ascii=False), 1 if enabled else 0, now),
            )
            conn.commit()
        return self.get_settings()

    def record_run(self, report: Dict[str, Any], *, status: str, error_text: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_history (
                    status, total_posts, matched_count, category_skipped, detail_checked,
                    keyword_skipped, seen_skipped, matched_post_ids_json, error_text, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    status,
                    int(report.get("total_posts", 0)),
                    int(report.get("matched_count", 0)),
                    int(report.get("category_skipped", 0)),
                    int(report.get("detail_checked", 0)),
                    int(report.get("keyword_skipped", 0)),
                    int(report.get("seen_skipped", 0)),
                    json.dumps(report.get("matched_post_ids", []), ensure_ascii=False),
                    error_text,
                    utc_now_iso(),
                ),
            )
            conn.commit()

    def record_hit(self, post: Post, matched_keywords: List[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO hit_history (
                    source_id, matched_keywords_json, category, title, summary,
                    contact, created_at, captured_at, content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.source_id,
                    json.dumps(matched_keywords, ensure_ascii=False),
                    post.category,
                    post.title,
                    _build_summary(post.content),
                    _extract_contact(post.content),
                    post.created_at,
                    utc_now_iso(),
                    post.content,
                ),
            )
            conn.commit()

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM run_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["matched_post_ids"] = json.loads(item.pop("matched_post_ids_json"))
            result.append(item)
        return result

    def list_hits(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM hit_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["matched_keywords"] = json.loads(item.pop("matched_keywords_json"))
            result.append(item)
        return result
