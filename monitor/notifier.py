from __future__ import annotations

import base64
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List

from monitor.models import Post

LABEL_HIT = "\u547d\u4e2d\u5173\u952e\u8bcd"
LABEL_CATEGORY = "\u5206\u7c7b"
LABEL_POST_ID = "\u5e16\u5b50ID"
LABEL_CONTACT = "\u8054\u7cfb\u65b9\u5f0f"
LABEL_TITLE = "\u6807\u9898"
LABEL_SUMMARY = "\u6458\u8981"
LABEL_TIME = "\u65f6\u95f4"
LABEL_OPEN_IN_MINIAPP = "\u5c0f\u7a0b\u5e8f\u5185\u67e5\u770b"
LABEL_LOOKUP_HINT = "\u68c0\u7d22\u63d0\u793a"
TEXT_ASSISTANT = "\u901a\u77e5\u52a9\u624b"
TEXT_FOUND_POST = "\u68c0\u6d4b\u5230\u65b0\u5e16\u5b50"
TEXT_MINIAPP_NAME = "\u4e91\u4e0a\u6821\u53cb\u5708"
TEXT_OPEN_IN_MINIAPP = (
    "\u5fae\u4fe1\u91cc\u6253\u5f00 `\u4e91\u4e0a\u6821\u53cb\u5708` \u540e\u641c\u7d22\u4e0b\u9762\u4fe1\u606f"
)
TEXT_LOOKUP_FALLBACK = "\u8bf7\u6309\u5e16\u5b50\u53d1\u5e03\u65f6\u95f4\u9644\u8fd1\u5185\u5bb9\u624b\u52a8\u67e5\u627e"


def notify(post: Post, matched_keywords: Iterable[str], notifier_config: Dict) -> None:
    matched_list = [keyword for keyword in matched_keywords if keyword]
    matched_text = ", ".join(matched_list) or "-"
    share_url = _get_shareable_url(post.url)
    contact = _extract_contact(post.content)
    summary = _build_summary(post.content)
    display_title = _build_display_title(post, summary)
    lookup_hint = _build_lookup_hint(post, matched_list, contact, summary)
    saved_code_path = _save_miniapp_code_image(post) if post.miniapp_code_data_url else ""

    if notifier_config.get("console", True):
        print("=" * 60)
        print(f"[{LABEL_HIT}] {matched_text}")
        print(f"{LABEL_CATEGORY}: {post.category or '-'}")
        print(f"{LABEL_POST_ID}: {post.source_id or '-'}")
        if contact:
            print(f"{LABEL_CONTACT}: {contact}")
        print(f"{LABEL_TITLE}: {display_title}")
        print(f"{LABEL_SUMMARY}: {summary or '-'}")
        if not share_url:
            print(f"\u67e5\u770b\u65b9\u5f0f: \u8bf7\u5728\u5fae\u4fe1\u5c0f\u7a0b\u5e8f\u201c{TEXT_MINIAPP_NAME}\u201d\u5185\u641c\u7d22")
            print(f"{LABEL_LOOKUP_HINT}: {lookup_hint}")
        print(f"{LABEL_TIME}: {post.created_at or '-'}")

    if notifier_config.get("windows_popup"):
        _windows_popup(display_title, matched_text, summary)

    pushplus = notifier_config.get("pushplus", {})
    if pushplus.get("enabled") and pushplus.get("token"):
        _send_pushplus(post, matched_list, pushplus, saved_code_path)

    webhook = notifier_config.get("webhook", {})
    if webhook.get("enabled") and webhook.get("url"):
        _send_webhook(post, matched_list, webhook, saved_code_path)


def _windows_popup(display_title: str, matched_text: str, summary: str) -> None:
    title = TEXT_ASSISTANT
    message = f"{LABEL_HIT}: {matched_text}\n{display_title or summary or TEXT_FOUND_POST}"
    safe_title = title.replace("'", "''")
    safe_message = message.replace("'", "''")
    command = (
        "$wshell = New-Object -ComObject WScript.Shell; "
        f"$wshell.Popup('{safe_message}', 8, '{safe_title}', 64) | Out-Null"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )


def _send_pushplus(
    post: Post,
    matched_keywords: Iterable[str],
    pushplus_config: Dict,
    saved_code_path: str,
) -> None:
    title = _build_push_title(matched_keywords)
    content = _build_push_content(post, matched_keywords, saved_code_path)
    payload = {
        "token": pushplus_config["token"],
        "title": title,
        "content": content,
        "template": pushplus_config.get("template", "markdown"),
    }
    topic = str(pushplus_config.get("topic", "")).strip()
    if topic:
        payload["topic"] = topic

    response = _post_json(
        "https://www.pushplus.plus/send",
        payload,
        {"Content-Type": "application/json"},
        error_prefix="PushPlus \u901a\u77e5\u5931\u8d25",
    )
    if response:
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            print(f"[PushPlus \u8fd4\u56de] {response[:300]}")
            return

        code = parsed.get("code")
        if code != 200:
            print(f"[PushPlus \u8fd4\u56de\u5f02\u5e38] code={code} msg={parsed.get('msg')} data={parsed.get('data')}")


def _send_webhook(
    post: Post,
    matched_keywords: Iterable[str],
    webhook_config: Dict,
    saved_code_path: str,
) -> None:
    payload = {
        "matched_keywords": list(matched_keywords),
        "post": {
            "id": post.source_id,
            "category": post.category,
            "title": post.title,
            "content": post.content,
            "url": post.url,
            "created_at": post.created_at,
            "miniapp_code_saved_path": saved_code_path,
        },
    }

    headers = webhook_config.get("headers", {})
    _post_json(
        webhook_config["url"],
        payload,
        headers,
        method=webhook_config.get("method", "POST"),
        error_prefix="Webhook \u901a\u77e5\u5931\u8d25",
    )


