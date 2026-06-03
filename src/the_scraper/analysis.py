from __future__ import annotations

import json
import os
from collections.abc import Iterable

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from .models import InstagramPost, PostAnalysis, ScrapeDataset


class AnalyzedPost(BaseModel):
    id: str
    analysis: PostAnalysis


class AnalysisBatch(BaseModel):
    posts: list[AnalyzedPost] = Field(default_factory=list)


SYSTEM_PROMPT = """You analyze public Instagram captions from regional ADL accounts.
Return JSON only. Focus on how a post directs, encourages, or equips followers to
confront, handle, report, respond to, or counter antisemitism.
Categories must be one of:
Reporting, Education, Advocacy, Community Action, Toolkit or Resource,
Incident Response, Commemoration, Awareness, Other.
Be conservative: if there is no explicit or implied follower action, mark
equips_followers=false and use a lower actionability_score.
Use Hebrew for these free-text fields: strategy, target_audience, follower_action,
and evidence. Keep enum values in English exactly as required by the schema."""


def analyze_dataset(
    dataset: ScrapeDataset,
    provider: str = "auto",
    model: str | None = None,
    batch_size: int = 8,
) -> ScrapeDataset:
    load_dotenv()
    model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    use_openai = provider == "openai" or (
        provider == "auto" and bool(os.getenv("OPENAI_API_KEY"))
    )

    if use_openai:
        analyses = analyze_with_openai(dataset.posts, model=model, batch_size=batch_size)
    else:
        analyses = {post.id: analyze_with_rules(post) for post in dataset.posts}

    for post in dataset.posts:
        post.analysis = analyses.get(post.id) or analyze_with_rules(post)

    return dataset


def analyze_with_openai(
    posts: list[InstagramPost],
    model: str,
    batch_size: int = 8,
) -> dict[str, PostAnalysis]:
    client = OpenAI()
    results: dict[str, PostAnalysis] = {}

    for chunk in chunked(posts, batch_size):
        payload = [
            {
                "id": post.id,
                "account": post.account,
                "date": post.timestamp.isoformat() if post.timestamp else None,
                "caption": post.caption[:5000],
            }
            for post in chunk
        ]
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "Analyze these posts as JSON:\n"
                    + json.dumps(payload, ensure_ascii=False),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "adl_instagram_analysis",
                    "schema": AnalysisBatch.model_json_schema(),
                    "strict": False,
                }
            },
        )
        parsed = AnalysisBatch.model_validate_json(response.output_text)
        for item in parsed.posts:
            results[item.id] = item.analysis

    return results


