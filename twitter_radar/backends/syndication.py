"""Syndication API backend — NO AUTH, NO LOGIN, FREE.

Endpoint:  GET https://cdn.syndication.twimg.com/tweet-result?id={id}&token=0

This is the endpoint that powers embedded tweets on third-party sites.  It's
on a CDN, tolerant of default User-Agents, and — crucially — when you fetch a
**reply**, the response includes a `parent` field with the *full parent tweet
object*.  That means 2 fetches reconstruct a complete 3-tweet thread.

Returns HTTP 200 with a `TweetTombstone` payload for deleted/suspended tweets
— code must handle this.

Note: the *timeline* variant (syndication.twitter.com/srv/timeline-profile/...)
IS rate-limited from datacenter IPs (HTTP 429).  This backend only does single
tweets + thread reconstruction, which are reliable.
"""

from __future__ import annotations

import logging

import httpx

from ..models import Author, Backend, BackendResult, Tweet
from .base import BaseBackend

log = logging.getLogger(__name__)

BASE = "https://cdn.syndication.twimg.com/tweet-result"


class SyndicationBackend(BaseBackend):
    name = Backend.SYNDICATION

    def available(self) -> bool:
        return True

    def supports_single_tweet(self) -> bool:
        return True

    def get_tweet(self, tweet_id: str) -> BackendResult:
        """Fetch a single tweet.  If it's a reply, the parent is included."""
        url = f"{BASE}?id={tweet_id}&token=0"
        try:
            r = httpx.get(
                url,
                timeout=self.timeout,
                follow_redirects=True,
                headers={"Accept": "application/json"},
            )
        except Exception as exc:  # noqa: BLE001
            return BackendResult(ok=False, error=str(exc), backend=self.name)

        if r.status_code == 429:
            return BackendResult(
                ok=False, error="rate_limited", backend=self.name, rate_limited=True
            )
        if r.status_code != 200:
            return BackendResult(
                ok=False, error=f"HTTP {r.status_code}", backend=self.name
            )

        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            return BackendResult(ok=False, error="bad_json", backend=self.name)

        # Handle tombstone (deleted / suspended account)
        typename = data.get("__typename", "")
        if typename == "TweetTombstone" or "tombstone" in data:
            return self._tombstone_result(self.name)

        tweet = self._parse(data)
        if not tweet:
            return BackendResult(ok=False, error="parse_fail", backend=self.name)

        self._sleep()
        return BackendResult(ok=True, tweets=[tweet], backend=self.name)

    def reconstruct_thread(self, tweet_id: str, max_depth: int = 10) -> BackendResult:
        """Walk the `in_reply_to_status_id_str` chain upward to get a full thread.

        Each Syndication fetch of a reply includes the immediate `parent`, so
        we can walk the chain with minimal requests.  We cap at `max_depth`
        to avoid runaway loops on edge cases.
        """
        tweets: list[Tweet] = []
        seen: set[str] = set()
        current_id = tweet_id
        depth = 0

        while current_id and current_id not in seen and depth < max_depth:
            seen.add(current_id)
            result = self.get_tweet(current_id)
            if not result.ok or not result.tweets:
                break
            tw = result.tweets[0]
            tweets.append(tw)
            # Try the embedded parent first (saves a request)
            parent_data = (tw.raw or {}).get("parent") if tw.raw else None
            if parent_data:
                parent = self._parse(parent_data)
                if parent:
                    tweets.append(parent)
                    current_id = parent.reply_to_id or ""
                    if not current_id:
                        break
                    continue
            current_id = tw.reply_to_id or ""
            depth += 1

        # Reverse so the thread reads top-down (root first)
        tweets.reverse()
        log.info(
            "Syndication thread from %s → %d tweets", tweet_id, len(tweets)
        )
        return BackendResult(ok=True, tweets=tweets, backend=self.name)

    # -- parser ----------------------------------------------------------------

    def _parse(self, data: dict) -> Tweet | None:
        if not data:
            return None
        tid = str(data.get("id_str") or data.get("id") or "")
        if not tid:
            return None
        user = data.get("user") or {}
        author = Author(
            screen_name=user.get("screen_name", ""),
            user_id=str(user.get("id_str") or ""),
            name=user.get("name", ""),
            verified=bool(user.get("is_blue_verified")),
            profile_url=f"https://x.com/{user.get('screen_name', '')}",
        )
        return Tweet(
            tweet_id=tid,
            text=data.get("text") or "",
            author=author,
            created_at=data.get("created_at") or "",
            like_count=int(data.get("favorite_count") or 0),
            reply_count=int(data.get("conversation_count") or 0),
            retweet_count=int(data.get("retweet_count") or 0),
            quote_count=int(data.get("quote_count") or 0),
            bookmark_count=int(data.get("bookmark_count") or 0),
            lang=data.get("lang") or "",
            url=self._build_url(tid, author.screen_name),
            reply_to_id=data.get("in_reply_to_status_id_str"),
            source_backend=self.name,
            raw=data,
        )
