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
    # Chinese-first providers: the same evidence in another language
    "\u514d\u8d39\u989d\u5ea6", "\u514d\u8d39\u8bd5\u7528", "\u6ce8\u518c\u9001",
    "\u514d\u8d39", "\u8d60\u9001", "\u4f18\u60e0",
]

# Strong evidence a page offers something free without a payment method.
NO_CC_SIGNALS = [
    "no credit card", "no credit-card", "no card required", "no card needed",
    "without a credit card", "without credit card", "no payment method",
    "no payment required", "no card", "no cc required", "free, no card",
    # Chinese-first: "\u65e0\u9700\u4fe1\u7528\u5361" = no credit card needed
    "\u65e0\u9700\u4fe1\u7528\u5361", "\u514d\u4fe1\u7528\u5361",
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

# Discussion/aggregator pages contain other people's words, so finding
# "free tier" on them proves nothing about a real offer. They cannot be
# treated as authoritative evidence.
DERIVATIVE_HOSTS = (
    "news.ycombinator.com", "reddit.com", "lobste.rs", "x.com", "twitter.com",
    "t.me", "mastodon.social", "producthunt.com", "dev.to", "medium.com",
)

# A phrase like "credit card required" is NOT evidence of a card requirement
# when it is negated ("no credit card required"). Substring matching alone got
# this wrong and marked free-tier pages as card-required.
_NEG_BEFORE = ("no ", "no-", "without ", "not ", "never ", "zero ", "0 ")


def _negated(text: str, idx: int, span: int = 18) -> bool:
    pre = (text or "")[max(0, idx - span):idx].lower()
    return any(n in pre for n in _NEG_BEFORE)


def find_card_signals(body: str) -> list:
    """Card-required phrases that are not negated by a preceding 'no/without'."""
    found = []
    text = (body or "").lower()
    for phrase in CARD_SIGNALS:
        start = 0
        while True:
            i = text.find(phrase, start)
            if i == -1:
                break
            if i > 0 and text[i - 1].isalnum():
                start = i + 1
                continue
            if not _negated(text, i):
                found.append(phrase)
                break
            start = i + 1
    return found


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

    def _mcp_contents(self, url: str) -> str:
        """Fetch rendered page text through the You.com MCP contents tool."""
        try:
            resp = self.enricher._call(  # noqa: SLF001 - intentional reuse
                "tools/call",
                {"name": "you-contents",
                 "arguments": {"urls": [url], "formats": ["markdown"]}})
            content = resp.get("result", {}).get("content", [])
            if not content:
                return ""
            import json as _json
            raw = content[0].get("text", "")
            try:
                data = _json.loads(raw)
                if isinstance(data, list) and data:
                    return str(data[0].get("markdown") or data[0].get("content") or "")[:200000]
                if isinstance(data, dict):
                    return str(data.get("markdown") or data.get("content") or "")[:200000]
            except Exception:
                return raw[:200000]
        except Exception:
            return ""
        return ""

    def verify(self, offer) -> dict:
        url = (offer.url or "").strip()
        from urllib.parse import urlparse as _up
        host = _up(url).netloc.lower()
        derivative = any(d in host for d in DERIVATIVE_HOSTS)
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
                base["card_signals"] = find_card_signals(body)
                base["india_signals"] = [s for s in INDIA_SIGNALS if s in body]
                base["upi_signals"] = [s for s in UPI_SIGNALS if s in body]
                m = re.search(r"<title[^>]*>(.*?)</title>", r.text or "", re.I | re.S)
                if m:
                    base["page_title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:140]
        except Exception as exc:  # noqa: BLE001
            base["status"] = "UNREACHABLE"
            base["notes"] = [f"fetch failed: {exc}"]
            return base

        # JS-rendered pages serve a shell to a plain GET, so a static scan finds
        # nothing (groq.com reads WEAK). Fall back to the You.com MCP "you-contents"
        # extractor for those pages, which returns rendered text.
        if not base["signals"] and self.enricher is not None and \
                getattr(self.enricher, "available", lambda: False)():
            text = self._mcp_contents(url)
            if text:
                body = text.lower()
                base["signals"] = [s for s in FREE_SIGNALS if s in body]
                base["no_cc_signals"] = [s for s in NO_CC_SIGNALS if s in body]
                base["card_signals"] = find_card_signals(body)
                base["india_signals"] = [s for s in INDIA_SIGNALS if s in body]
                base["upi_signals"] = [s for s in UPI_SIGNALS if s in body]
                if base["signals"]:
                    base["notes"].append("signals recovered via MCP page extraction")

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
                  "free access",
                  "\u514d\u8d39\u989d\u5ea6", "\u514d\u8d39\u8bd5\u7528", "\u6ce8\u518c\u9001"}
        MEDIUM = {"pricing", "trial", "discount", "credits"}
        strong = [s for s in base["signals"] if s in STRONG]
        medium = [s for s in base["signals"] if s in MEDIUM]

        if not base["signals"]:
            status = "NOT_AN_OFFER"
            base["notes"].append("target page contains no free/offer signal")
        elif strong and base["no_cc_signals"]:
            # A pricing page that says "free tier, no credit card" and "Pro tier,
            # card required" is a NO-CARD offer for its free tier. Explicit no-card
            # wording wins over generic card wording.
            status = "VERIFIED_NO_CC"
            if base["card_signals"]:
                base["notes"].append("page also mentions card for a paid tier")
        elif strong and base["card_signals"]:
            status = "CARD_REQUIRED"
        elif strong:
            status = "VERIFIED"
        elif len(medium) >= 2:
            status = "PARTIAL"
        else:
            status = "WEAK"

        if derivative and status in ("VERIFIED", "VERIFIED_NO_CC", "PARTIAL"):
            status = "DERIVATIVE"
            base["notes"].append("discussion/aggregator page - not authoritative evidence")

        offer.link_ok = True
        offer.web_verified = status in ("VERIFIED", "VERIFIED_NO_CC")
        base["status"] = status
        return base
