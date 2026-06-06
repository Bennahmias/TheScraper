from __future__ import annotations

import base64
import mimetypes
import re
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from .models import InstagramPost, ScrapeDataset
from .report import category_label, relative_asset


ACTION_CATEGORIES = {
    "Reporting",
    "Education",
    "Advocacy",
    "Community Action",
    "Toolkit or Resource",
}

METHOD_LABELS = {
    "Reporting": "דיווח על אירועים ותוכן אנטישמי",
    "Education": "חינוך, הסברה וזיהוי אנטישמיות",
    "Advocacy": "סנגור ופנייה למוסדות או נבחרי ציבור",
    "Community Action": "הגעה לאירועים ופעולה קהילתית",
    "Toolkit or Resource": "שימוש במשאבים וכלים מעשיים",
    "Incident Response": "תגובה ציבורית לאירועים אנטישמיים",
    "Commemoration": "הנצחה וזיכרון כבסיס למחויבות",
    "Awareness": "העלאת מודעות",
    "Other": "מסרים כלליים או ארגוניים",
}

ACCOUNT_LOCATION_LABELS_HE = {
    "adlmichigan": "מישיגן",
    "adlaustin": "אוסטין",
    "adlcalifornia": "קליפורניה",
    "adl.heartland": "הארטלנד",
    "adl_newengland": "ניו אינגלנד",
    "adlsoutheast": "דרום-מזרח ארה״ב",
    "adldesert": "אזור המדבר",
    "adl_philly": "פילדלפיה",
    "adl_texoma": "טקסומה",
    "adlsouthcentral": "דרום-מרכז ארה״ב",
    "adl_nynj": "ניו יורק וניו ג׳רזי",
    "adl_washdc": "וושינגטון די.סי.",
    "adl_midwest": "המערב התיכון",
    "adlpnw": "הצפון-מערב הפסיפי",
}

PREFERRED_EXAMPLES = {
    "adlmichigan:DX_7ui1HApZ": {
        "translation": (
            "ADL מציגים נתונים על היקף האירועים האנטישמיים בארה״ב ובמישיגן, "
            "ומסבירים מדוע הקהילה היהודית מרגישה פחות בטוחה. זה מחזק מודעות ומספק הקשר עובדתי."
        ),
        "takeaway": "הם מציידים את העוקבים בנתונים כדי לזהות את חומרת הבעיה.",
    },
    "adlmichigan:DY18fEHEXZU": {
        "translation": (
            "הפוסט מזמין את העוקבים להגיע לערב קהילתי על יהדות, גאווה יהודית ומוזיקה, "
            "עם רישום מראש וללא כניסה חופשית."
        ),
        "takeaway": "הפעולה המבוקשת היא להגיע פיזית ולהשתתף בחיזוק קהילתי.",
    },
    "adlmichigan:DYlPSbcpi96": {
        "translation": (
            "ADL מגיבים להודעת בית ספר בעקבות אירוע ספציפי, וממקמים אותו כחלק מהצורך "
            "להתייחס ברצינות לאנטישמיות במרחבים חינוכיים."
        ),
        "takeaway": "הם נותנים לקהילה מסגרת תגובה לאירוע אנטישמי קונקרטי.",
    },
    "adlcalifornia:DYF-UFuEqVp": {
        "translation": (
            "מנהלי ADL קליפורניה שולחים מכתב רשמי לגורם מדינתי בעקבות הפצת רטוריקה אנטישמית "
            "במדריך מידע רשמי לבוחרים."
        ),
        "takeaway": "הם מראים שימוש בכלים מוסדיים ורשמיים כדי להתמודד עם אנטישמיות.",
    },
    "adl_newengland:DYNbgakFoe3": {
        "translation": (
            "הפוסט עומד לצד עסק יהודי שספג ונדליזם אנטישמי חוזר, ומבקש מהעוקבים לבקר או להזמין, "
            "לשתף את הפוסט, ולדווח ל-ADL אם הם רואים אירוע שנאה."
        ),
        "takeaway": "זו הדוגמה הכי ישירה: תמיכה בעסק, שיתוף, ודיווח על שנאה.",
    },
    "adl_midwest:DXzv6-xkbXq": {
        "translation": (
            "הפוסט מתאר התנגדות משותפת להצעת חוק באילינוי, ומדגיש שכאשר הקהילה מופיעה יחד "
            "הקול הציבורי שלה חזק יותר."
        ),
        "takeaway": "כאן הפעולה היא סנגור ציבורי ועבודה עם שותפים מול מדיניות.",
    },
}

