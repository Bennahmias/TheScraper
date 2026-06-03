from datetime import date
from pathlib import Path

from the_scraper.config import default_since_date, load_account_urls, normalize_instagram_url, username_from_url


def test_normalize_instagram_url_strips_tracking_query() -> None:
    url = "https://www.instagram.com/adlmichigan?igsh=abc"

    assert normalize_instagram_url(url) == "https://www.instagram.com/adlmichigan/"
    assert username_from_url(url) == "adlmichigan"


def test_load_account_urls_deduplicates(tmp_path: Path) -> None:
    path = tmp_path / "urls.txt"
    path.write_text(
        "https://www.instagram.com/adlmichigan?igsh=abc\n"
        "https://www.instagram.com/adlmichigan/\n"
        "# comment\n",
        encoding="utf-8",
    )

    assert load_account_urls(path) == ["https://www.instagram.com/adlmichigan/"]


def test_default_since_date_uses_may_first_of_current_year() -> None:
    assert default_since_date(date(2026, 6, 3)) == date(2026, 5, 1)
