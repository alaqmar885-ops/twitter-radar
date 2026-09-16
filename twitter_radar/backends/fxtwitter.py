"""FxTwitter backend — NO AUTH, NO LOGIN, FREE.

Two working endpoints (both verified live):
  1. Single tweet:  GET https://api.fxtwitter.com/{user}/status/{id}
     → richest free payload: text, raw_text facets, author followers/following/
       likes/media_count/bio, media, quotes.

  2. Profile timeline:  GET https://api.fxtwitter.com/2/profile/{handle}/statuses
     → a user's recent tweets as JSON — free, no login, no account.
     (This is the rare "no-account timeline" endpoint from the research report.)

FxTwitter is a volunteer-run service (FixTweet/FxEmbed).  Treat as a primary
no-auth source but always wire in a fallback — it can rate-limit or go down.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import Author, Backend, BackendResult, Tweet
from .base import BaseBackend

log = logging.getLogger(__name__)

BASE = "https://api.fxtwitter.com"

# FxTwitter sits behind Cloudflare which blocks httpx's default python-httpx
# User-Agent.  Send a browser-like UA so requests go through cleanly.
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


class FxTwitterBackend(BaseBackend):
    name = Backend.FXTWITTER

    def available(self) -> bool:
        # Always available — no deps beyond httpx, no auth.
        return True

    def supports_timeline(self) -> bool:
        return True

    def supports_single_tweet(self) -> bool:
        return True

    # -- timeline ---------------------------------------------------------------

    def get_timeline(self, handle: str, limit: int = 25) -> BackendResult:
        """Fetch recent tweets from a user's timeline — no login required."""
        handle = handle.lstrip("@")
        url = f"{BASE}/2/profile/{handle}/statuses"
        try:
            r = httpx.get(url, timeout=self.timeout, follow_redirects=True, headers=HEADERS)
            if r.status_code == 429:
                return BackendResult(
                    ok=False, error="rate_limited", backend=self.name, rate_limited=True
                )
            if r.status_code != 200:
                return BackendResult(
                    ok=False,
                    error=f"HTTP {r.status_code}",
                    backend=self.name,
                )
            payload = r.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("FxTwitter timeline %s failed: %s", handle, exc)
            return BackendResult(ok=False, error=str(exc), backend=self.name)

        results = payload.get("results") or payload.get("tweets") or []
        tweets: list[Tweet] = []
        for item in results[:limit]:
            tw = self._parse_timeline_item(item, handle)
            if tw:
                tweets.append(tw)

        self._sleep()
        log.info("FxTwitter timeline @%s → %d tweets", handle, len(tweets))
        return BackendResult(ok=True, tweets=tweets, backend=self.name)

    # -- single tweet -----------------------------------------------------------

    def get_tweet(self, tweet_id: str) -> BackendResult:
        """Fetch a single tweet with rich metadata (author follower counts etc)."""
        url = f"{BASE}/i/status/{tweet_id}"
        try:
            r = httpx.get(url, timeout=self.timeout, follow_redirects=True, headers=HEADERS)
        except Exception as exc:  # noqa: BLE001
            return BackendResult(ok=False, error=str(exc), backend=self.name)

        if r.status_code == 429:
            return BackendResult(
                ok=False, error="rate_limited", backend=self.name, rate_limited=True
            )
        if r.status_code != 200:
            # Fallback: try the /{user}/status/{id} form (needs a handle we
            # may not have).  Skip — caller should use Syndication for this.
            return BackendResult(
                ok=False, error=f"HTTP {r.status_code}", backend=self.name
            )

        try:
            payload = r.json()
        except Exception:  # noqa: BLE001
            return BackendResult(ok=False, error="bad_json", backend=self.name)

        tweet_data = payload.get("tweet") or payload
        tweet = self._parse_single(tweet_data)
        if not tweet:
            return BackendResult(ok=False, error="tombstone_or_empty", backend=self.name)

        self._sleep()
        return BackendResult(ok=True, tweets=[tweet], backend=self.name)

    # -- parsers ----------------------------------------------------------------

    def _parse_timeline_item(self, item: dict, handle: str) -> Tweet | None:
        """Parse a /2/profile/.../statuses result item."""
        if not item:
            return None
        tid = str(item.get("id") or item.get("tweet_id") or "")
        if not tid:
            return None
        text = item.get("text") or item.get("content") or ""
        url = item.get("url") or self._build_url(tid, handle)
        created = item.get("created_at") or item.get("date") or ""
        author = Author(screen_name=handle, profile_url=f"https://x.com/{handle}")
        # If the item embeds author data, use it.
        if item.get("author"):
            author = self._parse_author(item)
        return Tweet(
            tweet_id=tid,
            text=text,
            author=author,
            created_at=created,
            url=url,
            source_backend=self.name,
            raw=item,
        )

    def _parse_single(self, data: dict) -> Tweet | None:
        """Parse a full single-tweet payload (richest)."""
        if not data:
            return None
        tid = str(data.get("id") or "")
        if not tid:
            return None
        author = self._parse_author(data)
        text = data.get("text") or ""
        url = data.get("url") or self._build_url(tid, author.screen_name)
        return Tweet(
            tweet_id=tid,
            text=text,
            author=author,
            created_at=data.get("created_at") or "",
            like_count=int(data.get("likes") or data.get("like_count") or 0),
            reply_count=int(data.get("replies") or data.get("reply_count") or 0),
            retweet_count=int(data.get("retweets") or data.get("retweet_count") or 0),
            quote_count=int(data.get("quotes") or data.get("quote_count") or 0),
            bookmark_count=int(data.get("bookmarks") or 0),
            lang=data.get("lang") or "",
            url=url,
            media=data.get("media", {}).get("all") or [],
            source_backend=self.name,
            raw=data,
        )

    def _parse_author(self, data: dict) -> Author:
        a = data.get("author") or {}
        return Author(
            screen_name=a.get("screen_name") or "",
            user_id=str(a.get("id") or ""),
            name=a.get("name", ""),
            description=a.get("description", ""),
            followers=int(a.get("followers") or 0),
            following=int(a.get("following") or 0),
            verified=bool(a.get("verified")),
            profile_url=f"https://x.com/{a.get('screen_name', '')}",
        )
