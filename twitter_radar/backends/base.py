"""Abstract base class for all scraper backends.

Each backend implements a uniform interface so the router can try them in
priority order with automatic fallback.  Backends that require auth (twifork)
or a running service (nitter) gracefully report `available = False` when
their prerequisites aren't met, so the router skips them cleanly.
"""

from __future__ import annotations

import abc
import logging
import time
from typing import Optional

from ..models import Author, Backend, BackendResult, Tweet

log = logging.getLogger(__name__)


class BaseBackend(abc.ABC):
    """Contract for all backends."""

    name: Backend = Backend.FXTWITTER

    def __init__(self, timeout: int = 20, delay: float = 1.5):
        self.timeout = timeout
        self.delay = delay

    @abc.abstractmethod
    def available(self) -> bool:
        """Return True if this backend can run right now (deps + config OK)."""
        ...

    def _sleep(self) -> None:
        """Polite delay between requests to avoid hammering endpoints."""
        if self.delay > 0:
            time.sleep(self.delay)

    # -- optional capabilities -------------------------------------------------
    # Not every backend supports every operation.  The router checks these
    # before calling, so it can pick the right tool for the job.

    def supports_keyword_search(self) -> bool:
        return False

    def supports_timeline(self) -> bool:
        return False

    def supports_single_tweet(self) -> bool:
        return False

    # -- operations (override the ones you support) ----------------------------

    def search(self, query: str, limit: int = 20) -> BackendResult:
        """Keyword search — requires login on most backends."""
        return BackendResult(ok=False, error="not supported", backend=self.name)

    def get_timeline(self, handle: str, limit: int = 25) -> BackendResult:
        """Fetch a user's recent tweets (timeline)."""
        return BackendResult(ok=False, error="not supported", backend=self.name)

    def get_tweet(self, tweet_id: str) -> BackendResult:
        """Fetch a single tweet by ID — optionally with thread context."""
        return BackendResult(ok=False, error="not supported", backend=self.name)

    # -- shared helpers ---------------------------------------------------------

    @staticmethod
    def _build_url(tweet_id: str, screen_name: str) -> str:
        return f"https://x.com/{screen_name}/status/{tweet_id}"

    @staticmethod
    def _tombstone_result(backend: Backend) -> BackendResult:
        """A deleted/suspended tweet — HTTP 200 but a tombstone payload."""
        return BackendResult(
            ok=False, error="tombstone", backend=backend, tombstones=1
        )

    @staticmethod
    def _parse_author(data: dict) -> Author:
        """Best-effort author extraction from varied payload shapes."""
        a = data.get("author") or data.get("user") or {}
        return Author(
            screen_name=a.get("screen_name") or a.get("username", ""),
            user_id=str(a.get("id") or a.get("id_str") or a.get("user_id", "")),
            name=a.get("name", ""),
            description=a.get("description", ""),
            followers=int(a.get("followers") or a.get("followers_count") or 0),
            following=int(a.get("following") or a.get("friends_count") or 0),
            verified=bool(
                a.get("is_blue_verified") or a.get("verified")
                or a.get("is_verified")
            ),
            profile_url=f"https://x.com/{a.get('screen_name') or a.get('username', '')}",
        )
