from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    report_path = Path(os.environ.get("MONITOR_REPORT_PATH", "data/monitor_report.json"))
    if not report_path.exists():
        print("## Monitor Report")
        print()
        print("No report file was generated.")
        return

    report = json.loads(report_path.read_text(encoding="utf-8"))
    print("## Monitor Report")
    print()
    print(f"- Status: `{report.get('status', 'unknown')}`")

    if report.get("status") != "success":
        error = str(report.get("error", "")).strip()
        print(f"- Error: `{error[:500] or 'unknown'}`")
        return

    print(f"- Total posts: `{report.get('total_posts', 0)}`")
    print(f"- New matches: `{report.get('matched_count', 0)}`")
    print(f"- Category skipped: `{report.get('category_skipped', 0)}`")
    print(f"- Keyword skipped: `{report.get('keyword_skipped', 0)}`")
    print(f"- Seen skipped: `{report.get('seen_skipped', 0)}`")

    matched_post_ids = [post_id for post_id in report.get("matched_post_ids", []) if post_id]
    if matched_post_ids:
        print(f"- Matched post IDs: `{', '.join(matched_post_ids)}`")
    else:
        print("- Matched post IDs: `none`")


if __name__ == "__main__":
    main()
