from pathlib import Path

from the_scraper.instaloader_backend import first_downloaded_media


def test_first_downloaded_media_finds_shortcode_image(tmp_path: Path) -> None:
    (tmp_path / "ABC123.txt").write_text("caption", encoding="utf-8")
    image = tmp_path / "2026-05-01_ABC123.jpg"
    image.write_bytes(b"fake")

    assert first_downloaded_media(tmp_path, "ABC123") == image
