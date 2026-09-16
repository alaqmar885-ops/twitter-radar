"""oEmbed backend — NO AUTH, OFFICIAL, FREE.

Endpoint:  GET https://publish.twitter.com/oembed?url=...&omit_script=true

This is X's own sanctioned endpoint.  Limited fields (HTML block + author
name/url + provider), but it's the only officially-blessed free source, so
it's a good last-resort fallback for existence verification and basic
authorship.  Requires `-L` / follow_redirects because it 301s first.
"""

from __future__ import annotations

import logging
import re

import httpx

from ..models import Author, Backend, BackendResult, Tweet
from .base import BaseBackend

log = logging.getLogger(__name__)

BASE = "https://publish.twitter.com/oembed"


class OEmbedBackend(BaseBackend):
    name = Backend.OEMBED

    def available(self) -> bool:
        return True

    def supports_single_tweet(self) -> bool:
        return True

    def get_tweet(self, tweet_id: str, handle: str = "i") -> BackendResult:
        """Fetch via oEmbed.  Best-effort — text is embedded in HTML block.

        `handle` is needed to construct the URL (oEmbed requires a full URL).
        If unknown, use 'i' — but the URL may 404.  Prefer this only as a
        fallback when FxTwitter/Syndication already failed.
        """
        tweet_url = f"https://x.com/{handle}/status/{tweet_id}"
        url = f"{BASE}?url={tweet_url}&omit_script=true"
        try:
            r = httpx.get(url, timeout=self.timeout, follow_redirects=True)
        except Exception as exc:  # noqa: BLE001
            return BackendResult(ok=False, error=str(exc), backend=self.name)

        if r.status_code != 200:
            return BackendResult(
                ok=False, error=f"HTTP {r.status_code}", backend=self.name
            )

        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            return BackendResult(ok=False, error="bad_json", backend=self.name)

        html = data.get("html", "")
        # Extract the tweet text from the blockquote HTML (strip tags).
        text = _strip_html(html)
        author = Author(
            screen_name=_extract_handle(data.get("author_url", ""))
                or handle,
            name=data.get("author_name", ""),
            profile_url=data.get("author_url", ""),
        )
        tweet = Tweet(
            tweet_id=tweet_id,
            text=text,
            author=author,
            url=tweet_url,
            source_backend=self.name,
            raw=data,
        )
        self._sleep()
        return BackendResult(ok=True, tweets=[tweet], backend=self.name)


def _strip_html(html: str) -> str:
    """Extract visible text from a blockquote HTML block."""
    # Remove <br> → newline, then strip all tags.
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip().strip("—").strip()


def _extract_handle(url: str) -> str:
    """https://x.com/levelsio → levelsio"""
    m = re.search(r"x\.com/([A-Za-z0-9_]+)", url)
    return m.group(1) if m else ""
