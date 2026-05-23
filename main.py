from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict

from monitor.config import load_config
from monitor.runtime import run_cycle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="\u6821\u56ed\u5899\u5173\u952e\u8bcd\u76d1\u63a7\u5de5\u5177")
    parser.add_argument(
        "--config",
        default="config.sample.json",
        help="\u914d\u7f6e\u6587\u4ef6\u8def\u5f84",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="\u53ea\u6267\u884c\u4e00\u8f6e\u68c0\u67e5",
    )
    return parser.parse_args()


def run_once(config_path: str) -> Dict[str, Any]:
    config = load_config(config_path)
    report = run_cycle(config, seen_db_path="data/state.db")
    report["config_path"] = config_path

    print(
        f"[\u672c\u8f6e\u68c0\u67e5\u5b8c\u6210] "
        f"\u5171\u62c9\u53d6 {report['total_posts']} \u6761\u5e16\u5b50\uff0c"
        f"\u65b0\u589e\u547d\u4e2d {report['matched_count']} \u6761\uff0c"
        f"\u5206\u7c7b\u8fc7\u6ee4 {report['category_skipped']} \u6761\uff0c"
        f"\u8865\u8be6\u60c5 {report['detail_checked']} \u6761\uff0c"
        f"\u5173\u952e\u8bcd\u672a\u547d\u4e2d {report['keyword_skipped']} \u6761\uff0c"
        f"\u5df2\u901a\u77e5\u8fc7 {report['seen_skipped']} \u6761\u3002"
    )
    return report


def _write_report(status: str, report: Dict[str, Any] | None = None, error: str = "") -> None:
    path = os.environ.get("MONITOR_REPORT_PATH", "").strip()
    if not path:
        return

    payload: Dict[str, Any] = {
        "status": status,
        "error": error,
    }
    if report:
        payload.update(report)

    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)

    if not config_path.exists():
        print(f"\u914d\u7f6e\u6587\u4ef6\u4e0d\u5b58\u5728: {config_path}")
        return 1

    if args.once:
        try:
            report = run_once(str(config_path))
            _write_report("success", report)
            return 0
        except Exception:
            _write_report("error", error=traceback.format_exc())
            traceback.print_exc()
            return 1

    config = load_config(str(config_path))
    interval = int(config.get("poll_interval_seconds", 30))
    print(f"[\u901a\u77e5\u52a9\u624b\u5df2\u542f\u52a8] \u8f6e\u8be2\u95f4\u9694 {interval} \u79d2\uff0c\u914d\u7f6e\u6587\u4ef6 {config_path}")

    consecutive_failures = 0

    while True:
        try:
            report = run_once(str(config_path))
            _write_report("success", report)
            consecutive_failures = 0
        except KeyboardInterrupt:
            print("\n[\u901a\u77e5\u52a9\u624b\u5df2\u505c\u6b62]")
            return 0
        except Exception as exc:
            consecutive_failures += 1
            _write_report("error", error=traceback.format_exc())
            print(f"[\u68c0\u67e5\u5931\u8d25] \u7b2c {consecutive_failures} \u6b21\u8fde\u7eed\u5931\u8d25: {exc}")
            if consecutive_failures >= 3:
                print("[\u5efa\u8bae] \u8bf7\u4f18\u5148\u68c0\u67e5 Cookie \u662f\u5426\u5931\u6548\uff0c\u5e76\u91cd\u65b0\u6293\u5305\u66f4\u65b0\u914d\u7f6e\u3002")
            traceback.print_exc()

        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
