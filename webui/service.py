from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from monitor.runtime import MatchResult, run_cycle
from webui.storage import AppStorage, utc_now_iso


@dataclass
class ServiceState:
    running: bool = False
    background_enabled: bool = False
    last_started_at: str = ""
    last_finished_at: str = ""
    last_error: str = ""
    last_report: Dict[str, Any] = field(default_factory=dict)


class MonitorService:
    def __init__(self, storage: AppStorage) -> None:
        self.storage = storage
        self.state = ServiceState()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._run_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(target=self._loop, name="monitor-service", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def trigger_run(self) -> Dict[str, Any]:
        return self._run_once()

    def wake(self) -> None:
        self._wake_event.set()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            settings = self.storage.get_settings()
            enabled = bool(settings.get("_meta", {}).get("enabled", True))
            self.state.background_enabled = enabled

            if enabled:
                self._run_once()

            interval = int(settings.get("poll_interval_seconds", 60))
            if interval < 15:
                interval = 15
            self._wake_event.wait(timeout=interval)
            self._wake_event.clear()

    def _run_once(self) -> Dict[str, Any]:
        with self._run_lock:
            settings = self.storage.get_settings()
            config = dict(settings)
            config.pop("_meta", None)

            self.state.running = True
            self.state.last_started_at = utc_now_iso()
            self.state.last_error = ""

            try:
                report = run_cycle(config, seen_db_path="data/state.db")
                self.state.last_report = _strip_matches(report)
                self.state.last_finished_at = utc_now_iso()
                self.storage.record_run(report, status="success")
                for match in report.get("matches", []):
                    if isinstance(match, MatchResult):
                        self.storage.record_hit(match.post, match.matched_keywords)
                return self.state.last_report
            except Exception:
                error_text = traceback.format_exc()
                self.state.last_error = error_text
                self.state.last_finished_at = utc_now_iso()
                self.storage.record_run({}, status="error", error_text=error_text)
                raise
            finally:
                self.state.running = False


def _strip_matches(report: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(report)
    cleaned.pop("matches", None)
    return cleaned
