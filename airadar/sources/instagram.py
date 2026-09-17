"""Instagram - optional, lazy. Only available if `instaloader` is installed."""
from __future__ import annotations

import logging

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)


class InstagramSource(BaseSource):
    name = "instagram"
    platform = "instagram"

    def available(self) -> bool:
        try:
            import instaloader  # noqa: F401
            return True
        except Exception:
            return False

    def fetch(self, limit: int = 25) -> list:
        if not self.available():
            return []
        try:
            import instaloader
        except Exception:
            return []
        items = []
        L = instaloader.Instaloader(download_pictures=False, download_videos=False,
                                    download_comments=False, save_metadata=False,
                                    quiet=True)
        for user in getattr(self.cfg, "instagram_usernames", []) or []:
            try:
                prof = instaloader.Profile.from_username(L.context, user)
                for i, post in enumerate(prof.get_posts()):
                    if i >= limit:
                        break
                    items.append(Item(
                        id=f"ig:{post.shortcode}", platform="instagram",
                        author=user, title="", text=post.caption or "",
                        url=f"https://www.instagram.com/p/{post.shortcode}/",
                        created_at=str(post.date_utc), metrics={"likes": post.likes},
                        source=self.name, query=user,
                    ))
            except Exception as exc:  # noqa: BLE001
                log.warning("instagram %s failed: %s", user, exc)
        return items
