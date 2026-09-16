"""twifork backend — KEYWORD SEARCH (requires login cookies).

twifork is a maintained fork of twikit that fixes 15+ upstream bugs so
Twitter's internal GraphQL API actually works in 2026.  It's the primary
way to do *keyword search* (which is login-gated on X).

Install:
    pip install twifork
    pip install "twifork[impersonate]"   # browser TLS fingerprint — avoids 403s

Auth: provide a cookies file (ct0 + auth_token exported from a browser session
on a THROWAWAY account — ban risk exists with aggressive use).  This backend
is only `available()` when twifork is installed AND a cookies file is present.

If twifork isn't installed or no cookies are configured, the router silently
skips this backend and falls back to no-auth endpoints.  This keeps the system
running even on a fresh VPS before the operator sets up accounts.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from ..models import Author, Backend, BackendResult, Tweet
from .base import BaseBackend

log = logging.getLogger(__name__)


class TwiForkBackend(BaseBackend):
    name = Backend.TWIFORK

    def __init__(
        self,
        cookies_path: str = "",
        timeout: int = 20,
        delay: float = 1.5,
    ):
        super().__init__(timeout=timeout, delay=delay)
        self.cookies_path = cookies_path
        self._client: Any = None

    def available(self) -> bool:
        if not self.cookies_path:
            return False
        if not os.path.exists(self.cookies_path):
            log.debug("twifork cookies file not found: %s", self.cookies_path)
            return False
        try:
            import twifork  # noqa: F401  — just probing import
            return True
        except ImportError:
            log.debug("twifork not installed — keyword search backend disabled")
            return False

    def supports_keyword_search(self) -> bool:
        return True

    def _get_client(self) -> Any:
        """Lazy-init the twifork client with cookies + TLS impersonation."""
        if self._client is not None:
            return self._client
        try:
            from twikit import Client
        except ImportError:
            # Try the twifork package directly if the shim name differs.
            from twifork.twikit import Client  # type: ignore

        try:
            client = Client("en-US", impersonate="chrome124")
        except TypeError:
            # Older versions don't support impersonate kwarg.
            client = Client("en-US")
        self._client = client
        return client

    def search(self, query: str, limit: int = 20) -> BackendResult:
        """Keyword search via twifork's internal-API client.

        twikit/twifork is async-only, so we run it in an event loop.  The
        cookies file is loaded on first use (avoids re-login every call).
        """
        if not self.available():
            return BackendResult(
                ok=False, error="not_available", backend=self.name
            )

        async def _run() -> BackendResult:
            try:
                client = self._get_client()
                # Load saved cookies (avoids re-login + anti-bot friction).
                await client.load_cookies(self.cookies_path)
                tweets_raw = await client.search_tweet(query, "Latest", limit)
            except Exception as exc:  # noqa: BLE001
                log.warning("twifork search '%s' failed: %s", query, exc)
                return BackendResult(ok=False, error=str(exc), backend=self.name)

            tweets: list[Tweet] = []
            for t in tweets_raw:
                tw = self._parse(t)
                if tw:
                    tweets.append(tw)

            self._sleep()
            log.info("twifork search '%s' → %d tweets", query, len(tweets))
            return BackendResult(ok=True, tweets=tweets, backend=self.name)

        return asyncio.get_event_loop().run_until_complete(_run()) \
            if not asyncio.get_event_loop().is_running() \
            else asyncio.ensure_future(_run())  # caller must await

    def _parse(self, t: Any) -> Tweet | None:
        """Parse a twikit/twifork tweet object into our Tweet model.

        twikit objects expose attributes dynamically; we guard everything.
        """
        tid = getattr(t, "id", None) or getattr(t, "id_str", None)
        if not tid:
            return None
        user = getattr(t, "user", None)
        author = Author(
            screen_name=getattr(user, "screen_name", "") if user else "",
            user_id=str(getattr(user, "id", "") if user else ""),
            name=getattr(user, "name", "") if user else "",
            followers=int(getattr(user, "followers_count", 0) if user else 0),
            following=int(getattr(user, "following_count", 0) if user else 0),
            verified=bool(getattr(user, "is_blue_verified", False) if user else False),
            description=getattr(user, "description", "") if user else "",
        )
        return Tweet(
            tweet_id=str(tid),
            text=getattr(t, "text", ""),
            author=author,
            created_at=getattr(t, "created_at", ""),
            like_count=int(getattr(t, "favorite_count", 0)),
            reply_count=int(getattr(t, "reply_count", 0)),
            retweet_count=int(getattr(t, "retweet_count", 0)),
            quote_count=int(getattr(t, "quote_count", 0)),
            bookmark_count=int(getattr(t, "bookmark_count", 0)),
            lang=getattr(t, "lang", ""),
            url=self._build_url(str(tid), author.screen_name),
            reply_to_id=str(getattr(t, "in_reply_to_status_id_str", "") or "") or None,
            source_backend=self.name,
        )
