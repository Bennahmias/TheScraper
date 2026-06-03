from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .analysis import analyze_dataset
from .brief import generate_manager_brief
from .config import default_since_date, load_account_urls
from .feed_backend import InstagramFeedBackend
from .instaloader_backend import scrape_with_instaloader
from .report import generate_report
from .scraper import InstagramScraper
from .storage import load_dataset, save_dataset

app = typer.Typer(help="Scrape, analyze, and report on regional ADL Instagram posts.")
console = Console()


@app.command()
def scrape(
    accounts: Annotated[Path, typer.Option(help="Text file containing Instagram profile URLs.")] = Path(
        "URLS.txt"
    ),
    output: Annotated[Path, typer.Option(help="JSON output path.")] = Path("output/posts.json"),
    since: Annotated[
        str | None,
        typer.Option(help="Inclusive cutoff date in YYYY-MM-DD format. Defaults to May 1 current year."),
    ] = None,
    max_posts_per_account: Annotated[int, typer.Option(help="Safety cap per account.")] = 30,
    headless: Annotated[bool, typer.Option(help="Run browser in headless mode.")] = True,
    backend: Annotated[
        str,
        typer.Option(help="Scraping backend: feed, playwright, or instaloader."),
    ] = "feed",
) -> None:
    since_date = parse_since(since)
    urls = load_account_urls(accounts)
    if not urls:
        raise typer.BadParameter(f"No account URLs found in {accounts}")

    console.print(
        f"[bold]Scraping {len(urls)} accounts from {since_date} onward via {backend}...[/bold]"
    )
    if backend == "feed":
        scraper = InstagramFeedBackend(
            output_dir=output.parent,
            max_posts_per_account=max_posts_per_account,
            headless=headless,
        )
        dataset = asyncio.run(scraper.scrape_accounts(urls, since_date))
    elif backend == "playwright":
        scraper = InstagramScraper(
            output_dir=output.parent,
            max_posts_per_account=max_posts_per_account,
            headless=headless,
        )
        dataset = asyncio.run(scraper.scrape_accounts(urls, since_date))
    elif backend == "instaloader":
        dataset = scrape_with_instaloader(
            account_urls=urls,
            since=since_date,
            output_dir=output.parent,
            max_posts_per_account=max_posts_per_account,
        )
    else:
        raise typer.BadParameter("backend must be 'feed', 'playwright', or 'instaloader'")

    save_dataset(dataset, output)
    console.print(f"[green]Saved {len(dataset.posts)} posts to {output}[/green]")
    for warning in dataset.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")


@app.command()
def analyze(
    input: Annotated[Path, typer.Option(help="Scraped JSON input.")] = Path("output/posts.json"),
    output: Annotated[Path, typer.Option(help="Analyzed JSON output.")] = Path(
        "output/analyzed_posts.json"
    ),
    provider: Annotated[
        str,
        typer.Option(help="auto, openai, or rules. auto uses OpenAI when OPENAI_API_KEY exists."),
    ] = "auto",
    model: Annotated[str | None, typer.Option(help="OpenAI model name.")] = None,
) -> None:
    dataset = load_dataset(input)
    dataset = analyze_dataset(dataset, provider=provider, model=model)
    save_dataset(dataset, output)
    console.print(f"[green]Saved analyzed dataset to {output}[/green]")


@app.command()
def report(
    input: Annotated[Path, typer.Option(help="Analyzed JSON input.")] = Path(
        "output/analyzed_posts.json"
    ),
    output: Annotated[Path, typer.Option(help="HTML dashboard output.")] = Path("output/report.html"),
) -> None:
    dataset = load_dataset(input)
    generate_report(dataset, output)
    console.print(f"[green]Generated dashboard at {output}[/green]")


@app.command()
def brief(
    input: Annotated[Path, typer.Option(help="Analyzed JSON input.")] = Path(
        "output/analyzed_posts.json"
    ),
    html: Annotated[Path, typer.Option(help="Simple Hebrew HTML brief output.")] = Path(
        "output/manager_brief_he.html"
    ),
    markdown: Annotated[Path, typer.Option(help="Simple Hebrew Markdown brief output.")] = Path(
        "output/manager_brief_he.md"
    ),
) -> None:
    dataset = load_dataset(input)
    generate_manager_brief(dataset, html, markdown)
    console.print(f"[green]Generated manager brief at {html} and {markdown}[/green]")


@app.command("run-all")
def run_all(
    accounts: Annotated[Path, typer.Option(help="Text file containing Instagram profile URLs.")] = Path(
        "URLS.txt"
    ),
    since: Annotated[
        str | None,
        typer.Option(help="Inclusive cutoff date in YYYY-MM-DD format. Defaults to May 1 current year."),
    ] = None,
    max_posts_per_account: Annotated[int, typer.Option(help="Safety cap per account.")] = 30,
    provider: Annotated[str, typer.Option(help="auto, openai, or rules.")] = "auto",
    model: Annotated[str | None, typer.Option(help="OpenAI model name.")] = None,
    headless: Annotated[bool, typer.Option(help="Run browser in headless mode.")] = True,
    backend: Annotated[str, typer.Option(help="Scraping backend: feed, playwright, or instaloader.")] = "feed",
) -> None:
    posts_path = Path("output/posts.json")
    analyzed_path = Path("output/analyzed_posts.json")
    report_path = Path("output/report.html")

    scrape(accounts, posts_path, since, max_posts_per_account, headless, backend)
    analyze(posts_path, analyzed_path, provider, model)
    report(analyzed_path, report_path)


def parse_since(value: str | None) -> date:
    if not value:
        return default_since_date()
    return datetime.strptime(value, "%Y-%m-%d").date()


if __name__ == "__main__":
    app()
