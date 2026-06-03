from __future__ import annotations

import asyncio
import random
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright

from .config import username_from_url
from .models import InstagramPost, ScrapeDataset

COUNT_RE = re.compile(r"(?P<count>[\d,.]+)\s*(?P<suffix>[KMB])?", re.IGNORECASE)
POST_URL_RE = re.compile(r"https://www\.instagram\.com/(?:p|reel)/([^/?#]+)/?")


class InstagramScraper:
    def __init__(
        self,
        output_dir: Path,
        max_posts_per_account: int = 30,
        min_delay: float = 4.0,
        max_delay: float = 9.0,
        headless: bool = True,
    ) -> None:
        self.output_dir = output_dir
        self.max_posts_per_account = max_posts_per_account
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.headless = headless

    async def scrape_accounts(self, account_urls: list[str], since: date) -> ScrapeDataset:
        dataset = ScrapeDataset(since=datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1440, "height": 1200},
                locale="en-US",
            )
            page = await context.new_page()

            for account_url in account_urls:
                account = username_from_url(account_url)
                try:
                    post_urls = await self._collect_post_urls(page, account_url)
                    if not post_urls:
                        dataset.warnings.append(f"No public post URLs found for {account}.")

                    for post_url in post_urls[: self.max_posts_per_account]:
                        post = await self._scrape_post(page, account, account_url, post_url, since)
                        if post is None:
                            continue
                        dataset.posts.append(post)
                        await self._delay()
                except PlaywrightError as exc:
                    dataset.warnings.append(f"Playwright error for {account}: {exc}")
                except Exception as exc:  # noqa: BLE001 - preserve scrape progress across accounts.
                    dataset.warnings.append(f"Unexpected error for {account}: {exc}")
                finally:
                    await self._delay()

            await context.close()
            await browser.close()

        return dataset

    async def _collect_post_urls(self, page: Page, account_url: str) -> list[str]:
        await page.goto(account_url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(2_500)

        seen: list[str] = []
        seen_set: set[str] = set()
        stable_rounds = 0

        for _ in range(8):
            hrefs = await page.locator('a[href*="/p/"], a[href*="/reel/"]').evaluate_all(
                "(links) => links.map((a) => a.href)"
            )
            for href in hrefs:
                normalized = normalize_post_url(str(href))
                if normalized and normalized not in seen_set:
                    seen.append(normalized)
                    seen_set.add(normalized)

            if len(seen) >= self.max_posts_per_account:
                break

            previous_count = len(seen)
            await page.mouse.wheel(0, 2400)
            await self._delay()
            stable_rounds = stable_rounds + 1 if len(seen) == previous_count else 0
            if stable_rounds >= 2:
                break

        return seen

    async def _scrape_post(
        self,
        page: Page,
        account: str,
        account_url: str,
        post_url: str,
        since: date,
    ) -> InstagramPost | None:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(2_500)

        post_id = shortcode_from_url(post_url)
        timestamp = await extract_timestamp(page)
        if timestamp and timestamp.date() < since:
            return None

        description = await extract_meta_content(page, "meta[property='og:description']")
        title = await extract_meta_content(page, "meta[property='og:title']")
        media_url = await extract_meta_content(page, "meta[property='og:image']")
        caption = extract_caption(description) or extract_caption(title) or await extract_article_text(page)
        likes, comments = extract_counts(description)

        screenshot_path = await self._save_screenshot(page, account, post_id)
        media_path = await self._download_media(account, post_id, media_url) if media_url else None

        return InstagramPost(
            id=f"{account}:{post_id}",
            account=account,
            account_url=account_url,
            post_url=post_url,
            timestamp=timestamp,
            caption=caption,
            likes=likes,
            comments=comments,
            screenshot_path=str(screenshot_path) if screenshot_path else None,
            media_url=media_url,
            media_path=str(media_path) if media_path else None,
        )

    async def _save_screenshot(self, page: Page, account: str, post_id: str) -> Path | None:
        target_dir = self.output_dir / "screenshots" / account
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{post_id}.png"

        try:
            article = page.locator("article").first
            if await article.count():
                await article.screenshot(path=str(target), animations="disabled")
            else:
                await page.screenshot(path=str(target), full_page=False, animations="disabled")
            return target
        except PlaywrightError:
            return None

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

    async def _delay(self) -> None:
        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))


def normalize_post_url(raw_url: str) -> str | None:
    parsed = urlparse(raw_url)
    match = re.search(r"/(p|reel)/([^/?#]+)/?", parsed.path)
    if not match:
        return None
    return f"https://www.instagram.com/{match.group(1)}/{match.group(2)}/"


def shortcode_from_url(post_url: str) -> str:
    match = POST_URL_RE.search(post_url)
    if match:
        return match.group(1)
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", post_url).strip("_")[:80]


async def extract_meta_content(page: Page, selector: str) -> str:
    try:
        value = await page.locator(selector).first.get_attribute("content")
    except PlaywrightError:
        return ""
    return value or ""


async def extract_timestamp(page: Page) -> datetime | None:
    try:
        value = await page.locator("time").first.get_attribute("datetime")
    except PlaywrightError:
        return None
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


async def extract_article_text(page: Page) -> str:
    try:
        text = await page.locator("article").first.inner_text(timeout=5_000)
    except PlaywrightError:
        return ""
    return clean_text(text)


def extract_caption(description: str) -> str:
    if not description:
        return ""

    quoted = re.search(r":\s*[\"“](?P<caption>.*)[\"”]\.?\s*$", description, flags=re.DOTALL)
    if quoted:
        return clean_text(quoted.group("caption"))

    marker = " on Instagram: "
    if marker in description:
        return clean_text(description.split(marker, 1)[1].strip(" \""))

    return ""


def extract_counts(text: str) -> tuple[int | None, int | None]:
    likes = extract_count_before_word(text, "likes")
    comments = extract_count_before_word(text, "comments")
    return likes, comments


def extract_count_before_word(text: str, word: str) -> int | None:
    if not text:
        return None
    pattern = re.compile(rf"(?P<count>[\d,.]+)\s*(?P<suffix>[KMB])?\s+{word}", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    return parse_count(match.group("count"), match.group("suffix"))


def parse_count(value: str, suffix: str | None = None) -> int | None:
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return None

    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(
        (suffix or "").upper(),
        1,
    )
    return int(number * multiplier)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
