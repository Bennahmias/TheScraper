from datetime import UTC, datetime
from pathlib import Path

from the_scraper.brief import generate_manager_brief
from the_scraper.models import InstagramPost, PostAnalysis, ScrapeDataset


def test_generate_manager_brief(tmp_path: Path) -> None:
    dataset = ScrapeDataset(
        since=datetime(2026, 5, 1, tzinfo=UTC),
        posts=[
            InstagramPost(
                id="adlcalifornia:DYF-UFuEqVp",
                account="adlcalifornia",
                account_url="https://www.instagram.com/adlcalifornia/",
                post_url="https://www.instagram.com/p/test/",
                caption="Report antisemitism.",
                analysis=PostAnalysis(
                    category="Reporting",
                    strategy="הפניה לדיווח על אירועים אנטישמיים.",
                    equips_followers=True,
                ),
            )
        ],
    )
    html = tmp_path / "brief.html"
    md = tmp_path / "brief.md"

    generate_manager_brief(dataset, html, md)

    assert "השורה התחתונה" in md.read_text(encoding="utf-8")
    markdown = md.read_text(encoding="utf-8")
    html_text = html.read_text(encoding="utf-8")
    assert "adlcalifornia (קליפורניה)" in markdown
    assert "קישורים רלוונטיים" in markdown
    assert "הערה למנהל" not in markdown
    assert "תקציר מנהלים" in html_text
    assert "adlcalifornia (קליפורניה)" in html_text
    assert "הערה למנהל" not in html_text
    assert '<a href="https://www.instagram.com/p/test/" target="_blank" rel="noreferrer">פוסט</a>' in html_text
    assert '<img src=' in html_text
