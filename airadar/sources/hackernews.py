"""Hacker News via the free Algolia search API (no key)."""
from __future__ import annotations

import logging

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)


class HackerNewsSource(BaseSource):
    name = "hackernews"
    platform = "hackernews"
    API = "https://hn.algolia.com/api/v1/search_by_date"

    def fetch(self, limit: int = 25) -> list:
        items = []
        for q in getattr(self.cfg, "hn_queries", []) or []:
            try:
                r = self._get(self.API, params={"query": q, "tags": "story",
                                                "hitsPerPage": limit})
                if r.status_code != 200:
                    log.warning("HN %s -> HTTP %s", q, r.status_code)
                    continue
                for h in (r.json().get("hits") or [])[:limit]:
                    oid = h.get("objectID") or ""
                    items.append(Item(
                        id=f"hn:{oid}", platform="hackernews",
                        author=h.get("author") or "",
                        title=h.get("title") or h.get("story_title") or "",
                        text=h.get("story_text") or "",
                        url=h.get("url") or f"https://news.ycombinator.com/item?id={oid}",
                        created_at=h.get("created_at") or "",
                        metrics={"points": h.get("points") or 0,
                                 "comments": h.get("num_comments") or 0},
                        source=self.name, query=q,
                    ))
            except Exception as exc:  # noqa: BLE001
                log.warning("HN query '%s' failed: %s", q, exc)
            self._sleep()
        return items
