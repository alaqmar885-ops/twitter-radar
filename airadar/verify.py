"""Per-finding verification: link live? really free? does it need a credit card?"""
from __future__ import annotations

import logging
import re

from .sources.base import BROWSER_UA

log = logging.getLogger(__name__)

# Signals that a destination page advertises a free/offer proposition.
FREE_SIGNALS = [
    "free tier", "free plan", "free trial", "start free", "try free",
    "free credits", "free forever", "always free", "no credit card",
    "credits", "pricing", "free", "trial", "discount", "off",
]

# Strong evidence a page offers something free without a payment method.
NO_CC_SIGNALS = [
    "no credit card", "no credit-card", "no card required", "no card needed",
    "without a credit card", "without credit card", "no payment method",
    "no payment required", "no card", "no cc required", "free, no card",
]

# Strong evidence the free tier actually REQUIRES a card / payment method.
CARD_SIGNALS = [
    "credit card required", "card required", "requires a credit card",
    "add a payment method", "payment method required", "billing enabled",
    "add your card", "enter your card", "requires payment",
]

# Evidence that a page is relevant/usable for an Indian customer.
INDIA_SIGNALS = [
    "india", "indian", "inr", "\u20b9", "rupee", "rupees", "jio", "airtel",
    "vi ", "bsnl", "upi", "razorpay", "paytm", "phonepe", "google pay", "gpay",
    "netbanking", "net banking", "bharat", "gst",
]

# Subset: payment rails an Indian customer can actually pay with.
UPI_SIGNALS = [
    "upi", "razorpay", "paytm", "phonepe", "google pay", "gpay",
    "netbanking", "net banking", "autopay", "mandate",
]

_TAG = re.compile(r"<[^>]+>")


def page_text(html: str, limit: int = 200_000) -> str:
    txt = _TAG.sub(" ", html or "")
    txt = re.sub(r"\s+", " ", txt)
    return txt[:limit].lower()


class FindingVerifier:
    """Checks one offer: link liveness + on-page free evidence + card policy + web corroboration."""

    def __init__(self, cfg, enricher=None):
        self.cfg = cfg
        self.enricher = enricher

    def verify(self, offer) -> dict:
        url = (offer.url or "").strip()
        base = {"page_status": 0, "signals": [], "no_cc_signals": [],
                "card_signals": [], "india_signals": [], "upi_signals": [],
                "web_hits": 0, "page_title": "", "notes": []}
        if not url:
            base["status"] = "NO_URL"
            base["notes"] = ["no url on finding"]
            return base

        try:
            import httpx
            with httpx.Client(follow_redirects=True, timeout=20,
                              headers={"User-Agent": BROWSER_UA}) as c:
                r = c.get(url)
                base["page_status"] = r.status_code
                if r.status_code >= 400:
                    base["status"] = "UNREACHABLE"
                    base["notes"] = [f"HTTP {r.status_code}"]
                    return base
                body = page_text(r.text)
                base["signals"] = [s for s in FREE_SIGNALS if s in body]
                base["no_cc_signals"] = [s for s in NO_CC_SIGNALS if s in body]
                base["card_signals"] = [s for s in CARD_SIGNALS if s in body]
                base["india_signals"] = [s for s in INDIA_SIGNALS if s in body]
                base["upi_signals"] = [s for s in UPI_SIGNALS if s in body]
                m = re.search(r"<title[^>]*>(.*?)</title>", r.text or "", re.I | re.S)
                if m:
                    base["page_title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:140]
        except Exception as exc:  # noqa: BLE001
            base["status"] = "UNREACHABLE"
            base["notes"] = [f"fetch failed: {exc}"]
            return base

        web_hits = 0
        if self.enricher is not None and getattr(self.enricher, "available", lambda: False)():
            q = (offer.product or offer.title or "")[:110]
            try:
                res = self.enricher.search(q, max_results=4) if q else []
                web_hits = len(res or [])
                offer.web_sources = (res or [])[:4]
            except Exception as exc:  # noqa: BLE001
                base["notes"].append(f"web search failed: {exc}")
        base["web_hits"] = web_hits

        STRONG = {"free tier", "free plan", "free trial", "start free", "try free",
                  "free credits", "free forever", "always free", "no credit card",
                  "free access"}
        MEDIUM = {"pricing", "trial", "discount", "credits"}
        strong = [s for s in base["signals"] if s in STRONG]
        medium = [s for s in base["signals"] if s in MEDIUM]

        if not base["signals"]:
            status = "NOT_AN_OFFER"
            base["notes"].append("target page contains no free/offer signal")
        elif strong and base["card_signals"]:
            status = "CARD_REQUIRED"
        elif strong and base["no_cc_signals"]:
            status = "VERIFIED_NO_CC"
        elif strong:
            status = "VERIFIED"
        elif len(medium) >= 2:
            status = "PARTIAL"
        else:
            status = "WEAK"

        offer.link_ok = True
        offer.web_verified = status in ("VERIFIED", "VERIFIED_NO_CC")
        base["status"] = status
        return base
