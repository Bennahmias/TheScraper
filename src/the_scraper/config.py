from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def default_since_date(today: date | None = None) -> date:
    current = today or date.today()
    return date(current.year, 5, 1)


def normalize_instagram_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url:
        return ""

    parsed = urlparse(raw_url if raw_url.startswith("http") else f"https://{raw_url}")
    path = parsed.path.strip("/")
    if not path:
        return ""

    username = path.split("/")[0]
    return urlunparse(("https", "www.instagram.com", f"/{username}/", "", "", ""))


def username_from_url(url: str) -> str:
    parsed = urlparse(normalize_instagram_url(url))
    return parsed.path.strip("/").split("/")[0]


def load_account_urls(path: Path) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        normalized = normalize_instagram_url(line)
        if normalized and normalized not in seen:
            urls.append(normalized)
            seen.add(normalized)

    return urls
