"""Telegram public web previews (t.me/s/<channel>)."""
from __future__ import annotations

import logging

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)


class TelegramSource(BaseSource):
    name = "telegram"
    platform = "telegram"

    def fetch(self, limit: int = 25) -> list:
        try:
            from bs4 import BeautifulSoup
        except Exception:
            return []
        items = []
        for ch in getattr(self.cfg, "telegram_channels", []) or []:
            url = f"https://t.me/s/{ch}"
            try:
                r = self._get(url)
                if r.status_code != 200:
                    log.warning("telegram %s -> HTTP %s", ch, r.status_code)
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                posts = soup.select(".tgme_widget_message_wrap")[-limit:]
                for p in posts:
                    body = p.select_one(".tgme_widget_message_text")
                    if not body:
                        continue
                    t = p.select_one("time[datetime]")
                    a = p.select_one(".tgme_widget_message_date a[href]")
                    link = a.get("href") if a else ""
                    msg_id = (link.rstrip("/").split("/")[-1] if link else
                              str(abs(hash(body.get_text()))))
                    items.append(Item(
                        id=f"tg:{ch}:{msg_id}", platform="telegram", author=ch,
                        title="", text=body.get_text(" ", strip=True),
                        url=link, created_at=(t.get("datetime") if t else "") or "",
                        metrics={}, source=self.name, query=ch,
                    ))
            except Exception as exc:  # noqa: BLE001
                log.warning("telegram %s failed: %s", ch, exc)
            self._sleep()
        return items