EXAMPLE_IMAGE_FALLBACKS = {
    "adlmichigan:DX_7ui1HApZ": Path("docs/assets/brief_examples/adlmichigan_DX_7ui1HApZ.jpg"),
    "adlmichigan:DY18fEHEXZU": Path("docs/assets/brief_examples/adlmichigan_DY18fEHEXZU.jpg"),
    "adlmichigan:DYlPSbcpi96": Path("docs/assets/brief_examples/adlmichigan_DYlPSbcpi96.jpg"),
    "adlcalifornia:DYF-UFuEqVp": Path("docs/assets/brief_examples/adlcalifornia_DYF-UFuEqVp.jpg"),
    "adl_newengland:DYNbgakFoe3": Path("docs/assets/brief_examples/adl_newengland_DYNbgakFoe3.jpg"),
    "adl_midwest:DXzv6-xkbXq": Path("docs/assets/brief_examples/adl_midwest_DXzv6-xkbXq.jpg"),
}


def generate_manager_brief(
    dataset: ScrapeDataset,
    html_path: Path,
    markdown_path: Path,
    embed_assets: bool = False,
) -> None:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    posts = sorted(dataset.posts, key=lambda post: post.timestamp or post.scraped_at, reverse=True)
    context = build_brief_context(posts, html_path, embed_assets=embed_assets)
    markdown = render_markdown(context)
    html = render_html(markdown, context)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")


def build_brief_context(
    posts: list[InstagramPost],
    html_path: Path,
    embed_assets: bool = False,
) -> dict[str, object]:
    categories = Counter(post.analysis.category if post.analysis else "Other" for post in posts)
    accounts: dict[str, list[InstagramPost]] = defaultdict(list)
    for post in posts:
        accounts[post.account].append(post)

    actionable = [
        post
        for post in posts
        if post.analysis and post.analysis.category in ACTION_CATEGORIES
    ]

    account_rows = []
    for account, account_posts in sorted(accounts.items()):
        account_categories = Counter(
            post.analysis.category if post.analysis else "Other" for post in account_posts
        )
        top_category = account_categories.most_common(1)[0][0]
        equipped_count = sum(
            1 for post in account_posts if post.analysis and post.analysis.equips_followers
        )
        relevant_posts = [
            post
            for post in sorted(
                account_posts,
                key=lambda item: item.timestamp or item.scraped_at,
                reverse=True,
            )
            if post.post_url
            and post.analysis
            and (
                post.analysis.category in ACTION_CATEGORIES
                or post.analysis.equips_followers
            )
        ][:3]
        account_rows.append(
            {
                "account": account,
                "location": ACCOUNT_LOCATION_LABELS_HE.get(account, ""),
                "posts": len(account_posts),
                "top_method": METHOD_LABELS.get(top_category, category_label(top_category)),
                "equipped": equipped_count,
                "links": [post.post_url for post in relevant_posts],
            }
        )

    return {
        "total_posts": len(posts),
        "account_count": len(accounts),
        "equipped_posts": len(actionable),
        "equipped_share": round((len(actionable) / max(len(posts), 1)) * 100),
        "categories": categories,
        "account_rows": account_rows,
        "examples": pick_examples(posts, html_path, embed_assets=embed_assets),
    }


