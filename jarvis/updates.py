"""Read-only official release discovery. No background download or self-update."""
from __future__ import annotations

import json
import re
from urllib.request import Request, urlopen

RELEASE_API = "https://api.github.com/repos/tuckusss/Jarvis/releases/latest"
RELEASE_PAGE_PREFIX = "https://github.com/tuckusss/Jarvis/releases/tag/"


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
    return tuple(map(int, match.groups())) if match else None


def evaluate_release(data: dict, current_version: str) -> dict:
    """Ignore draft, prerelease, unsigned development CI and unexpected URLs."""
    current = parse_version(current_version)
    if current is None:
        raise ValueError("Unrecognized running JARVIS version")
    if data.get("draft") or data.get("prerelease"):
        return {"update": False, "reason": "No stable release"}
    tag = data.get("tag_name", "")
    published = parse_version(tag)
    url = data.get("html_url", "")
    if (not published or not isinstance(url, str)
            or not url.startswith(RELEASE_PAGE_PREFIX)
            or url != RELEASE_PAGE_PREFIX + tag):
        return {"update": False, "reason": "No verified official release"}
    return {
        "update": published > current,
        "version": tag,
        "url": url,
        "manual_only": True,
    }


def check_official_release(current_version: str = "0.8.0") -> dict:
    request = Request(RELEASE_API, headers={
        "User-Agent": "JARVIS-Desktop-Update-Checker",
        "Accept": "application/vnd.github+json",
    })
    with urlopen(request, timeout=9) as response:
        payload = json.load(response)
    return evaluate_release(payload, current_version)
