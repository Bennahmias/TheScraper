from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import instaloader

from .config import username_from_url
from .models import InstagramPost, ScrapeDataset


def scrape_with_instaloader(
    account_urls: list[str],
    since: date,
    output_dir: Path,
    max_posts_per_account: int = 30,
) -> ScrapeDataset:
    dataset = ScrapeDataset(since=datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc))
    media_root = output_dir / "media"
    media_root.mkdir(parents=True, exist_ok=True)

    loader = instaloader.Instaloader(
        download_pictures=True,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        dirname_pattern=str(media_root / "{profile}"),
        filename_pattern="{shortcode}",
    )

    for account_url in account_urls:
        account = username_from_url(account_url)
        count = 0
        try:
            profile = instaloader.Profile.from_username(loader.context, account)
            for post in profile.get_posts():
                timestamp = post.date_utc.replace(tzinfo=timezone.utc)
                if timestamp.date() < since:
                    break
                if count >= max_posts_per_account:
                    break

                target = media_root / account
                loader.download_post(post, target=account)
                media_path = first_downloaded_media(target, post.shortcode)

                dataset.posts.append(
                    InstagramPost(
                        id=f"{account}:{post.shortcode}",
                        account=account,
                        account_url=account_url,
                        post_url=f"https://www.instagram.com/p/{post.shortcode}/",
                        timestamp=timestamp,
                        caption=post.caption or "",
                        likes=post.likes,
                        comments=post.comments,
                        media_url=post.url,
                        media_path=str(media_path) if media_path else None,
                    )
                )
                count += 1
        except Exception as exc:  # noqa: BLE001 - keep progress across accounts.
            dataset.warnings.append(f"Instaloader error for {account}: {exc}")

    return dataset


def first_downloaded_media(directory: Path, shortcode: str) -> Path | None:
    if not directory.exists():
        return None

    candidates = sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and shortcode in path.name
        and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    return candidates[0] if candidates else None
