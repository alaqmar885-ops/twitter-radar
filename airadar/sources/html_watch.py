"""Generic HTML watch pages: surface offer-like links/headings from deal sites."""
from __future__ import annotations

import hashlib
import logging

from ..models import Item
from .base import BaseSource

log = logging.getLogger(__name__)

DEFAULT_HINTS = ["free", "deal", "credit", "lifetime", "discount", "off", "launch",
                 "promo", "coupon", "giveaway", "trial", "tier"]


class HtmlWatchSource(BaseSource):
    name = "html"
    platform = "html"

    def fetch(self, limit: int = 25) -> list:
        try:
            from bs4 import BeautifulSoup
        except Exception:
            return []
        hints = [k.lower() for k in (getattr(self.cfg, "offer_keywords", None) or DEFAULT_HINTS)]
        items = []
        for page in getattr(self.cfg, "html_watch", []) or []:
            try:
                r = self._get(page)
                if r.status_code != 200:
                    log.warning("html %s -> HTTP %s", page, r.status_code)
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                seen = set()
                n = 0

                # (a) the watched page may itself BE the offer (e.g. a provider's
                # pricing/docs page). Emit it directly so a provider added to the
                # watchlist is actually captured, not just its outbound links.
                try:
                    from ..signals import is_offer_text
                    title = (soup.title.get_text(strip=True) if soup.title else "")
                    body = soup.get_text(" ", strip=True)[:4000]
                    if is_offer_text(f"{title} {body}"):
                        h0 = hashlib.sha1(page.encode("utf-8", "ignore")).hexdigest()[:16]
                        seen.add(h0)
                        items.append(Item(id=f"html:{h0}", platform="html",
                                          author=(page.split("/")[2] if "//" in page else ""),
                                          title=title[:180] or page, text=body[:500],
                                          url=page, created_at="", metrics={},
                                          source=self.name, query=page))
                        n += 1
                except Exception as exc:  # noqa: BLE001
                    log.debug("self-offer check failed for %s: %s", page, exc)
                for a in soup.find_all("a", href=True):
                    text = (a.get_text(" ", strip=True) or "")[:180]
                    href = a["href"]
                    if not text or len(text) < 6:
                        continue
                    blob = f"{text} {href}".lower()
                    if not any(h in blob for h in hints):
                        continue
                    if href.startswith("/"):
                        base = page.split("/")[0] + "//" + page.split("/")[2]
                        href = base + href
                    if not href.startswith("http"):
                        continue
                    h = hashlib.sha1(f"{href}|{text}".encode("utf-8", "ignore")).hexdigest()[:16]
                    if h in seen:
                        continue
                    seen.add(h)
                    items.append(Item(id=f"html:{h}", platform="html", author="",
                                      title=text, text=text, url=href, created_at="",
                                      metrics={}, source=self.name, query=page))
                    n += 1
                    if n >= limit:
                        break
            except Exception as exc:  # noqa: BLE001
                log.warning("html %s failed: %s", page, exc)
            self._sleep()
        return items
