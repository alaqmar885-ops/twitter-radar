"""Bluesky public search via the AT Protocol AppView (no auth)."""
from __future__ import annotations

import logging

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)


class BlueskySource(BaseSource):
    name = "bluesky"
    platform = "bluesky"
    API = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"

    def fetch(self, limit: int = 25) -> list:
        items = []
        for q in getattr(self.cfg, "bluesky_queries", []) or []:
            try:
                r = self._get(self.API, params={"q": q, "limit": min(limit, 50)})
                if r.status_code != 200:
                    log.warning("bluesky '%s' -> HTTP %s", q, r.status_code)
                    continue
                for p in (r.json().get("posts") or [])[:limit]:
                    rec = p.get("record") or {}
                    uri = p.get("uri") or ""
                    handle = (p.get("author") or {}).get("handle") or ""
                    rk = uri.rsplit("/", 1)[-1] if uri else ""
                    items.append(Item(
                        id=f"bs:{rk}", platform="bluesky", author=handle,
                        title="", text=rec.get("text") or "",
                        url=f"https://bsky.app/profile/{handle}/post/{rk}" if rk else "",
                        created_at=rec.get("createdAt") or "",
                        metrics={"likes": p.get("likeCount") or 0,
                                 "replies": p.get("replyCount") or 0},
                        source=self.name, query=q,
                    ))
            except Exception as exc:  # noqa: BLE001
                log.warning("bluesky '%s' failed: %s", q, exc)
            self._sleep()
        return items
