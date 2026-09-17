"""Per-finding verification: is the link live, and does it really offer something free?"""
from __future__ import annotations

import logging
import re

from .sources.base import BROWSER_UA

log = logging.getLogger(__name__)

# Signals that a destination page actually advertises a free/offer proposition.
FREE_SIGNALS = [
    "free tier", "free plan", "free trial", "start free", "try free",
    "free credits", "free forever", "always free", "no credit card",
    "credits", "pricing", "free", "trial", "discount", "off",
]

_TAG = re.compile(r"<[^>]+>")


def page_text(html: str, limit: int = 200_000) -> str:
    txt = _TAG.sub(" ", html or "")
    txt = re.sub(r"\s+", " ", txt)
    return txt[:limit].lower()


class FindingVerifier:
    """Checks one offer: link liveness + on-page free/offer evidence + web corroboration."""

    def __init__(self, cfg, enricher=None):
        self.cfg = cfg
        self.enricher = enricher

    def verify(self, offer) -> dict:
        url = (offer.url or "").strip()
        page_status = 0
        signals: list = []
        page_title = ""
        notes: list = []

        if not url:
            return {"status": "NO_URL", "page_status": 0, "signals": [],
                    "web_hits": 0, "notes": ["no url on finding"]}

        try:
            import httpx
            with httpx.Client(follow_redirects=True, timeout=20,
                              headers={"User-Agent": BROWSER_UA}) as c:
                r = c.get(url)
                page_status = r.status_code
                if r.status_code < 400:
                    body = page_text(r.text)
                    signals = [s for s in FREE_SIGNALS if s in body]
                    m = re.search(r"<title[^>]*>(.*?)</title>", r.text or "",
                                  re.I | re.S)
                    if m:
                        page_title = re.sub(r"\s+", " ", m.group(1)).strip()[:140]
        except Exception as exc:  # noqa: BLE001
            notes.append(f"fetch failed: {exc}")
            return {"status": "UNREACHABLE", "page_status": 0, "signals": [],
                    "web_hits": 0, "notes": notes}

        if page_status >= 400:
            return {"status": "UNREACHABLE", "page_status": page_status,
                    "signals": [], "web_hits": 0, "notes": [f"HTTP {page_status}"]}

        web_hits = 0
        if self.enricher is not None and getattr(self.enricher, "available", lambda: False)():
            q = (offer.product or offer.title or "")[:110]
            try:
                res = self.enricher.search(q, max_results=4) if q else []
                web_hits = len(res or [])
                offer.web_sources = (res or [])[:4]
            except Exception as exc:  # noqa: BLE001
                notes.append(f"web search failed: {exc}")

        strong = [s for s in signals if s not in ("off", "free")]
        if not signals:
            status = "NOT_AN_OFFER"
            notes.append("target page contains no free/offer signal")
        elif web_hits >= 2 and signals:
            status = "VERIFIED"
        elif len(strong) >= 2 or web_hits == 1:
            status = "PARTIAL"
        else:
            status = "WEAK"

        offer.link_ok = True
        offer.web_verified = status == "VERIFIED"
        return {"status": status, "page_status": page_status,
                "signals": signals[:8], "web_hits": web_hits,
                "page_title": page_title, "notes": notes}
