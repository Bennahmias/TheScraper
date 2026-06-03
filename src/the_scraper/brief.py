from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .models import InstagramPost, ScrapeDataset
from .report import category_label


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


def generate_manager_brief(dataset: ScrapeDataset, html_path: Path, markdown_path: Path) -> None:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    posts = sorted(dataset.posts, key=lambda post: post.timestamp or post.scraped_at, reverse=True)
    context = build_brief_context(posts)
    markdown = render_markdown(context)
    html = render_html(markdown, context)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")


def build_brief_context(posts: list[InstagramPost]) -> dict[str, object]:
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
        account_rows.append(
            {
                "account": account,
                "posts": len(account_posts),
                "top_method": METHOD_LABELS.get(top_category, category_label(top_category)),
                "equipped": equipped_count,
            }
        )

    return {
        "total_posts": len(posts),
        "account_count": len(accounts),
        "equipped_posts": len(actionable),
        "equipped_share": round((len(actionable) / max(len(posts), 1)) * 100),
        "categories": categories,
        "account_rows": account_rows,
        "examples": pick_examples(actionable),
    }


def pick_examples(posts: list[InstagramPost]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    used_categories: set[str] = set()
    for post in posts:
        if not post.analysis or post.analysis.category in used_categories:
            continue
        examples.append(
            {
                "account": post.account,
                "category": METHOD_LABELS.get(post.analysis.category, category_label(post.analysis.category)),
                "summary": post.analysis.strategy,
                "url": post.post_url,
            }
        )
        used_categories.add(post.analysis.category)
        if len(examples) >= 5:
            break
    return examples


def render_markdown(context: dict[str, object]) -> str:
    categories: Counter[str] = context["categories"]  # type: ignore[assignment]
    account_rows: list[dict[str, object]] = context["account_rows"]  # type: ignore[assignment]
    examples: list[dict[str, str]] = context["examples"]  # type: ignore[assignment]

    category_lines = [
        f"- {METHOD_LABELS.get(category, category_label(category))}: {count} פוסטים"
        for category, count in categories.most_common()
    ]
    account_lines = [
        f"- {row['account']}: {row['top_method']} ({row['equipped']} מתוך {row['posts']} פוסטים עם הכוונה לפעולה)"
        for row in account_rows
    ]
    example_lines = [
        f"- {item['account']}: {item['category']} - {item['summary']} ({item['url']})"
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
            "",
            "## הערה למנהל",
            (
                "המסר המרכזי: ADL האזוריים בונים יכולת תגובה קהילתית יותר מאשר קריאה לעימות. "
                "הם מלמדים מה לזהות, לאן לדווח, מתי להגיע פיזית, ואיך לחזק תגובה ציבורית מאורגנת."
            ),
        ]
    )


def render_html(markdown: str, context: dict[str, object]) -> str:
    body = markdown_to_html(markdown)
    return f"""<!doctype html>
<html lang="he" dir="rtl">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>תקציר מנהלים - ADL Instagram</title>
    <style>
      body {{
        margin: 0;
        background: #f8fafc;
        color: #0f1f3d;
        font-family: Arial, "Noto Sans Hebrew", sans-serif;
        line-height: 1.65;
      }}
      main {{
        max-width: 920px;
        margin: 0 auto;
        padding: 40px 24px 56px;
        background: #fff;
        min-height: 100vh;
      }}
      h1 {{ font-size: 30px; line-height: 1.25; margin: 0 0 24px; }}
      h2 {{ font-size: 19px; margin: 28px 0 8px; border-top: 1px solid #dbe3ef; padding-top: 18px; }}
      p, li {{ font-size: 16px; }}
      ul, ol {{ padding-inline-start: 26px; }}
      a {{ color: #0b5cad; }}
      .stats {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin: 24px 0;
      }}
      .stat {{
        border: 1px solid #dbe3ef;
        border-radius: 8px;
        padding: 14px;
        background: #f8fafc;
      }}
      .stat b {{ display: block; font-size: 28px; color: #0b5cad; }}
      @media print {{
        body {{ background: #fff; }}
        main {{ padding: 0; }}
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
      {body}
    </main>
  </body>
</html>
"""


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
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("- "):
            if not in_list or list_type != "ul":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            html_lines.append(f"<li>{link_urls(line[2:])}</li>")
        elif len(line) > 3 and line[0].isdigit() and line[1:3] == ". ":
            if not in_list or list_type != "ol":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            html_lines.append(f"<li>{link_urls(line[3:])}</li>")
        else:
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append(f"<p>{link_urls(line)}</p>")
    if in_list:
        html_lines.append(f"</{list_type}>")
    return "\n".join(html_lines)


def link_urls(text: str) -> str:
    parts = text.split("https://")
    if len(parts) == 1:
        return text
    result = parts[0]
    for part in parts[1:]:
        url, *rest = part.split(")", 1)
        full_url = "https://" + url
        result += f'<a href="{full_url}" target="_blank" rel="noreferrer">קישור לפוסט</a>'
        if rest:
            result += ")" + rest[0]
    return result
