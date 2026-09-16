"""Multi-backend router with automatic fallback.

The router is the heart of the resilience strategy.  Inspired by
x-tweet-fetcher's 3-backend design, it:

  1. Tries backends in priority order (configurable).
  2. Skips backends that report `available() == False` (e.g. twifork without
     cookies, nitter without a URL) — so the system degrades gracefully.
  3. On rate-limit (429) or error, falls through to the next backend.
  4. Deduplicates results by tweet_id across backends (no duplicate work).
  5. Logs which backend produced each batch, so operators can see health.

Key principle from the research: "the single most common failure in this
space is trusting one endpoint to stay up."  This router makes that
structurally impossible.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Optional

from .backends.base import BaseBackend
from .backends.fxtwitter import FxTwitterBackend
from .backends.nitter import NitterBackend
from .backends.oembed import OEmbedBackend
from .backends.syndication import SyndicationBackend
from .backends.twifork import TwiForkBackend
from .config import Config
from .models import Backend, BackendResult, Tweet

log = logging.getLogger(__name__)

# Registry: backend name string → constructor (lazy, takes the Config).
BACKEND_CLASSES: dict[str, type[BaseBackend]] = {
    "fxtwitter": FxTwitterBackend,
    "syndication": SyndicationBackend,
    "oembed": OEmbedBackend,
    "twifork": TwiForkBackend,
    "nitter": NitterBackend,
}


class Router:
    """Owns backend instances and routes calls with fallback."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._backends: dict[str, BaseBackend] = OrderedDict()
        self._init_backends()

    def _init_backends(self) -> None:
        """Instantiate backends in priority order, injecting config."""
        for name in self.cfg.backend_order:
            cls = BACKEND_CLASSES.get(name)
            if not cls:
                log.warning("Unknown backend '%s' in config — skipping", name)
                continue
            try:
                if name == "twifork":
                    backend = TwiForkBackend(
                        cookies_path=self.cfg.twifork_cookies,
                        timeout=self.cfg.schedule.per_backend_timeout,
                        delay=self.cfg.schedule.delay_between_requests,
                    )
                elif name == "nitter":
                    backend = NitterBackend(
                        base_url=self.cfg.nitter_url,
                        timeout=self.cfg.schedule.per_backend_timeout,
                        delay=self.cfg.schedule.delay_between_requests,
                    )
                else:
                    backend = cls(
                        timeout=self.cfg.schedule.per_backend_timeout,
                        delay=self.cfg.schedule.delay_between_requests,
                    )
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to init backend '%s': %s", name, exc)
                continue
            self._backends[name] = backend

        avail = [n for n, b in self._backends.items() if b.available()]
        log.info("Router ready. Available backends: %s", ", ".join(avail) or "(none)")
        if not avail:
            log.error(
                "No backends available! Check config: twifork needs cookies, "
                "nitter needs a URL. FxTwitter/Syndication/OEmbed should "
                "always work."
            )

    @property
    def available_backends(self) -> list[str]:
        return [n for n, b in self._backends.items() if b.available()]

    # -- routing operations ----------------------------------------------------

    def search(self, query: str, limit: int = 20) -> BackendResult:
        """Keyword search.  Only twifork supports this (login required).

        Falls back to no result if twifork isn't available — keyword search
        is the one capability that's genuinely gated behind a login on X.
        """
        for name, backend in self._backends.items():
            if not backend.available() or not backend.supports_keyword_search():
                continue
            log.debug("Router.search → trying %s", name)
            result = backend.search(query, limit=limit)
            if result.ok and result.tweets:
                return result
            if result.rate_limited:
                log.warning("Backend %s rate-limited on search — falling back", name)
                continue
            log.debug("Backend %s returned no results for search: %s", name, result.error)
        return BackendResult(ok=False, error="no_backend_for_search", backend=Backend.TWIFORK)

    def get_timeline(self, handle: str, limit: int = 25) -> BackendResult:
        """Fetch a user timeline.  Priority: fxtwitter (no-auth) → nitter."""
        seen_ids: set[str] = set()
        merged: list[Tweet] = []
        used_backend = Backend.FXTWITTER

        for name, backend in self._backends.items():
            if not backend.available() or not backend.supports_timeline():
                continue
            log.debug("Router.get_timeline(@%s) → trying %s", handle, name)
            result = backend.get_timeline(handle, limit=limit)
            if result.ok and result.tweets:
                for tw in result.tweets:
                    if tw.tweet_id not in seen_ids:
                        seen_ids.add(tw.tweet_id)
                        merged.append(tw)
                used_backend = result.backend
                if len(merged) >= limit:
                    break
            elif result.rate_limited:
                log.warning("Backend %s rate-limited on timeline @%s", name, handle)
                continue
            else:
                log.debug("Backend %s no timeline: %s", name, result.error)

        if not merged:
            return BackendResult(
                ok=False, error="all_timeline_backends_failed", backend=used_backend
            )
        return BackendResult(ok=True, tweets=merged[:limit], backend=used_backend)

    def get_tweet(self, tweet_id: str, handle: str = "i") -> BackendResult:
        """Fetch a single tweet.  Priority: fxtwitter → syndication → oembed."""
        for name, backend in self._backends.items():
            if not backend.available() or not backend.supports_single_tweet():
                continue
            log.debug("Router.get_tweet(%s) → trying %s", tweet_id, name)
            if name == "oembed":
                result = backend.get_tweet(tweet_id, handle=handle)
            else:
                result = backend.get_tweet(tweet_id)
            if result.ok and result.tweets:
                return result
            if result.rate_limited:
                log.warning("Backend %s rate-limited on tweet %s", name, tweet_id)
                continue
            log.debug("Backend %s failed tweet %s: %s", name, tweet_id, result.error)
        return BackendResult(ok=False, error="all_tweet_backends_failed", backend=Backend.OEMBED)

    def reconstruct_thread(self, tweet_id: str) -> BackendResult:
        """Reconstruct a full thread.  Only Syndication supports parent nesting."""
        backend = self._backends.get("syndication")
        if backend and backend.available():
            return backend.reconstruct_thread(tweet_id)  # type: ignore[attr-defined]
        # Fallback: just get the single tweet from any backend.
        return self.get_tweet(tweet_id)