def pick_examples(
    posts: list[InstagramPost],
    html_path: Path,
    embed_assets: bool = False,
) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    by_id = {post.id: post for post in posts}
    ordered_posts = [by_id[post_id] for post_id in PREFERRED_EXAMPLES if post_id in by_id]

    used_categories: set[str] = set()
    for post in ordered_posts:
        if not post.analysis:
            continue
        translation = PREFERRED_EXAMPLES.get(post.id, {})
        examples.append(
            {
                "account": post.account,
                "category": METHOD_LABELS.get(post.analysis.category, category_label(post.analysis.category)),
                "date": post.timestamp.strftime("%Y-%m-%d") if post.timestamp else "",
                "original": excerpt(post.caption),
                "translation": translation.get("translation", ""),
                "takeaway": translation.get("takeaway", post.analysis.strategy),
                "image": example_image_src(post, html_path, embed_assets),
                "url": post.post_url,
            }
        )
        used_categories.add(post.analysis.category)
        if len(examples) >= 6:
            break

    if len(examples) >= 6:
        return examples

    for post in posts:
        if not post.analysis or post.analysis.category in used_categories:
            continue
        examples.append(
            {
                "account": post.account,
                "category": METHOD_LABELS.get(post.analysis.category, category_label(post.analysis.category)),
                "date": post.timestamp.strftime("%Y-%m-%d") if post.timestamp else "",
                "original": excerpt(post.caption),
                "translation": post.analysis.strategy,
                "takeaway": post.analysis.follower_action or post.analysis.strategy,
                "image": example_image_src(post, html_path, embed_assets),
                "url": post.post_url,
            }
        )
        used_categories.add(post.analysis.category)
        if len(examples) >= 6:
            break
    return examples


def excerpt(text: str, limit: int = 360) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def image_src(asset_path: str | None, html_path: Path, embed_assets: bool) -> str:
    if not asset_path:
        return ""
    if not embed_assets:
        return relative_asset(asset_path, html_path)

    path = Path(asset_path)
    if not path.exists():
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def example_image_src(post: InstagramPost, html_path: Path, embed_assets: bool) -> str:
    primary = image_src(post.media_path, html_path, embed_assets)
    if primary:
        return primary
    fallback = EXAMPLE_IMAGE_FALLBACKS.get(post.id)
    if not fallback:
        return ""
    return image_src(str(fallback), html_path, embed_assets)


def render_markdown(context: dict[str, object]) -> str:
    categories: Counter[str] = context["categories"]  # type: ignore[assignment]
    account_rows: list[dict[str, object]] = context["account_rows"]  # type: ignore[assignment]
    examples: list[dict[str, str]] = context["examples"]  # type: ignore[assignment]

    category_lines = [
        f"- {METHOD_LABELS.get(category, category_label(category))}: {count} פוסטים"
        for category, count in categories.most_common()
    ]
    account_lines = [
        (
            f"- {row['account']}{format_location(row['location'])}: "
            f"{row['top_method']} ({row['equipped']} מתוך {row['posts']} פוסטים עם הכוונה לפעולה)"
            f"{format_post_links(row['links'])}"
        )
        for row in account_rows
    ]
    example_lines = [
        (
            f"- {item['account']} | {item['category']}\n"
            f"  מקור: {item['original']}\n"
            f"  תרגום/משמעות: {item['translation']}\n"
            f"  למה זה חשוב: {item['takeaway']}\n"
            f"  קישור: {item['url']}"
        )
        for item in examples
    ]

    return "\n".join(
        [
            "# כיצד חשבונות ADL האזוריים מניעים עוקבים להתמודד עם אנטישמיות?",
            "",
            "## השורה התחתונה",
            (
                "החשבונות לא מתמקדים בעיקר בקריאה לעימות ישיר. "
                "הם מציידים את העוקבים לפעולה דרך דיווח, למידה, השתתפות קהילתית, "
                "תגובה לאירועים, ולעיתים סנגור מול מוסדות או מקבלי החלטות."
            ),
            "",
            "## תמונת מצב",
            f"- נותחו {context['total_posts']} פוסטים מ-{context['account_count']} חשבונות אזוריים.",
            (
                f"- {context['equipped_posts']} פוסטים ({context['equipped_share']}%) "
                "כוללים הכוונה ברורה יחסית לפעולה מצד העוקבים."
            ),
            "",
            "## איך הם גורמים לעוקבים לפעול?",
            "1. דיווח: הפניה לדיווח על אירועים אנטישמיים או תכנים בעייתיים.",
            "2. חינוך והסברה: נתונים, הדרכות, סדנאות והסברים שמלמדים לזהות אנטישמיות.",
            "3. פעולה קהילתית: הזמנה להגיע לאירועים, מפגשים, פעילויות תמיכה וסולידריות.",
            "4. תגובה לאירועים: מסגור אירועים אנטישמיים והכוונת הקהילה לתמיכה, ערנות ודיווח.",
            "5. סנגור: במקרים מסוימים קריאה לפנות למוסדות, מנהיגים או גורמי ממשל.",
            "",
            "## התפלגות מסרים",
            *category_lines,
            "",
            "## לפי חשבון",
            *account_lines,
            "",
            "## דוגמאות מייצגות",
            *example_lines,
        ]
    )