def analyze_with_rules(post: InstagramPost) -> PostAnalysis:
    caption = post.caption.lower()

    if any(word in caption for word in ["report", "hotline", "tip line", "file a complaint"]):
        return PostAnalysis(
            category="Reporting",
            strategy="הפניה ברורה לדיווח על אירועים או תכנים אנטישמיים.",
            tone=tone_for(caption),
            target_audience="עוקבים שנתקלים באנטישמיות",
            follower_action="לדווח על האירוע או התוכן בערוץ שצוין בפוסט.",
            equips_followers=True,
            urgency=4,
            actionability_score=5,
            evidence=first_evidence(post.caption, ["report", "hotline", "complaint"]),
        )

    if any(word in caption for word in ["toolkit", "guide", "resource", "resources", "download"]):
        return PostAnalysis(
            category="Toolkit or Resource",
            strategy="אספקת משאבים, מדריכים או חומרי עזר שניתן להשתמש בהם ולשתף.",
            tone=tone_for(caption),
            target_audience="חברי קהילה שמחפשים הדרכה מעשית",
            follower_action="להשתמש במשאב או לשתף אותו עם אחרים.",
            equips_followers=True,
            urgency=3,
            actionability_score=4,
            evidence=first_evidence(post.caption, ["toolkit", "guide", "resource"]),
        )

    if any(word in caption for word in ["call your", "contact your", "advocate", "legislation"]):
        return PostAnalysis(
            category="Advocacy",
            strategy="עידוד פעולה אזרחית או מוסדית מול מקבלי החלטות.",
            tone=tone_for(caption),
            target_audience="עוקבים שמוכנים לפעול בזירה הציבורית",
            follower_action="לפנות לנציגים, לתמוך במדיניות או להצטרף למהלך הסברה.",
            equips_followers=True,
            urgency=4,
            actionability_score=4,
            evidence=first_evidence(post.caption, ["call", "contact", "advocate"]),
        )

    if any(word in caption for word in ["webinar", "learn", "education", "training", "workshop"]):
        return PostAnalysis(
            category="Education",
            strategy="הזמנה ללמידה, הכשרה או הרחבת מודעות בנושא אנטישמיות.",
            tone=tone_for(caption),
            target_audience="עוקבים שמבקשים ידע וכלים",
            follower_action="להשתתף בהדרכה או לצרוך את חומרי הלמידה.",
            equips_followers=True,
            urgency=2,
            actionability_score=3,
            evidence=first_evidence(post.caption, ["learn", "training", "workshop", "webinar"]),
        )

    if any(word in caption for word in ["join us", "rally", "event", "community", "stand together"]):
        return PostAnalysis(
            category="Community Action",
            strategy="גיוס עוקבים לפעולה קהילתית או ציבורית משותפת.",
            tone=tone_for(caption),
            target_audience="חברי הקהילה המקומית",
            follower_action="להצטרף, להשתתף, להגיע לאירוע או לשתף.",
            equips_followers=True,
            urgency=3,
            actionability_score=4,
            evidence=first_evidence(post.caption, ["join", "rally", "event", "community"]),
        )

    if any(word in caption for word in ["incident", "attack", "threat", "vandalism", "harassment"]):
        return PostAnalysis(
            category="Incident Response",
            strategy="תגובה לאירוע אנטישמי ספציפי והצבתו בהקשר קהילתי או ציבורי.",
            tone=tone_for(caption),
            target_audience="עוקבים מודאגים וקהילות שנפגעו",
            follower_action="להישאר מעודכנים, לתמוך בקהילה שנפגעה או לדווח על אירועים דומים.",
            equips_followers=False,
            urgency=4,
            actionability_score=2,
            evidence=first_evidence(post.caption, ["incident", "attack", "threat", "vandalism"]),
        )

    if any(word in caption for word in ["remember", "memorial", "honor", "commemorate", "yom hashoah"]):
        return PostAnalysis(
            category="Commemoration",
            strategy="שימוש בזיכרון ובהנצחה כדי לחזק ערנות, סולידריות ומחויבות ציבורית.",
            tone="Commemorative",
            target_audience="כלל העוקבים",
            follower_action="לזכור, לשתף או להשתתף בפעילות הנצחה.",
            equips_followers=False,
            urgency=2,
            actionability_score=2,
            evidence=first_evidence(post.caption, ["remember", "honor", "commemorate"]),
        )

    if any(word in caption for word in ["antisemitism", "hate", "bias", "extremism"]):
        return PostAnalysis(
            category="Awareness",
            strategy="העלאת מודעות לאנטישמיות, שנאה, הטיה או קיצוניות.",
            tone=tone_for(caption),
            target_audience="כלל העוקבים",
            follower_action="להכיר את הסוגיה, לדבר עליה ולשתף מידע.",
            equips_followers=False,
            urgency=3,
            actionability_score=2,
            evidence=first_evidence(post.caption, ["antisemitism", "hate", "bias", "extremism"]),
        )

    return PostAnalysis(
        category="Other",
        strategy="לא זוהתה אסטרטגיית פעולה ברורה להתמודדות עם אנטישמיות.",
        tone=tone_for(caption),
        target_audience="כלל העוקבים",
        follower_action="",
        equips_followers=False,
        urgency=1,
        actionability_score=1,
        evidence=post.caption[:180],
    )


def tone_for(caption: str) -> str:
    if any(word in caption for word in ["urgent", "now", "act", "immediately"]):
        return "Urgent"
    if any(word in caption for word in ["together", "stand", "solidarity", "community"]):
        return "Solidarity"
    if any(word in caption for word in ["protect", "safety", "secure", "threat"]):
        return "Protective"
    if any(word in caption for word in ["learn", "facts", "education", "training"]):
        return "Informative"
    if any(word in caption for word in ["empower", "speak up", "take action"]):
        return "Empowering"
    return "Informative"


def first_evidence(caption: str, keywords: list[str]) -> str:
    if not caption:
        return ""
    sentences = [part.strip() for part in caption.replace("\n", " ").split(".") if part.strip()]
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            return sentence[:220]
    return caption[:220]


def chunked(items: list[InstagramPost], size: int) -> Iterable[list[InstagramPost]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
