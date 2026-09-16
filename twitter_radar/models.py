"""Data models for TwitterRadar.

All backends normalize their output into these dataclasses so the router,
confidence engine, and digest renderer can treat data uniformly regardless
of which endpoint produced it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Backend(str, Enum):
    FXTWITTER = "fxtwitter"
    SYNDICATION = "syndication"
    OEMBED = "oembed"
    TWIFORK = "twifork"
    NITTER = "nitter"
    YOU_WEB = "you-web"


class FindingType(str, Enum):
    FREE_AI_SERVICE = "free_ai_service"
    SUBSCRIPTION_OFFER = "subscription_offer"
    NEWS = "news"
    LAUNCH = "launch"
    DISCOUNT = "discount"
    GENERAL = "general"


@dataclass
class Author:
    """A Twitter/X account."""
    screen_name: str = ""
    user_id: str = ""
    name: str = ""
    description: str = ""
    followers: int = 0
    following: int = 0
    verified: bool = False
    profile_url: str = ""

    @property
    def credibility_tier(self) -> int:
        """Heuristic credibility tier 1-5 (5 = most credible).

        Combines follower count and verification status.  This is a signal,
        not a guarantee — the confidence engine cross-checks with web sources.
        """
        if self.verified and self.followers >= 100_000:
            return 5
        if self.followers >= 100_000:
            return 4
        if self.followers >= 10_000:
            return 3
        if self.followers >= 1_000:
            return 2
        return 1


@dataclass
class Tweet:
    """A normalized tweet from any backend."""
    tweet_id: str
    text: str = ""
    author: Author = field(default_factory=Author)
    created_at: str = ""          # ISO 8601
    like_count: int = 0
    reply_count: int = 0
    retweet_count: int = 0
    quote_count: int = 0
    bookmark_count: int = 0
    lang: str = ""
    url: str = ""
    media: list[dict] = field(default_factory=list)
    reply_to_id: Optional[str] = None        # parent tweet id (thread)
    parent_tweet: Optional["Tweet"] = None    # resolved parent (Syndication)
    source_backend: Backend = Backend.FXTWITTER
    fetched_at: float = field(default_factory=time.time)
    raw: Optional[dict] = None               # original payload for debugging

    @property
    def engagement_score(self) -> int:
        """Weighted engagement — replies and quotes signal discussion, not just likes."""
        return self.like_count + (self.reply_count * 3) + (self.quote_count * 2) + self.retweet_count

    @property
    def is_thread_member(self) -> bool:
        return self.reply_to_id is not None


@dataclass
class Finding:
    """A deduplicated, classified intelligence item extracted from one or more tweets.

    A Finding groups tweets that report the same underlying claim (e.g. "Cursor
    is giving 2 weeks free Pro").  The confidence engine scores how trustworthy
    the claim is, optionally after web verification via You.com.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    finding_type: FindingType = FindingType.GENERAL
    headline: str = ""               # one-line summary
    summary: str = ""               # 1-3 sentence detail
    tweets: list[Tweet] = field(default_factory=list)   # supporting tweets
    topic: str = ""                 # which configured topic this matched
    confidence: float = 0.0         # 0.0 - 1.0, set by confidence engine
    confidence_label: str = "LOW"   # LOW / MEDIUM / HIGH / VERIFIED
    web_verified: bool = False      # confirmed via You.com search
    web_sources: list[dict] = field(default_factory=list)  # corroborating URLs
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def merge_tweet(self, tweet: Tweet) -> None:
        """Add a supporting tweet and bump last_updated."""
        self.tweets.append(tweet)
        self.last_updated = time.time()

    @property
    def source_count(self) -> int:
        return len(self.tweets)

    @property
    def top_tweet(self) -> Optional[Tweet]:
        """Highest-engagement supporting tweet — used for citations."""
        if not self.tweets:
            return None
        return max(self.tweets, key=lambda t: t.engagement_score)

    @property
    def best_author(self) -> Optional[Author]:
        """Highest-credibility author among supporting tweets."""
        if not self.tweets:
            return None
        return max(self.tweets, key=lambda t: t.author.credibility_tier).author


# ---------------------------------------------------------------------------
# Router result
# ---------------------------------------------------------------------------

@dataclass
class BackendResult:
    """Wrapper for a backend call outcome, used by the router for fallback logic."""
    ok: bool
    tweets: list[Tweet] = field(default_factory=list)
    error: str = ""
    backend: Backend = Backend.FXTWITTER
    rate_limited: bool = False
    tombstones: int = 0   # count of deleted/suspended tweets encountered
