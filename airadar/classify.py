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
        "free", "this", "that", "from", "your", "you", "our", "our", "all"}


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
        blob = f"{it.title} {it.text}"
        m = re.search(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)\s+(?:is|now|free|offers?|gives?|has)\b", blob)
        if m:
            return m.group(1).strip()
        for cand in re.findall(r"\b[A-Z][A-Za-z0-9]{2,}\b", it.title + " " + it.text[:160]):
            if cand.lower() not in STOP:
                return cand
        words = [w for w in (it.title or it.text).split() if w.lower() not in STOP]
        return " ".join(words[:3])

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
