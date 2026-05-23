from __future__ import annotations

from typing import Iterable, List

from monitor.models import Post


def match_keywords(post: Post, keywords: Iterable[str]) -> List[str]:
    text = post.search_text.casefold()
    matched = []
    for keyword in keywords:
        normalized = str(keyword).strip()
        if normalized and normalized.casefold() in text:
            matched.append(normalized)
    return matched


def match_categories(post: Post, categories: Iterable[str]) -> bool:
    normalized_categories = [str(category).strip() for category in categories if str(category).strip()]
    if not normalized_categories:
        return True

    post_category = post.category.casefold()
    return any(category.casefold() in post_category for category in normalized_categories)
