from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import InstagramPost, ScrapeDataset

CATEGORY_LABELS_HE = {
    "Reporting": "דיווח",
    "Education": "חינוך והדרכה",
    "Advocacy": "סנגור והשפעה ציבורית",
    "Community Action": "פעולה קהילתית",
    "Toolkit or Resource": "ערכת כלים או משאב",
    "Incident Response": "תגובה לאירוע",
    "Commemoration": "הנצחה וזיכרון",
    "Awareness": "מודעות",
    "Other": "אחר",
    "Unanalyzed": "לא נותח",
}

TONE_LABELS_HE = {
    "Empowering": "מעצים",
    "Urgent": "דחוף",
    "Informative": "אינפורמטיבי",
    "Solidarity": "סולידריות",
    "Protective": "מגן",
    "Commemorative": "הנצחתי",
    "Other": "אחר",
    "Unanalyzed": "לא נותח",
}


def generate_report(dataset: ScrapeDataset, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    view_model = build_view_model(dataset, output_path)
    output_path.write_text(template.render(**view_model), encoding="utf-8")


def build_view_model(dataset: ScrapeDataset, output_path: Path) -> dict[str, object]:
    posts = sorted(dataset.posts, key=lambda post: post.timestamp or post.scraped_at, reverse=True)
    categories = Counter(
        category_label(post.analysis.category if post.analysis else "Unanalyzed") for post in posts
    )
    tones = Counter(tone_label(post.analysis.tone if post.analysis else "Unanalyzed") for post in posts)
    accounts = Counter(post.account for post in posts)
    equipped = sum(1 for post in posts if post.analysis and post.analysis.equips_followers)
    engagement_values = [(post.likes or 0) + (post.comments or 0) for post in posts]

    account_rows = build_account_rows(posts)
    timeline = build_timeline(posts)
    serializable_posts = [serialize_post(post, output_path) for post in posts]

    return {
        "generated_at": dataset.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
        "since": dataset.since.strftime("%Y-%m-%d") if dataset.since else "May 1 onward",
        "total_posts": len(posts),
        "account_count": len(accounts),
        "equipped_count": equipped,
        "avg_actionability": round(
            sum(post.analysis.actionability_score for post in posts if post.analysis)
            / max(sum(1 for post in posts if post.analysis), 1),
            2,
        ),
        "total_engagement": sum(engagement_values),
        "warnings": [translate_warning(warning) for warning in dataset.warnings],
        "insight_lines": build_insight_lines(posts, categories, equipped),
        "posts_json": json.dumps(serializable_posts, ensure_ascii=False),
        "categories_json": json.dumps(dict(categories), ensure_ascii=False),
        "tones_json": json.dumps(dict(tones), ensure_ascii=False),
        "timeline_json": json.dumps(timeline, ensure_ascii=False),
        "account_rows": account_rows,
    }


def build_account_rows(posts: list[InstagramPost]) -> list[dict[str, object]]:
    grouped: dict[str, list[InstagramPost]] = defaultdict(list)
    for post in posts:
        grouped[post.account].append(post)

    rows: list[dict[str, object]] = []
    for account, account_posts in sorted(grouped.items()):
        category_counts = Counter(
            post.analysis.category if post.analysis else "Unanalyzed" for post in account_posts
        )
        tone_counts = Counter(post.analysis.tone if post.analysis else "Unanalyzed" for post in account_posts)
        rows.append(
            {
                "account": account,
                "posts": len(account_posts),
                "engagement": sum((post.likes or 0) + (post.comments or 0) for post in account_posts),
                "equipped": sum(
                    1 for post in account_posts if post.analysis and post.analysis.equips_followers
                ),
                "top_category": category_label(category_counts.most_common(1)[0][0]),
                "top_tone": tone_label(tone_counts.most_common(1)[0][0]),
                "avg_actionability": round(
                    sum(
                        post.analysis.actionability_score
                        for post in account_posts
                        if post.analysis
                    )
                    / max(sum(1 for post in account_posts if post.analysis), 1),
                    2,
                ),
            }
        )
    return rows


def build_timeline(posts: list[InstagramPost]) -> list[dict[str, object]]:
    counts: dict[str, int] = defaultdict(int)
    engagement: dict[str, int] = defaultdict(int)

    for post in posts:
        if not post.timestamp:
            continue
        day = post.timestamp.strftime("%Y-%m-%d")
        counts[day] += 1
        engagement[day] += (post.likes or 0) + (post.comments or 0)

    return [
        {"date": day, "posts": counts[day], "engagement": engagement[day]}
        for day in sorted(counts)
    ]


def serialize_post(post: InstagramPost, output_path: Path) -> dict[str, object]:
    analysis = post.analysis
    return {
        "id": post.id,
        "account": post.account,
        "postUrl": post.post_url,
        "date": post.timestamp.strftime("%Y-%m-%d") if post.timestamp else "Unknown",
        "caption": post.caption,
        "likes": post.likes,
        "comments": post.comments,
        "engagement": (post.likes or 0) + (post.comments or 0),
        "screenshot": relative_asset(post.screenshot_path, output_path),
        "media": relative_asset(post.media_path, output_path),
        "category": category_label(analysis.category if analysis else "Unanalyzed"),
        "categoryRaw": analysis.category if analysis else "Unanalyzed",
        "strategy": analysis.strategy if analysis else "",
        "tone": tone_label(analysis.tone if analysis else "Unanalyzed"),
        "toneRaw": analysis.tone if analysis else "Unanalyzed",
        "targetAudience": analysis.target_audience if analysis else "",
        "followerAction": analysis.follower_action if analysis else "",
        "equipsFollowers": analysis.equips_followers if analysis else False,
        "urgency": analysis.urgency if analysis else 1,
        "actionability": analysis.actionability_score if analysis else 1,
        "evidence": analysis.evidence if analysis else "",
    }


def relative_asset(asset_path: str | None, output_path: Path) -> str:
    if not asset_path:
        return ""
    path = Path(asset_path)
    try:
        return path.resolve().relative_to(output_path.parent.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_insight_lines(
    posts: list[InstagramPost],
    categories: Counter[str],
    equipped_count: int,
) -> list[str]:
    if not posts:
        return ["לא נמצאו פוסטים זמינים לניתוח בטווח התאריכים שנבחר."]

    top_categories = ", ".join(
        f"{category} ({count})" for category, count in categories.most_common(3)
    )
    total = len(posts)
    equipped_share = round((equipped_count / total) * 100)
    direct_examples = [
        post
        for post in posts
        if post.analysis
        and post.analysis.category in {"Reporting", "Education", "Advocacy", "Community Action", "Toolkit or Resource"}
    ]

    lines = [
        f"בפוסטים הציבוריים שנמצאו, הדגש המרכזי הוא: {top_categories}.",
        f"{equipped_count} מתוך {total} פוסטים ({equipped_share}%) כוללים הכוונה או כלי פעולה לעוקבים.",
    ]
    if direct_examples:
        lines.append(
            "החשבונות משתמשים בעיקר בהזמנות ללמידה, אירועים קהילתיים, דיווח על אירועים "
            "ושיתוף משאבים כדי לצייד את העוקבים להתמודדות עם אנטישמיות."
        )
    else:
        lines.append(
            "רוב הפוסטים שנמצאו מתמקדים במודעות ובהקשר ציבורי, עם מעט הנחיות פעולה ישירות."
        )
    return lines


def translate_warning(warning: str) -> str:
    prefix = "No public post URLs found for "
    if warning.startswith(prefix):
        account = warning.removeprefix(prefix).rstrip(".")
        return f"לא נמצאו קישורי פוסטים ציבוריים עבור {account} בגלישה ללא התחברות."
    return warning


def category_label(value: str) -> str:
    return CATEGORY_LABELS_HE.get(value, value)


def tone_label(value: str) -> str:
    return TONE_LABELS_HE.get(value, value)