def _build_push_title(matched_keywords: Iterable[str]) -> str:
    matched = _dedupe(keyword for keyword in matched_keywords if keyword)
    if not matched:
        return "\u4e91\u4e0a\u6821\u53cb\u5708\u65b0\u5e16\u63d0\u9192"
    if len(matched) == 1:
        return f"\u4e91\u4e0a\u6821\u53cb\u5708\u65b0\u5e16: {matched[0]}"
    return f"\u4e91\u4e0a\u6821\u53cb\u5708\u65b0\u5e16: {matched[0]} \u7b49{len(matched)}\u4e2a\u5173\u952e\u8bcd"


def _build_push_content(post: Post, matched_keywords: Iterable[str], saved_code_path: str) -> str:
    matched_list = [keyword for keyword in matched_keywords if keyword]
    matched_text = ", ".join(matched_list) or "-"
    share_url = _get_shareable_url(post.url)
    contact = _extract_contact(post.content)
    summary = _build_summary(post.content)
    display_title = _build_display_title(post, summary)
    lookup_hint = _build_lookup_hint(post, matched_list, contact, summary)

    lines = [f"**{LABEL_CATEGORY}**: {post.category or '-'}"]
    if post.source_id:
        lines.append(f"**{LABEL_POST_ID}**: {post.source_id}")
    if contact:
        lines.append(f"**{LABEL_CONTACT}**: `{contact}`")
    lines.extend(
        [
            f"**{LABEL_TITLE}**: {display_title}",
            f"**{LABEL_SUMMARY}**: {summary or '-'}",
            f"**{LABEL_TIME}**: {post.created_at or '-'}",
        ]
    )
    if not share_url:
        lines.extend(
            [
                f"**{LABEL_OPEN_IN_MINIAPP}**: {TEXT_OPEN_IN_MINIAPP}",
                f"**{LABEL_LOOKUP_HINT}**: `{lookup_hint}`",
            ]
        )
    elif matched_text != "-":
        lines.append(f"**{LABEL_HIT}**: {matched_text}")
    return "\n\n".join(lines)


def _build_display_title(post: Post, summary: str) -> str:
    title = (post.title or "").strip()
    category = (post.category or "").strip()
    if title and title != category:
        return title
    if summary:
        return _truncate(summary, 24)
    return "-"


def _build_lookup_hint(post: Post, matched_keywords: List[str], contact: str, summary: str) -> str:
    parts: List[str] = []
    if post.source_id:
        parts.append(f"ID {post.source_id}")
    if matched_keywords:
        parts.append(f"\u5173\u952e\u8bcd {'/'.join(_dedupe(matched_keywords))}")
    if contact:
        parts.append(f"\u8054\u7cfb {contact}")
    snippet = _build_search_snippet(summary)
    if snippet:
        parts.append(f"\u5185\u5bb9 {snippet}")
    if not parts:
        return TEXT_LOOKUP_FALLBACK
    return " | ".join(parts)


def _build_search_snippet(text: str, limit: int = 18) -> str:
    if not text:
        return ""
    snippet = re.sub(r"\s+", " ", text).strip()
    return _truncate(snippet, limit)


def _get_shareable_url(url: str) -> str:
    if not url:
        return ""

    normalized = url.strip().lower()
    if "/article/article/info" in normalized:
        return ""
    return url.strip()


def _extract_contact(text: str) -> str:
    if not text:
        return ""

    normalized = text.replace("\uff1a", ":").replace(" ", "").replace("\u3000", "")
    patterns = [
        r"(?:\u8054\u7cfb\u65b9\u5f0f|\u8054\u7cfb|\u52a0|vx|wx|\u5fae\u4fe1)[:]?(?:vx|wx|\u5fae\u4fe1)?[:]?(?:[:\uff1a])?([a-zA-Z][a-zA-Z0-9_-]{5,24})",
        r"(?:vx|wx)[:]?(?:[:\uff1a])?([a-zA-Z][a-zA-Z0-9_-]{5,24})",
        r"(?:\u8054\u7cfb\u65b9\u5f0f|\u8054\u7cfb|\u624b\u673a|\u7535\u8bdd)[:]?(?:[:\uff1a])?([1-9][0-9]{10})",
        r"(1[3-9][0-9]{9})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _build_summary(text: str, limit: int = 80) -> str:
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", text).strip()
    return _truncate(compact, limit)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _save_miniapp_code_image(post: Post) -> str:
    if not post.miniapp_code_data_url or not post.source_id:
        return ""

    text = post.miniapp_code_data_url.replace("\\/", "/").strip()
    if "," not in text:
        return ""

    header, b64 = text.split(",", 1)
    if not header.startswith("data:image/"):
        return ""

    image_ext = "jpg"
    if "png" in header.lower():
        image_ext = "png"

    padding = "=" * ((4 - len(b64) % 4) % 4)
    try:
        raw = base64.b64decode(b64 + padding)
    except Exception:
        return ""

    output_dir = Path("data") / "miniapp_codes"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"post_{post.source_id}.{image_ext}"
    path.write_bytes(raw)
    return str(path)


def _post_json(
    url: str,
    payload: Dict,
    headers: Dict,
    *,
    method: str = "POST",
    error_prefix: str,
) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        print(f"[{error_prefix}] {exc}")
        return ""
