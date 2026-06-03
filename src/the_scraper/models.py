from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ActionCategory = Literal[
    "Reporting",
    "Education",
    "Advocacy",
    "Community Action",
    "Toolkit or Resource",
    "Incident Response",
    "Commemoration",
    "Awareness",
    "Other",
]

Tone = Literal[
    "Empowering",
    "Urgent",
    "Informative",
    "Solidarity",
    "Protective",
    "Commemorative",
    "Other",
]


class PostAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: ActionCategory = "Other"
    strategy: str = ""
    tone: Tone = "Other"
    target_audience: str = ""
    follower_action: str = ""
    equips_followers: bool = False
    urgency: int = Field(default=1, ge=1, le=5)
    actionability_score: int = Field(default=1, ge=1, le=5)
    evidence: str = ""


class InstagramPost(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    account: str
    account_url: str
    post_url: str
    timestamp: datetime | None = None
    caption: str = ""
    likes: int | None = None
    comments: int | None = None
    screenshot_path: str | None = None
    media_url: str | None = None
    media_path: str | None = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    analysis: PostAnalysis | None = None


class ScrapeDataset(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str = "instagram_public_pages"
    since: datetime | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    posts: list[InstagramPost] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
