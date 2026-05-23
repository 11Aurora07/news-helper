from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from monitor.models import Post
from monitor.session import SessionStore


def fetch_posts(source_config: Dict[str, Any]) -> List[Post]:
    source_type = source_config.get("type")
    if source_type == "sample_json":
        return _load_sample_json(source_config)
    if source_type == "http_json":
        return _load_http_json(source_config)
    raise ValueError(f"Unsupported source type: {source_type}")


def enrich_post(post: Post, source_config: Dict[str, Any]) -> Post:
    detail_config = source_config.get("detail")
    code_config = source_config.get("miniapp_code")

    detailed_post = post
    if detail_config and post.source_id:
        detailed_post = _enrich_post_detail(post, source_config, detail_config)

    if code_config and detailed_post.source_id:
        detailed_post = _enrich_post_miniapp_code(detailed_post, source_config, code_config)

    return detailed_post


def _enrich_post_detail(post: Post, source_config: Dict[str, Any], detail_config: Dict[str, Any]) -> Post:
    try:
        raw = _request_json(_build_request_config(source_config, detail_config, post))
    except Exception as exc:
        print(f"[详情补拉失败] 帖子ID {post.source_id}: {exc}")
        return post

    field_map = detail_config.get("field_map", {})
    detailed_post = _normalize_post(raw, field_map)

    return Post(
        source_id=post.source_id or detailed_post.source_id,
        title=detailed_post.title or post.title,
        content=detailed_post.content or post.content,
        url=post.url or detailed_post.url,
        created_at=detailed_post.created_at or post.created_at,
        category=detailed_post.category or post.category,
        miniapp_code_data_url=post.miniapp_code_data_url,
    )


def _enrich_post_miniapp_code(post: Post, source_config: Dict[str, Any], code_config: Dict[str, Any]) -> Post:
    try:
        raw = _request_json(_build_request_config(source_config, code_config, post))
    except Exception as exc:
        print(f"[小程序码获取失败] 帖子ID {post.source_id}: {exc}")
        return post

    data_url = _extract_miniapp_code_data_url(raw, code_config)
    if not data_url:
        return post

    return Post(
        source_id=post.source_id,
        title=post.title,
        content=post.content,
        url=post.url,
        created_at=post.created_at,
        category=post.category,
        miniapp_code_data_url=data_url,
    )


def _extract_miniapp_code_data_url(raw: Any, code_config: Dict[str, Any]) -> str:
    field_name = str(code_config.get("field", "xcxCode")).strip() or "xcxCode"
    json_path = str(code_config.get("json_path", "data")).strip()
    try:
        payload = _resolve_json_path(raw, json_path) if json_path else raw
    except ValueError:
        payload = raw

    if not isinstance(payload, dict):
        return ""

    value = payload.get(field_name)
    if not value:
        return ""

    text = str(value).replace("\\/", "/").strip()
    if not text.startswith("data:image/"):
        return ""
    return text


def _load_sample_json(source_config: Dict[str, Any]) -> List[Post]:
    path = Path(source_config["path"])
    with path.open("r", encoding="utf-8") as fh:
        items = json.load(fh)
    return [_normalize_post(item) for item in items]


def _load_http_json(source_config: Dict[str, Any]) -> List[Post]:
    payload = _request_json(source_config)
    items = _resolve_json_path(payload, source_config.get("json_path", ""))
    if not isinstance(items, list):
        raise RuntimeError(
            "Resolved json_path does not point to a list. "
            "The API response shape may have changed, or the request may not have returned the expected data."
        )

    if not items and source_config.get("fail_on_empty", False):
        raise RuntimeError(
            "The API returned an empty list. "
            "If this is unexpected, the Cookie may have expired or the request may have been rate-limited."
        )

    field_map = source_config.get("field_map", {})
    return [_normalize_post(item, field_map) for item in items]


def _request_json(source_config: Dict[str, Any]) -> Any:
    method = source_config.get("method", "GET")
    headers = dict(source_config.get("headers", {}))
    url = _build_url(source_config["url"], source_config.get("params", {}))
    data = _build_request_data(source_config)
    session_store = _build_session_store(source_config)

    if session_store is not None:
        _inject_session_cookie(headers, source_config, session_store)

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if session_store is not None:
                _persist_session_cookie(response, source_config, session_store)
            encoding = source_config.get("response_encoding") or response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(encoding))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP request failed: {exc.code} {exc.reason}. "
            f"Check whether Cookie/headers have expired. Response: {detail[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network request failed: {exc}") from exc


def _build_request_config(
    source_config: Dict[str, Any],
    request_config: Dict[str, Any],
    post: Post,
) -> Dict[str, Any]:
    config = dict(request_config)
    if "headers" not in config:
        config["headers"] = dict(source_config.get("headers", {}))
    if "session_store_path" not in config:
        config["session_store_path"] = source_config.get("session_store_path", "")
    if "session_cookie_name" not in config:
        config["session_cookie_name"] = source_config.get("session_cookie_name", "")

    body = config.get("body")
    if isinstance(body, dict):
        config["body"] = _render_object_template(body, post)
    params = config.get("params")
    if isinstance(params, dict):
        config["params"] = _render_object_template(params, post)
    return config


def _render_object_template(data: Dict[str, Any], post: Post) -> Dict[str, Any]:
    rendered: Dict[str, Any] = {}
    for key, value in data.items():
        rendered[key] = _render_value_template(value, post)
    return rendered


