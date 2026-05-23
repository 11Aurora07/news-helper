from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from monitor.models import Post
from monitor.notifier import notify
from webui.service import MonitorService
from webui.storage import AppStorage


class SettingsPayload(BaseModel):
    poll_interval_seconds: int = Field(default=60, ge=15)
    keywords: list[str]
    categories: list[str] = Field(default_factory=list)
    source: Dict[str, Any]
    notifiers: Dict[str, Any]
    enabled: bool = True


class TestNotifyPayload(BaseModel):
    title: str = Field(default="测试通知")
    content: str = Field(default="这是一条来自通知助手 Web 控制台的测试消息，联系方式 wx:testnotify123")
    category: str = Field(default="测试分类")
    matched_keywords: list[str] = Field(default_factory=lambda: ["测试"])


storage = AppStorage()
service = MonitorService(storage)
app = FastAPI(title="通知助手", version="1.0.0")

STATIC_DIR = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def startup() -> None:
    service.start()


@app.on_event("shutdown")
def shutdown() -> None:
    service.stop()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def get_status() -> Dict[str, Any]:
    settings = storage.get_settings()
    runs = storage.list_runs(limit=1)
    return {
        "service": {
            "running": service.state.running,
            "enabled": bool(settings.get("_meta", {}).get("enabled", True)),
            "last_started_at": service.state.last_started_at,
            "last_finished_at": service.state.last_finished_at,
            "last_error": service.state.last_error,
            "last_report": service.state.last_report,
        },
        "settings_meta": settings.get("_meta", {}),
        "latest_run": runs[0] if runs else None,
    }


@app.get("/api/settings")
def get_settings() -> Dict[str, Any]:
    return storage.get_settings()


@app.put("/api/settings")
def update_settings(payload: SettingsPayload) -> Dict[str, Any]:
    config = payload.model_dump()
    enabled = bool(config.pop("enabled", True))
    saved = storage.save_settings(config, enabled=enabled)
    service.wake()
    return saved


@app.post("/api/run-now")
def run_now() -> Dict[str, Any]:
    try:
        report = service.trigger_run()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return report


@app.get("/api/runs")
def get_runs(limit: int = 20) -> Dict[str, Any]:
    return {"items": storage.list_runs(limit=max(1, min(limit, 100)))}


@app.get("/api/hits")
def get_hits(limit: int = 50) -> Dict[str, Any]:
    return {"items": storage.list_hits(limit=max(1, min(limit, 200)))}


@app.post("/api/test-notify")
def test_notify(payload: TestNotifyPayload) -> Dict[str, Any]:
    settings = storage.get_settings()
    config = dict(settings)
    config.pop("_meta", None)
    notifiers = config.get("notifiers", {})
    post = Post(
        source_id="test-notify",
        title=payload.title,
        content=payload.content,
        url="",
        created_at="",
        category=payload.category,
    )
    notify(post, payload.matched_keywords, notifiers)
    return {"ok": True}
