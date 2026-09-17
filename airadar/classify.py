"""Offer detection + extraction (keywords, type, value, promo code, product)."""
from __future__ import annotations

import re
import logging

log = logging.getLogger(__name__)

PROMO_PATTERNS = [
    re.compile(r"(?:promo\s*code|coupon\s*code|discount\s*code)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9_-]{2,23})", re.I),
    re.compile(r"\bcode\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9_-]{2,23})", re.I),
    re.compile(r"\b(?:use|with|apply)\s+(?:code\s+)?([A-Z][A-Z0-9_-]{4,23})\b"),
    re.compile(r"\b([A-Z]{3,}[0-9]{1,}[A-Z0-9]*)\b"),
]

TYPE_RULES = [
    ("lifetime_deal", ["lifetime deal", "lifetime license", "ltd ", "pay once", "one-time payment"]),
    ("free_credits", ["free credits", "free credit", "credits free", "$0", "free api", "api credits"]),
    ("free_trial", ["free trial", "trial free", "try free", "free for 14", "free for 30"]),
    ("free_tier", ["free tier", "free plan", "free forever", "always free", "no cost"]),
    ("discount", ["% off", "percent off", "discount", "promo code", "coupon", "deal"]),
    ("giveaway", ["giveaway", "give away", "win a", "free license"]),
    ("open_source", ["open source", "open-source", "mit license", "self-hosted", "free software"]),
]

VALUE_PATTERNS = [
    re.compile(r"(\d+\s*%\s*off)", re.I),
    re.compile(r"(\$\s?\d+(?:\.\d+)?\s*(?:in\s+)?(?:credits?|free|off)?)", re.I),
    re.compile(r"(\d+\s*(?:days?|weeks?|months?|years?)\s*(?:of\s*)?free)", re.I),
    re.compile(r"(free\s+forever)", re.I),
    re.compile(r"(\d+\s*(?:days?|weeks?|months?)\s*(?:free\s*)?trial)", re.I),
]

STOP = {"the", "a", "an", "is", "are", "for", "with", "and", "get", "now", "new",
        "free", "this", "that", "from", "your", "you", "our", "all", "how", "why",
        "what", "when", "we", "i", "my", "it", "to", "of", "in", "on", "at"}

# Words that must never become a product/cluster key - they are section prefixes
# ("Show HN:", "Ask HN:") or generic filler, and they cause unrelated posts to
# be merged into one Offer.
GENERIC = {"show", "ask", "tell", "hn", "showhn", "show hn", "ask hn", "introducing",
           "launch", "launching", "announcing", "free", "ai", "new", "update",
           "weekly", "daily", "news", "tool", "app", "model", "release"}


class OfferClassifier:
    def __init__(self, cfg):
        self.cfg = cfg
        self.keywords = [k.lower() for k in (getattr(cfg, "offer_keywords", None) or [])]

    def is_offer(self, it) -> bool:
        blob = (it.blob or "").lower()
        if not blob.strip():
            return False
        return any(k in blob for k in self.keywords)

    def extract_promo_code(self, text: str) -> str:
        t = text or ""
        for pat in PROMO_PATTERNS:
            m = pat.search(t)
            if m:
                code = m.group(1).strip().strip(".,;:")
                if len(code) >= 3 and code.lower() not in STOP:
                    return code.upper()
        return ""

    def _offer_type(self, blob: str) -> str:
        for name, needles in TYPE_RULES:
            for n in needles:
                if n in blob:
                    return name
        return "other"

    def _value(self, text: str) -> str:
        for pat in VALUE_PATTERNS:
            m = pat.search(text or "")
            if m:
                return m.group(1).strip()
        return ""

    def _product(self, it) -> str:
        """Best-effort product/entity name.

        Returns "" when there is no trustworthy signal, so the caller falls back
        to the URL/host as the cluster key (never a generic word like "Show").
        """
        title = (it.title or "").strip()
        # 1) "Show HN: Foo ..." / "Ask HN: Foo" -> Foo
        m = re.match(r"^(?:show|ask|tell)\s+hn\s*[:\-]\s*(.+)$", title, re.I)
        if m:
            rest = m.group(1).strip()
            token = re.split(r"[\s\u2013\u2014\-:|,(]+", rest)[0].strip()
            if token and token.lower() not in GENERIC and token.lower() not in STOP:
                return token
        # 2) "<Name> is/now/offers/gives <something>" (needs a real proper noun)
        blob = f"{title} {it.text[:200]}"
        m = re.search(r"\b([A-Z][A-Za-z0-9]{2,}(?:\s+[A-Z][A-Za-z0-9]{2,})?)\s+"
                      r"(?:is|now|free|offers?|gives?|has|launches?)\b", blob)
        if m:
            cand = m.group(1).strip()
            if cand.lower() not in GENERIC and cand.lower() not in STOP:
                return cand
        # 3) tool names with a known suffix (e.g. "-ai", ".ai", "GPT", "LLM")
        m = re.search(r"\b([A-Za-z0-9][A-Za-z0-9._-]{2,20}(?:ai|gpt|llm|bot|lab|dev)\b)", title, re.I)
        if m and m.group(1).lower() not in GENERIC:
            return m.group(1)
        return ""

    def classify(self, it) -> dict | None:
        if not self.is_offer(it):
            return None
        blob = (it.blob or "").lower()
        text = f"{it.title} {it.text}"
        otype = self._offer_type(blob)
        code = self.extract_promo_code(text)
        value = self._value(text)
        product = self._product(it)
        if otype == "other":
            if code or value:
                otype = "discount"
            elif "free" in blob:
                otype = "free_tier"
        summary = (it.title or it.text or "").strip()[:200]
        return {"offer_type": otype, "value": value, "promo_code": code,
                "product": product, "summary": summary}