def _render_value_template(value: Any, post: Post) -> Any:
    if isinstance(value, str):
        return (
            value.replace("{id}", post.source_id)
            .replace("{title}", post.title)
            .replace("{content}", post.content)
            .replace("{category}", post.category)
        )
    return value


def _build_url(base_url: str, params: Dict[str, Any]) -> str:
    if not params:
        return base_url

    query = urllib.parse.urlencode(_flatten_params(params), doseq=True)
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{query}"


def _flatten_params(params: Dict[str, Any]) -> Dict[str, Any]:
    flattened: Dict[str, Any] = {}
    for key, value in params.items():
        flattened[key] = value
    return flattened


def _build_request_data(source_config: Dict[str, Any]) -> bytes | None:
    body_mode = source_config.get("body_mode", "json")

    if "body_raw" in source_config:
        raw = source_config["body_raw"]
        return str(raw).encode(source_config.get("request_encoding", "utf-8"))

    if "body_form" in source_config:
        return urllib.parse.urlencode(source_config["body_form"], doseq=True).encode(
            source_config.get("request_encoding", "utf-8")
        )

    body = source_config.get("body")
    if body is None:
        return None

    encoding = source_config.get("request_encoding", "utf-8")
    if body_mode == "json":
        return json.dumps(body, ensure_ascii=False).encode(encoding)
    if body_mode == "form":
        return urllib.parse.urlencode(body, doseq=True).encode(encoding)
    if body_mode == "raw":
        return str(body).encode(encoding)

    raise ValueError(f"Unsupported body_mode: {body_mode}")


def _build_session_store(source_config: Dict[str, Any]) -> SessionStore | None:
    session_path = source_config.get("session_store_path", "")
    if not session_path:
        return None
    return SessionStore(str(session_path))


def _inject_session_cookie(headers: Dict[str, str], source_config: Dict[str, Any], session_store: SessionStore) -> None:
    cookie_name = str(source_config.get("session_cookie_name", "")).strip()
    if not cookie_name:
        return

    stored_value = session_store.get_cookie(cookie_name)
    if not stored_value:
        return

    current_cookie = headers.get("Cookie") or headers.get("cookie") or ""
    updated_cookie = _upsert_cookie(current_cookie, cookie_name, stored_value)
    headers["Cookie"] = updated_cookie
    headers.pop("cookie", None)


def _persist_session_cookie(response: Any, source_config: Dict[str, Any], session_store: SessionStore) -> None:
    cookie_name = str(source_config.get("session_cookie_name", "")).strip()
    if not cookie_name:
        return

    set_cookie_values = response.headers.get_all("Set-Cookie", [])
    for raw in set_cookie_values:
        parsed_name, parsed_value = _parse_set_cookie(raw)
        if parsed_name == cookie_name and parsed_value:
            session_store.set_cookie(cookie_name, parsed_value)
            return


def _upsert_cookie(cookie_header: str, name: str, value: str) -> str:
    cookies: List[Tuple[str, str]] = []
    found = False

    for part in cookie_header.split(";"):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        key, current_value = piece.split("=", 1)
        key = key.strip()
        current_value = current_value.strip()
        if key == name:
            cookies.append((key, value))
            found = True
        else:
            cookies.append((key, current_value))

    if not found:
        cookies.append((name, value))

    return "; ".join(f"{key}={cookie_value}" for key, cookie_value in cookies)


def _parse_set_cookie(raw: str) -> Tuple[str, str]:
    first = raw.split(";", 1)[0].strip()
    if "=" not in first:
        return "", ""
    name, value = first.split("=", 1)
    return name.strip(), value.strip()


def _resolve_json_path(data: Any, json_path: str) -> Any:
    if not json_path:
        return data

    current = data
    for part in json_path.split("."):
        current = _resolve_path_segment(current, part)
    return current


def _normalize_post(raw: Dict[str, Any], field_map: Dict[str, str] | None = None) -> Post:
    field_map = field_map or {}

    def pick(name: str) -> str:
        key = field_map.get(name, name)
        if not key:
            return ""
        try:
            value = _resolve_json_path(raw, key)
        except ValueError:
            value = ""
        return "" if value is None else str(value)

    source_id = pick("id")
    title = pick("title")
    content = pick("content")
    url = pick("url")
    created_at = pick("created_at")
    category = pick("category")

    if not url:
        url_template = field_map.get("url_template", "")
        if url_template:
            url = _render_template(url_template, raw)

    return Post(
        source_id=source_id,
        title=title,
        content=content,
        url=url,
        created_at=created_at,
        category=category,
    )


def _resolve_path_segment(current: Any, part: str) -> Any:
    if isinstance(current, dict):
        return current.get(part)

    if isinstance(current, list):
        if not part.isdigit():
            raise ValueError(f"Cannot resolve list segment '{part}'.")
        index = int(part)
        if index >= len(current):
            return None
        return current[index]

    raise ValueError(f"Cannot resolve json_path segment '{part}'.")


def _render_template(template: str, raw: Dict[str, Any]) -> str:
    rendered = template
    for match in set(re.findall(r"\{([^{}]+)\}", template)):
        try:
            value = _resolve_json_path(raw, match)
        except ValueError:
            value = ""
        replacement = "" if value is None else str(value)
        rendered = rendered.replace(f"{{{match}}}", replacement)
    return rendered
