"""YouTube channel uploads via RSS (no API key).

The feed endpoint may be blocked (404/500) from some hosts; channel-id
resolution via the channel page's canonical link is verified working.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"


class YouTubeSource(BaseSource):
    name = "youtube"
    platform = "youtube"

    def fetch(self, limit: int = 25) -> list:
        items = []
        for entry in getattr(self.cfg, "youtube_channel_ids", []) or []:
            cid = entry
            if entry.startswith("@"):
                cid = self.resolve_channel_id(entry) or ""
                if not cid:
                    log.warning("youtube: could not resolve %s", entry)
                    continue
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
            try:
                r = self._get(url)
                if r.status_code != 200:
                    log.warning("youtube %s -> HTTP %s", cid, r.status_code)
                    continue
                root = ET.fromstring(r.content)
                for e in root.findall(f"{ATOM}entry")[:limit]:
                    vid = e.findtext(f"{YT}videoId") or ""
                    link_el = e.find(f"{ATOM}link")
                    link = link_el.get("href") if link_el is not None else ""
                    stats = e.find(f"{MEDIA}group/{MEDIA}community/{MEDIA}statistics")
                    views = 0
                    if stats is not None:
                        try:
                            views = int(stats.get("views") or 0)
                        except Exception:
                            views = 0
                    items.append(Item(
                        id=f"yt:{vid}", platform="youtube",
                        author=e.findtext(f"{ATOM}author/{ATOM}name") or "",
                        title=e.findtext(f"{ATOM}title") or "", text="",
                        url=link or f"https://www.youtube.com/watch?v={vid}",
                        created_at=e.findtext(f"{ATOM}published") or "",
                        metrics={"views": views}, source=self.name, query=cid,
                    ))
            except Exception as exc:  # noqa: BLE001
                log.warning("youtube %s failed: %s", cid, exc)
            self._sleep()
        return items

    def resolve_channel_id(self, handle: str) -> str:
        import re
        h = handle if handle.startswith("@") else "@" + handle
        try:
            r = self._get(f"https://www.youtube.com/{h}")
            if r.status_code != 200:
                return ""
            m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', r.text)
            if not m:
                m = re.search(r'"externalId":"(UC[\w-]{22})"', r.text)
            return m.group(1) if m else ""
        except Exception:
            return ""
