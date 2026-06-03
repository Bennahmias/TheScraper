from datetime import UTC, datetime
from pathlib import Path

from the_scraper.models import InstagramPost, PostAnalysis, ScrapeDataset
from the_scraper.report import generate_report


def test_generate_report_uses_hebrew_labels(tmp_path: Path) -> None:
    dataset = ScrapeDataset(
        since=datetime(2026, 5, 1, tzinfo=UTC),
        posts=[
            InstagramPost(
                id="adl:test",
                account="adl",
                account_url="https://www.instagram.com/adl/",
                post_url="https://www.instagram.com/p/test/",
                caption="Report antisemitism.",
                analysis=PostAnalysis(category="Reporting", tone="Urgent"),
            )
        ],
    )
    output = tmp_path / "report.html"

    generate_report(dataset, output)

    html = output.read_text(encoding="utf-8")
    assert 'lang="he" dir="rtl"' in html
    assert "ניתוח פעילות אינסטגרם אזורית של ADL" in html
    assert "דיווח" in html
    assert "מסקנה ניהולית קצרה" in html
