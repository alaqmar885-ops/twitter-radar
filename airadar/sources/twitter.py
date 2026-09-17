"""Twitter/X source - adapts the existing twitter_radar no-auth router."""
from __future__ import annotations

import logging

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)


class TwitterSource(BaseSource):
    name = "twitter"
    platform = "twitter"

    def __init__(self, cfg):
        super().__init__(cfg)
        self._router = None
        self._err = ""
        try:
            from twitter_radar.config import load_config
            from twitter_radar.router import Router
            self._router = Router(load_config("config.yaml"))
        except Exception as exc:  # noqa: BLE001
            self._err = str(exc)
            log.warning("twitter source unavailable: %s", exc)

    def available(self) -> bool:
        return self._router is not None

    def fetch(self, limit: int = 25) -> list:
        if self._router is None:
            return []
        items = []
        for handle in getattr(self.cfg, "x_accounts", []) or []:
            try:
                res = self._router.get_timeline(handle, limit=limit)
            except Exception as exc:  # noqa: BLE001
                log.debug("timeline %s failed: %s", handle, exc)
                continue
            if not getattr(res, "ok", False):
                continue
            for tw in res.tweets or []:
                sn = tw.author.screen_name or handle
                items.append(Item(
                    id=f"tw:{tw.tweet_id}", platform="twitter", author=sn,
                    title="", text=tw.text or "",
                    url=tw.url or f"https://x.com/{sn}/status/{tw.tweet_id}",
                    created_at=tw.created_at or "",
                    metrics={"likes": tw.like_count, "replies": tw.reply_count,
                             "retweets": tw.retweet_count},
                    source=self.name, query=handle,
                ))
            self._sleep()
        return items
