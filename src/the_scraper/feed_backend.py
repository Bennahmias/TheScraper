from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import Page, async_playwright

from .config import username_from_url
from .models import InstagramPost, ScrapeDataset


class InstagramFeedBackend:
    def __init__(
        self,
        output_dir: Path,
        max_posts_per_account: int = 80,
        headless: bool = True,
        delay_seconds: float = 2.0,
    ) -> None:
        self.output_dir = output_dir
        self.max_posts_per_account = max_posts_per_account
        self.headless = headless
        self.delay_seconds = delay_seconds

    async def scrape_accounts(self, account_urls: list[str], since: date) -> ScrapeDataset:
        dataset = ScrapeDataset(since=datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            page = await context.new_page()

            for account_url in account_urls:
                account = username_from_url(account_url)
                try:
                    posts = await self._scrape_account(page, account, account_url, since)
                    dataset.posts.extend(posts)
                    if not posts:
                        dataset.warnings.append(
                            f"No May-onward posts found for {account} through Instagram feed endpoint."
                        )
                except Exception as exc:  # noqa: BLE001 - keep progress across accounts.
                    dataset.warnings.append(f"Feed endpoint error for {account}: {exc}")
                await asyncio.sleep(self.delay_seconds)

            await context.close()
            await browser.close()

        return dataset

    async def _scrape_account(
        self,
        page: Page,
        account: str,
        account_url: str,
        since: date,
    ) -> list[InstagramPost]:
        await page.goto(account_url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(1_800)

        posts: list[InstagramPost] = []
        seen_ids: set[str] = set()
        max_id: str | None = None
        should_continue = True

        while should_continue and len(posts) < self.max_posts_per_account:
            payload = await fetch_feed_page(page, account, max_id=max_id)
            items = payload.get("items") or []
            if not items:
                break

            page_timestamps: list[datetime] = []
            for item in items:
                post = await self._post_from_item(item, account, account_url)
                if post is None:
                    continue
                if post.timestamp:
                    page_timestamps.append(post.timestamp)
                if post.timestamp and post.timestamp.date() < since:
                    continue
                if post.id in seen_ids:
                    continue
                posts.append(post)
                seen_ids.add(post.id)
                if len(posts) >= self.max_posts_per_account:
                    break

            if page_timestamps and max(page_timestamps).date() < since:
                should_continue = False

            max_id = payload.get("next_max_id")
            if not payload.get("more_available") or not max_id:
                break
            await asyncio.sleep(self.delay_seconds)

        return posts

    async def _post_from_item(
        self,
        item: dict[str, Any],
        account: str,
        account_url: str,
    ) -> InstagramPost | None:
        code = item.get("code")
        if not code:
            return None

        timestamp = timestamp_from_item(item)
        caption = caption_from_item(item)
        media_url = media_url_from_item(item)
        media_path = await self._download_media(account, code, media_url) if media_url else None

        return InstagramPost(
            id=f"{account}:{code}",
            account=account,
            account_url=account_url,
            post_url=f"https://www.instagram.com/p/{code}/",
            timestamp=timestamp,
            caption=caption,
            likes=item.get("like_count"),
            comments=item.get("comment_count"),
            media_url=media_url,
            media_path=str(media_path) if media_path else None,
        )

    async def _download_media(self, account: str, post_id: str, media_url: str) -> Path | None:
        target_dir = self.output_dir / "media" / account
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{post_id}.jpg"

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(media_url)
                response.raise_for_status()
                target.write_bytes(response.content)
                return target
        except httpx.HTTPError:
            return None


async def fetch_feed_page(page: Page, account: str, max_id: str | None = None) -> dict[str, Any]:
    return await page.evaluate(
        """async ({ account, maxId }) => {
          const params = new URLSearchParams({ count: "12" });
          if (maxId) params.set("max_id", maxId);
          const response = await fetch(`/api/v1/feed/user/${account}/username/?${params}`, {
            credentials: "include",
            headers: { "x-ig-app-id": "936619743392459" },
          });
          if (!response.ok) {
            throw new Error(`feed status ${response.status}`);
          }
          return await response.json();
        }""",
        {"account": account, "maxId": max_id},
    )


def timestamp_from_item(item: dict[str, Any]) -> datetime | None:
    value = item.get("taken_at")
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def caption_from_item(item: dict[str, Any]) -> str:
    caption = item.get("caption")
    if isinstance(caption, dict):
        return str(caption.get("text") or "").strip()
    return ""


def media_url_from_item(item: dict[str, Any]) -> str | None:
    carousel = item.get("carousel_media")
    if isinstance(carousel, list) and carousel:
        first = carousel[0]
        if isinstance(first, dict):
            return image_candidate(first)
    return image_candidate(item)


def image_candidate(item: dict[str, Any]) -> str | None:
    versions = item.get("image_versions2")
    if not isinstance(versions, dict):
        return None
    candidates = versions.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    first = candidates[0]
    if not isinstance(first, dict):
        return None
    return first.get("url")
