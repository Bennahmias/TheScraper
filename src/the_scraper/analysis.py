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
equips_followers=false and use a lower actionability_score."""


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
            strategy="Direct followers to report antisemitic incidents or content.",
            tone=tone_for(caption),
            target_audience="Followers who witness antisemitism",
            follower_action="Report the incident or content through the named channel.",
            equips_followers=True,
            urgency=4,
            actionability_score=5,
            evidence=first_evidence(post.caption, ["report", "hotline", "complaint"]),
        )

    if any(word in caption for word in ["toolkit", "guide", "resource", "resources", "download"]):
        return PostAnalysis(
            category="Toolkit or Resource",
            strategy="Provide reusable resources or guidance materials.",
            tone=tone_for(caption),
            target_audience="Community members seeking practical guidance",
            follower_action="Use or share the provided resource.",
            equips_followers=True,
            urgency=3,
            actionability_score=4,
            evidence=first_evidence(post.caption, ["toolkit", "guide", "resource"]),
        )

    if any(word in caption for word in ["call your", "contact your", "advocate", "legislation"]):
        return PostAnalysis(
            category="Advocacy",
            strategy="Encourage civic or institutional advocacy.",
            tone=tone_for(caption),
            target_audience="Followers willing to take civic action",
            follower_action="Contact representatives or advocate for a stated policy.",
            equips_followers=True,
            urgency=4,
            actionability_score=4,
            evidence=first_evidence(post.caption, ["call", "contact", "advocate"]),
        )

    if any(word in caption for word in ["webinar", "learn", "education", "training", "workshop"]):
        return PostAnalysis(
            category="Education",
            strategy="Invite followers to learn, train, or build awareness.",
            tone=tone_for(caption),
            target_audience="Followers seeking education",
            follower_action="Attend or consume the educational material.",
            equips_followers=True,
            urgency=2,
            actionability_score=3,
            evidence=first_evidence(post.caption, ["learn", "training", "workshop", "webinar"]),
        )

    if any(word in caption for word in ["join us", "rally", "event", "community", "stand together"]):
        return PostAnalysis(
            category="Community Action",
            strategy="Mobilize followers toward collective public or community action.",
            tone=tone_for(caption),
            target_audience="Local community members",
            follower_action="Join, attend, share, or participate.",
            equips_followers=True,
            urgency=3,
            actionability_score=4,
            evidence=first_evidence(post.caption, ["join", "rally", "event", "community"]),
        )

    if any(word in caption for word in ["incident", "attack", "threat", "vandalism", "harassment"]):
        return PostAnalysis(
            category="Incident Response",
            strategy="Frame a response to a specific antisemitic incident.",
            tone=tone_for(caption),
            target_audience="Concerned followers and affected communities",
            follower_action="Stay informed, support affected communities, or report related incidents.",
            equips_followers=False,
            urgency=4,
            actionability_score=2,
            evidence=first_evidence(post.caption, ["incident", "attack", "threat", "vandalism"]),
        )

    if any(word in caption for word in ["remember", "memorial", "honor", "commemorate", "yom hashoah"]):
        return PostAnalysis(
            category="Commemoration",
            strategy="Use remembrance to reinforce vigilance and solidarity.",
            tone="Commemorative",
            target_audience="General followers",
            follower_action="Remember, share, or participate in commemoration.",
            equips_followers=False,
            urgency=2,
            actionability_score=2,
            evidence=first_evidence(post.caption, ["remember", "honor", "commemorate"]),
        )

    if any(word in caption for word in ["antisemitism", "hate", "bias", "extremism"]):
        return PostAnalysis(
            category="Awareness",
            strategy="Raise awareness of antisemitism, hate, or extremism.",
            tone=tone_for(caption),
            target_audience="General followers",
            follower_action="Recognize and discuss the issue.",
            equips_followers=False,
            urgency=3,
            actionability_score=2,
            evidence=first_evidence(post.caption, ["antisemitism", "hate", "bias", "extremism"]),
        )

    return PostAnalysis(
        category="Other",
        strategy="No clear counter-antisemitism action strategy detected.",
        tone=tone_for(caption),
        target_audience="General followers",
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
