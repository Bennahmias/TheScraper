from datetime import timezone

from the_scraper.feed_backend import caption_from_item, media_url_from_item, timestamp_from_item


def test_feed_item_parsing() -> None:
    item = {
        "taken_at": 1778097324,
        "caption": {"text": "Report antisemitism."},
        "image_versions2": {"candidates": [{"url": "https://example.com/image.jpg"}]},
    }

    assert timestamp_from_item(item).tzinfo == timezone.utc
    assert caption_from_item(item) == "Report antisemitism."
    assert media_url_from_item(item) == "https://example.com/image.jpg"
