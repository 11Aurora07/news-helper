from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from monitor.matcher import match_categories, match_keywords
from monitor.models import Post
from monitor.notifier import notify
from monitor.sources import enrich_post, fetch_posts
from monitor.store import SeenStore


@dataclass
class MatchResult:
    post: Post
    matched_keywords: List[str]


def run_cycle(config: Dict[str, Any], *, seen_db_path: str = "data/state.db") -> Dict[str, Any]:
    store = SeenStore(seen_db_path)
    keywords = config["keywords"]
    categories = config.get("categories", [])
    source = config["source"]
    notifiers = config.get("notifiers", {})

    posts = fetch_posts(source)
    matches: List[MatchResult] = []
    report: Dict[str, Any] = {
        "total_posts": len(posts),
        "category_skipped": 0,
        "keyword_skipped": 0,
        "seen_skipped": 0,
        "detail_checked": 0,
        "matched_count": 0,
        "matched_post_ids": [],
        "categories": categories,
        "keywords": keywords,
        "matches": matches,
    }

    for post in posts:
        if not match_categories(post, categories):
            report["category_skipped"] += 1
            continue

        if store.has_seen(post):
            report["seen_skipped"] += 1
            continue

        detailed_post = enrich_post(post, source)
        report["detail_checked"] += 1
        matched = match_keywords(detailed_post, keywords)
        if not matched:
            report["keyword_skipped"] += 1
            continue

        notify(detailed_post, matched, notifiers)
        store.mark_seen(detailed_post)
        report["matched_count"] += 1
        report["matched_post_ids"].append(detailed_post.source_id or "")
        matches.append(MatchResult(post=detailed_post, matched_keywords=list(matched)))

    return report
