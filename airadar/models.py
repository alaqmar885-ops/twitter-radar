"""Data models for AIOfferRadar."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Item:
    """One normalized post/video/message from any platform."""
    id: str
    platform: str = ""
    author: str = ""
    title: str = ""
    text: str = ""
    url: str = ""
    created_at: str = ""
    metrics: dict = field(default_factory=dict)
    source: str = ""
    query: str = ""
    raw: dict | None = None
    fetched_at: float = field(default_factory=time.time)

    @property
    def blob(self) -> str:
        return f"{self.title} {self.text}".lower()

    def as_row(self) -> tuple:
        import json
        return (self.id, self.platform, self.author, self.title, self.text, self.url,
                self.created_at, json.dumps(self.metrics or {}), self.source,
                self.query, self.fetched_at)


@dataclass
class Offer:
    """A deduped, scored free-AI-offer finding."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    summary: str = ""
    offer_type: str = "other"
    value: str = ""
    promo_code: str = ""
    product: str = ""
    url: str = ""
    platforms: list = field(default_factory=list)
    items: list = field(default_factory=list)
    score: float = 0.0
    label: str = "LOW"
    link_ok: bool = False
    web_verified: bool = False
    web_sources: list = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    @property
    def source_count(self) -> int:
        return len(self.items)
