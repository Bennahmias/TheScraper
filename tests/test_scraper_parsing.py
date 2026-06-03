from the_scraper.scraper import extract_caption, extract_counts, normalize_post_url, parse_count


def test_normalize_post_url_accepts_posts_and_reels() -> None:
    assert normalize_post_url("https://www.instagram.com/p/ABC123/?utm=x") == (
        "https://www.instagram.com/p/ABC123/"
    )
    assert normalize_post_url("https://www.instagram.com/reel/XYZ789/") == (
        "https://www.instagram.com/reel/XYZ789/"
    )


def test_extract_counts_supports_suffixes() -> None:
    assert parse_count("1.2", "K") == 1200
    assert extract_counts("1,234 likes, 56 comments - adl on Instagram") == (1234, 56)


def test_extract_caption_from_og_description() -> None:
    text = '125 likes, 4 comments - adl on Instagram: "Report antisemitism when you see it."'

    assert extract_caption(text) == "Report antisemitism when you see it."
