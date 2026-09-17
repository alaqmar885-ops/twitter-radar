"""Source registry - one import guard per module."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

SOURCE_REGISTRY: dict = {}


def _register(name, module, cls_name):
    try:
        mod = __import__(f"{__name__}.{module}", fromlist=[cls_name])
        SOURCE_REGISTRY[name] = getattr(mod, cls_name)
    except Exception as exc:  # noqa: BLE001
        log.warning("source '%s' unavailable (%s): %s", name, module, exc)


_register("twitter", "twitter", "TwitterSource")
_register("hackernews", "hackernews", "HackerNewsSource")
_register("telegram", "telegram", "TelegramSource")
_register("mastodon", "mastodon", "MastodonSource")
_register("reddit", "reddit", "RedditSource")
_register("rss", "rss", "RssSource")
_register("html", "html_watch", "HtmlWatchSource")
_register("youtube", "youtube", "YouTubeSource")
_register("threads", "threads", "ThreadsSource")
_register("bluesky", "bluesky", "BlueskySource")
_register("instagram", "instagram", "InstagramSource")

__all__ = ["SOURCE_REGISTRY"]
