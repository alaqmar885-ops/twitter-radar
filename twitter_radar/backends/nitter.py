"""Nitter backend — self-hosted fallback.

Nitter serves static HTML (no JS, no anti-bot) so it's trivially scrapable
with BeautifulSoup.  Public instances are unreliable, but self-hosting
changes the calculus: the failure mode shifts from "does X block me" to
"do I keep my instance alive".

    docker run -d -p 8788:8080 --name nitter zedeus/nitter:latest

This backend is only `available()` when a Nitter URL is configured and
responds.  Treat as a backend of last resort / secondary source, not primary.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..models import Author, Backend, BackendResult, Tweet
from .base import BaseBackend

log = logging.getLogger(__name__)


class NitterBackend(BaseBackend):
    name = Backend.NITTER

    def __init__(self, base_url: str = "", timeout: int = 20, delay: float = 1.5):
        super().__init__(timeout=timeout, delay=delay)
        self.base_url = (base_url or "").rstrip("/")

    def available(self) -> bool:
        if not self.base_url:
            return False
        # Quick liveness probe.
        try:
            r = httpx.get(
                self.base_url, timeout=5, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def supports_timeline(self) -> bool:
        return True

    def supports_single_tweet(self) -> bool:
        return True

    def get_timeline(self, handle: str, limit: int = 25) -> BackendResult:
        handle = handle.lstrip("@")
        url = f"{self.base_url}/{handle}"
        try:
            r = httpx.get(
                url, timeout=self.timeout, follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 429:
                return BackendResult(
                    ok=False, error="rate_limited", backend=self.name, rate_limited=True
                )
            if r.status_code != 200:
                return BackendResult(
                    ok=False, error=f"HTTP {r.status_code}", backend=self.name
                )
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception as exc:  # noqa: BLE001
            return BackendResult(ok=False, error=str(exc), backend=self.name)

        tweets: list[Tweet] = []
        for item in soup.select(".timeline .timeline-item")[:limit]:
            tw = self._parse_item(item, handle)
            if tw:
                tweets.append(tw)

        self._sleep()
        log.info("Nitter timeline @%s → %d tweets", handle, len(tweets))
        return BackendResult(ok=True, tweets=tweets, backend=self.name)

    def _parse_item(self, item, handle: str) -> Tweet | None:
        """Parse a Nitter timeline-item element."""
        # Tweet ID from the .tweet-link href: /user/status/123
        link = item.select_one("a.tweet-link")
        if not link:
            return None
        href = link.get("href", "")
        m = re.search(r"/status/(\d+)", href)
        if not m:
            return None
        tid = m.group(1)

        # Text
        body = item.select_one(".tweet-content")
        text = body.get_text("\n", strip=True) if body else ""

        # Stats
        def _stat(cls: str) -> int:
            el = item.select_one(f".{cls}")
            if not el:
                return 0
            txt = el.get_text(strip=True).replace(",", "")
            try:
                return int(txt)
            except ValueError:
                return 0

        return Tweet(
            tweet_id=tid,
            text=text,
            author=Author(screen_name=handle),
            created_at="",  # Nitter shows relative dates; skip for reliability
            like_count=_stat("icon-heart"),
            reply_count=_stat("icon-comment"),
            retweet_count=_stat("icon-retweet"),
            url=self._build_url(tid, handle),
            source_backend=self.name,
        )
