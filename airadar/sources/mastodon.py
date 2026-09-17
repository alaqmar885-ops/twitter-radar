"""Mastodon public tag timelines (no auth)."""
from __future__ import annotations

import logging

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)


class MastodonSource(BaseSource):
    name = "mastodon"
    platform = "mastodon"

    def fetch(self, limit: int = 25) -> list:
        base = (getattr(self.cfg, "mastodon_instance", "") or "https://mastodon.social").rstrip("/")
        items = []
        for tag in getattr(self.cfg, "mastodon_tags", []) or []:
            url = f"{base}/api/v1/timelines/tag/{tag}"
            try:
                r = self._get(url, params={"limit": limit})
                if r.status_code != 200:
                    log.warning("mastodon #%s -> HTTP %s", tag, r.status_code)
                    continue
                for st in (r.json() or [])[:limit]:
                    acct = st.get("account") or {}
                    items.append(Item(
                        id=f"ma:{st.get('id')}", platform="mastodon",
                        author=acct.get("acct") or acct.get("username") or "",
                        title="", text=self._clean(st.get("content") or ""),
                        url=st.get("url") or st.get("uri") or "",
                        created_at=st.get("created_at") or "",
                        metrics={"favourites": st.get("favourites_count") or 0,
                                 "reblogs": st.get("reblogs_count") or 0},
                        source=self.name, query=tag,
                    ))
            except Exception as exc:  # noqa: BLE001
                log.warning("mastodon #%s failed: %s", tag, exc)
            self._sleep()
        return items
