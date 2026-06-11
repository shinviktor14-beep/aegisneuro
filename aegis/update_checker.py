"""Проверка обновлений через GitHub Releases API.

При запуске приложения запрашивает последний релиз с GitHub,
сравнивает версию с текущей и предлагает скачать APK.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

GITHUB_REPO = "shinviktor14-beep/aegisneuro"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def get_latest_release() -> Optional[dict]:
    """Вернуть dict с 'tag', 'apk_url', 'body' или None при ошибке."""
    try:
        req = urllib.request.Request(
            RELEASES_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "AegisNeuro"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        tag = data.get("tag_name", "")
        apk_url = None
        for asset in data.get("assets", []):
            if asset.get("name", "").endswith(".apk"):
                apk_url = asset.get("browser_download_url")
                break

        return {"tag": tag, "apk_url": apk_url, "body": data.get("body", "")}
    except Exception as exc:  # noqa: BLE001
        log.debug(f"update check failed: {exc}")
        return None


def check_for_update(current_version: str) -> Optional[dict]:
    """Сравнить текущую версию с последним релизом.

    Возвращает dict с 'tag', 'apk_url' если обновление доступно,
    иначе None.
    """
    release = get_latest_release()
    if release is None:
        return None

    # Сравниваем числовые части (v8 → 8, v1.0.0 → 1.0.0)
    def _ver(s: str) -> list[int]:
        return [int(x) for x in s.lstrip("v").split(".") if x.isdigit()]

    if _ver(release["tag"]) > _ver(current_version):
        return release
    return None