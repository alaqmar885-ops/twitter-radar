"""Reddit via old.reddit .rss (primary) and PullPush (fallback)."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"


class RedditSource(BaseSource):
    name = "reddit"
    platform = "reddit"

    def fetch(self, limit: int = 25) -> list:
        items = []
        for sub in getattr(self.cfg, "subreddits", []) or []:
            got = self._rss(sub, limit)
            if not got:
                got = self._pullpush(sub, limit)
            items.extend(got)
            self._sleep()
        return items

    def _rss(self, sub: str, limit: int) -> list:
        url = f"https://old.reddit.com/r/{sub}/.rss"
        try:
            r = self._get(url)
            if r.status_code != 200:
                log.warning("reddit %s .rss -> HTTP %s", sub, r.status_code)
                return []
            root = ET.fromstring(r.content)
            out = []
            for e in root.findall(f"{ATOM}entry")[:limit]:
                eid = (e.findtext(f"{ATOM}id") or "").split("/")[-1]
                link = ""
                le = e.find(f"{ATOM}link")
                if le is not None:
                    link = le.get("href") or ""
                content_el = e.find(f"{ATOM}content")
                text = self._clean(content_el.text if content_el is not None else "")
                out.append(Item(
                    id=f"rd:{eid}", platform="reddit",
                    author=(e.findtext(f"{ATOM}author") or "").replace("/u/", ""),
                    title=e.findtext(f"{ATOM}title") or "", text=text, url=link,
                    created_at=e.findtext(f"{ATOM}updated") or "",
                    metrics={}, source=self.name, query=sub,
                ))
            return out
        except Exception as exc:  # noqa: BLE001
            log.warning("reddit %s .rss failed: %s", sub, exc)
            return []

    def _pullpush(self, sub: str, limit: int) -> list:
        url = "https://api.pullpush.io/reddit/search/submission/"
        try:
            r = self._get(url, params={"subreddit": sub, "size": limit, "sort": "desc"},
                          timeout=12)
            if r.status_code != 200:
                return []
            out = []
            for d in (r.json().get("data") or [])[:limit]:
                pid = d.get("id") or ""
                out.append(Item(
                    id=f"rd:{pid}", platform="reddit", author=d.get("author") or "",
                    title=d.get("title") or "",
                    text=(d.get("selftext") or d.get("url") or "")[:400],
                    url=f"https://reddit.com/comments/{pid}",
                    created_at=str(d.get("created_utc") or ""),
                    metrics={"score": d.get("score") or 0,
                             "comments": d.get("num_comments") or 0},
                    source=self.name, query=sub,
                ))
            return out
        except Exception as exc:  # noqa: BLE001
            log.debug("pullpush %s failed: %s", sub, exc)
            return []