def render_html(markdown: str, context: dict[str, object]) -> str:
    markdown_without_text_examples = remove_text_examples(markdown)
    before_breakdown, breakdown = split_before_breakdown(markdown_without_text_examples)
    body_before = markdown_to_html(before_breakdown)
    body_after = markdown_to_html(breakdown)
    cards = render_example_cards(context["examples"])  # type: ignore[arg-type]
    return f"""<!doctype html>
<html lang="he" dir="rtl">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>תקציר מנהלים - ADL Instagram</title>
    <style>
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: #eef3f8;
        color: #0f1f3d;
        font-family: Arial, "Noto Sans Hebrew", sans-serif;
        line-height: 1.65;
      }}
      main {{
        max-width: 1040px;
        margin: 28px auto;
        padding: 34px 38px 48px;
        background: #fff;
        border: 1px solid #dbe3ef;
        border-radius: 12px;
        box-shadow: 0 18px 45px rgba(15, 31, 61, 0.08);
      }}
      h1 {{
        font-size: 32px;
        line-height: 1.25;
        margin: 10px 0 26px;
        padding-bottom: 18px;
        border-bottom: 3px solid #0b5cad;
      }}
      h2 {{ font-size: 20px; margin: 30px 0 10px; border-top: 1px solid #dbe3ef; padding-top: 18px; }}
      p, li {{ font-size: 16px; }}
      ul, ol {{ padding-inline-start: 26px; }}
      a {{ color: #0b5cad; }}
      .stats {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin: 0 0 24px;
      }}
      .stat {{
        border: 1px solid #dbe3ef;
        border-radius: 8px;
        padding: 18px;
        background: linear-gradient(180deg, #ffffff, #f8fbff);
      }}
      .stat b {{ display: block; font-size: 28px; color: #0b5cad; }}
      ol li::marker {{ color: #0b5cad; font-weight: 700; }}
      .examples {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
        margin-top: 18px;
      }}
      .card {{
        border: 1px solid #dbe3ef;
        border-radius: 8px;
        overflow: hidden;
        background: #fff;
        box-shadow: 0 10px 24px rgba(15, 31, 61, 0.06);
      }}
      .card img {{
        width: 100%;
        height: 230px;
        object-fit: cover;
        background: #eef2f7;
      }}
      .card-body {{ padding: 14px; }}
      .card h3 {{ margin: 0 0 4px; font-size: 17px; }}
      .meta {{ color: #52647c; font-size: 13px; margin-bottom: 10px; }}
      .chip {{
        display: inline-block;
        margin: 0 0 10px 6px;
        padding: 4px 8px;
        border-radius: 6px;
        background: #e8f6f7;
        color: #087985;
        font-size: 13px;
        font-weight: 700;
      }}
      .quote {{
        direction: ltr;
        text-align: left;
        color: #24364f;
        background: #f8fafc;
        border-radius: 6px;
        padding: 10px;
        font-size: 14px;
      }}
      .translation {{ font-size: 15px; }}
      .takeaway {{
        border-top: 1px solid #edf1f7;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: 700;
        color: #0f1f3d;
      }}
      .example-section {{
        border-top: 1px solid #dbe3ef;
        margin-top: 28px;
        padding-top: 18px;
      }}
      .example-section > p {{
        color: #52647c;
        margin-top: 0;
      }}
      @media print {{
        body {{ background: #fff; }}
        main {{ margin: 0; border: 0; box-shadow: none; }}
      }}
      @media (max-width: 760px) {{
        .stats, .examples {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <div class="stats">
        <div class="stat"><b>{context['total_posts']}</b><span>פוסטים נותחו</span></div>
        <div class="stat"><b>{context['account_count']}</b><span>חשבונות</span></div>
        <div class="stat"><b>{context['equipped_share']}%</b><span>עם הכוונה לפעולה</span></div>
      </div>
      {body_before}
      <section class="example-section">
        <h2>דוגמאות עם תרגום קצר</h2>
        <p>אלה דוגמאות מייצגות שמראות בפועל איך החשבונות מנסים להפעיל את העוקבים.</p>
        <div class="examples">
          {cards}
        </div>
      </section>
      {body_after}
    </main>
  </body>
</html>
"""


