"""Generic RSS/Atom feeds (vendor blogs, aggregators)."""
from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"


class RssSource(BaseSource):
    name = "rss"
    platform = "rss"

    def fetch(self, limit: int = 25) -> list:
        items = []
        for feed in getattr(self.cfg, "rss_feeds", []) or []:
            try:
                r = self._get(feed)
                if r.status_code != 200:
                    log.warning("rss %s -> HTTP %s", feed, r.status_code)
                    continue
                items.extend(self._parse(r.content, feed, limit))
            except Exception as exc:  # noqa: BLE001
                log.warning("rss %s failed: %s", feed, exc)
            self._sleep()
        return items

    def _parse(self, content: bytes, feed: str, limit: int) -> list:
        out = []
        try:
            root = ET.fromstring(content)
        except Exception:
            return out
        # Atom
        entries = root.findall(f"{ATOM}entry")
        if entries:
            for e in entries[:limit]:
                link = ""
                le = e.find(f"{ATOM}link")
                if le is not None:
                    link = le.get("href") or ""
                guid = e.findtext(f"{ATOM}id") or link
                body = e.findtext(f"{ATOM}summary") or e.findtext(f"{ATOM}content") or ""
                out.append(self._mk(guid, e.findtext(f"{ATOM}title") or "", body, link,
                                    e.findtext(f"{ATOM}updated") or "", feed))
            return out
        # RSS 2.0
        for it in root.iter("item"):
            title = it.findtext("title") or ""
            link = it.findtext("link") or ""
            guid = it.findtext("guid") or link or title
            body = it.findtext("description") or ""
            out.append(self._mk(guid, title, body, link, it.findtext("pubDate") or "", feed))
            if len(out) >= limit:
                break
        return out

    def _mk(self, guid: str, title: str, body: str, link: str, when: str, feed: str) -> Item:
        h = hashlib.sha1((guid or link or title).encode("utf-8", "ignore")).hexdigest()[:16]
        return Item(id=f"rss:{h}", platform="rss", author="", title=title,
                    text=self._clean(body)[:500], url=link, created_at=when,
                    metrics={}, source=self.name, query=feed)
