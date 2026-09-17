"""Meta Threads public profiles (HTML, best-effort)."""
from __future__ import annotations

import hashlib
import json
import logging
import re

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)


class ThreadsSource(BaseSource):
    name = "threads"
    platform = "threads"

    def fetch(self, limit: int = 25) -> list:
        items = []
        for user in getattr(self.cfg, "threads_usernames", []) or []:
            try:
                r = self._get(f"https://www.threads.net/@{user}")
                if r.status_code != 200:
                    log.warning("threads @%s -> HTTP %s", user, r.status_code)
                    continue
                items.extend(self._extract(r.text, user, limit))
            except Exception as exc:  # noqa: BLE001
                log.warning("threads @%s failed: %s", user, exc)
            self._sleep()
        return items

    def _extract(self, html: str, user: str, limit: int) -> list:
        """Best-effort: pull caption/text fields out of embedded JSON."""
        out = []
        seen = set()
        for m in re.finditer(r'"text":"((?:[^"\\]|\\.){20,600})"', html):
            raw = m.group(1)
            try:
                text = json.loads('"' + raw + '"')
            except Exception:
                text = raw
            if not text or text in seen:
                continue
            seen.add(text)
            h = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:16]
            out.append(Item(id=f"th:{h}", platform="threads", author=user,
                            title="", text=self._clean(text),
                            url=f"https://www.threads.net/@{user}",
                            created_at="", metrics={}, source=self.name, query=user))
            if len(out) >= limit:
                break
        return out
