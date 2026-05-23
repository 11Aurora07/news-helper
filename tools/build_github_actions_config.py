from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    template_path = Path("config.miniprogram.template.json")
    output_path = Path("config.generated.json")

    config = json.loads(template_path.read_text(encoding="utf-8"))

    session_cookie = os.environ["YS_SESSION_COOKIE"].strip()
    pushplus_token = os.environ["PUSHPLUS_TOKEN"].strip()

    source = config["source"]
    source["headers"]["Cookie"] = f'ys7_ysxy_session={session_cookie}'
    source["session_store_path"] = "data/session.json"

    notifiers = config.setdefault("notifiers", {})
    notifiers["console"] = True
    notifiers["windows_popup"] = False

    pushplus = notifiers.setdefault("pushplus", {})
    pushplus["enabled"] = True
    pushplus["token"] = pushplus_token

    poll_interval = os.environ.get("POLL_INTERVAL_SECONDS", "").strip()
    if poll_interval:
        config["poll_interval_seconds"] = int(poll_interval)

    output_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
