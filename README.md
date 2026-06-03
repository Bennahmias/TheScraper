# TheScraper

Automated research pipeline for public Instagram posts from regional ADL accounts.

The agent is designed to answer:

> How do different regional accounts direct, encourage, or equip followers to confront, handle, and counter antisemitism?

It collects public post metadata, stores screenshots/media where available, analyzes captions into action-oriented categories, and generates an interactive static HTML dashboard.

## Important Boundaries

Instagram restricts automated data collection in its terms. This project uses conservative public-page collection only:

- No login automation.
- No credential handling.
- No CAPTCHA bypass.
- No proxy rotation or block evasion.
- Low-volume, delayed requests.
- Stop and report when content is unavailable or blocked.

For production or institutional use, review Meta/Instagram policies and consider official Meta API access where possible.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install chromium
```

Optional OpenAI analysis:

```powershell
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY
```

If no OpenAI key is configured, the analyzer falls back to deterministic keyword rules.

## Usage

Scrape posts from May 1 of the current year:

```powershell
the-scraper scrape --accounts URLS.txt --output output/posts.json
```

Analyze captions:

```powershell
the-scraper analyze --input output/posts.json --output output/analyzed_posts.json
```

Generate the interactive dashboard:

```powershell
the-scraper report --input output/analyzed_posts.json --output output/report.html
```

Run the full pipeline:

```powershell
the-scraper run-all --accounts URLS.txt
```

Open `output/report.html` in a browser.

## Output

- `output/posts.json`: scraped post records.
- `output/analyzed_posts.json`: post records with analysis.
- `output/screenshots/`: post screenshots.
- `output/media/`: downloaded media thumbnails/images when available.
- `output/report.html`: interactive dashboard.

## Data Extracted

Per post:

- account username
- post URL
- timestamp when visible
- caption/post text
- like count when visible
- comment count when visible
- screenshot path
- media URL/path when available
- analysis category, strategy, tone, urgency, evidence, and actionability score