def render_example_cards(examples: list[dict[str, str]]) -> str:
    cards: list[str] = []
    for item in examples:
        image = item.get("image") or ""
        account = item["account"]
        category = item["category"]
        date = item["date"]
        original = item["original"]
        translation = item["translation"]
        takeaway = item["takeaway"]
        url = item["url"]
        image_html = f'<img src="{escape(image)}" alt="דוגמה מפוסט של {escape(account)}" />' if image else ""
        cards.append(
            f"""
          <article class="card">
            {image_html}
            <div class="card-body">
              <h3>{escape(account)}</h3>
              <div class="meta">{escape(date)} · {escape(category)}</div>
              <span class="chip">{escape(category)}</span>
              <p class="quote">{escape(original)}</p>
              <p class="translation"><b>תרגום/משמעות:</b> {escape(translation)}</p>
              <p class="takeaway">{escape(takeaway)}</p>
              <a href="{escape(url)}" target="_blank" rel="noreferrer">פתיחת הפוסט</a>
            </div>
          </article>
            """
        )
    return "\n".join(cards)


def markdown_to_html(markdown: str) -> str:
    html_lines: list[str] = []
    in_list = False
    list_type = ""
    for line in markdown.splitlines():
        if not line:
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
                list_type = ""
            continue
        if line.startswith("# "):
            html_lines.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_list or list_type != "ul":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            html_lines.append(f"<li>{link_urls(escape(line[2:]))}</li>")
        elif len(line) > 3 and line[0].isdigit() and line[1:3] == ". ":
            if not in_list or list_type != "ol":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            html_lines.append(f"<li>{link_urls(escape(line[3:]))}</li>")
        else:
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append(f"<p>{link_urls(escape(line))}</p>")
    if in_list:
        html_lines.append(f"</{list_type}>")
    return "\n".join(html_lines)


def remove_text_examples(markdown: str) -> str:
    marker = "\n## דוגמאות מייצגות\n"
    if marker not in markdown:
        return markdown
    before, rest = markdown.split(marker, 1)
    next_heading = re.search(r"\n## [^\n]+\n", rest)
    if not next_heading:
        return before.rstrip()
    return before + rest[next_heading.start() :]


def split_before_breakdown(markdown: str) -> tuple[str, str]:
    marker = "\n## התפלגות מסרים\n"
    if marker not in markdown:
        return markdown, ""
    before, after = markdown.split(marker, 1)
    return before, marker.lstrip("\n") + after


def link_urls(text: str) -> str:
    return re.sub(
        r"https://[^\s)]+",
        lambda match: (
            f'<a href="{match.group(0)}" target="_blank" rel="noreferrer">פוסט</a>'
        ),
        text,
    )


def format_location(location: object) -> str:
    return f" ({location})" if location else ""


def format_post_links(links: object) -> str:
    if not isinstance(links, list) or not links:
        return ""
    return " | קישורים רלוונטיים: " + " ".join(str(link) for link in links)
