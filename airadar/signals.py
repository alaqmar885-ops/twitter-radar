"""Weighted offer-signal engine.

The first version of the radar used a substring match on a keyword list, which
flagged anything containing the word "free" - the verification pass then threw
away roughly half of it. This module replaces that with a weighted phrase
scorer plus explicit negative evidence, so triage decides on *strength of
evidence* rather than the presence of one word.
"""
from __future__ import annotations

import re

# (phrase, weight) - strong evidence of a real free/offer proposition.
STRONG = {
    "free tier": 3, "free plan": 3, "free trial": 3, "free forever": 3,
    "always free": 3, "no credit card": 3, "no card required": 3,
    "no card needed": 3, "free credits": 3, "free of charge": 3,
    "100% off": 3, "lifetime deal": 3, "lifetime license": 3,
    "free for": 3, "start free": 2, "try free": 2, "free access": 2,
    "free api": 2, "promo code": 2, "coupon code": 2, "giveaway": 2,
    "beta access": 2, "no cost": 2, "$0": 2, "credits": 1,
    "open source": 1, "self-hosted": 1, "free": 1, "trial": 1,
    # Chinese-first providers (SiliconFlow / ModelScope / AgentRouter ...)
    "免费额度": 3, "免费试用": 3, "注册送": 3, "无需信用卡": 3, "免信用卡": 3,
    "赠送额度": 3, "免费": 1, "试用": 1, "赠送": 2, "优惠": 2,
    "discount": 2, "% off": 2, "deal": 2, "launch": 1,
}

# Phrases that cancel a free claim outright - if one of these is present the
# text is treated as NOT an offer regardless of positive signals.
HARD_VETO = [
    "no free tier", "no free plan", "no longer free", "free tier is gone",
    "removed the free", "not free", "paid only", "free tier was removed",
]

# Phrases that contradict or weaken a "free" claim.
NEGATIVE = {
    "not free": 3, "no free tier": 3, "paid only": 3, "requires payment": 3,
    "credit card required": 2, "price increase": 2, "no longer free": 3,
    "free tier is gone": 3, "removed the free": 3, "subscription required": 1,
}

DEFAULT_THRESHOLD = 3


def _hits(text: str, table: dict) -> dict:
    low = (text or "").lower()
    return {p: w for p, w in table.items() if p in low}


def score_text(text: str) -> dict:
    """Return {score, strong, medium, negative, veto, matched} for a blob of text."""
    low = (text or "").lower()
    veto = [v for v in HARD_VETO if v in low]
    if veto:
        return {"score": 0, "strong": [], "medium": [], "negative": [], "veto": veto,
                "negative_score": 0, "matched": []}
    strong = _hits(text, {p: w for p, w in STRONG.items() if w >= 2})
    medium = _hits(text, {p: w for p, w in STRONG.items() if w < 2})
    neg = _hits(text, NEGATIVE)
    strong_score = sum(strong.values())
    medium_score = sum(medium.values())
    neg_score = sum(neg.values())
    # A single weak word ("free") is not evidence; strong phrases dominate,
    # and accumulated medium signals can qualify on their own.
    score = strong_score + (medium_score if medium_score >= 2 else 0)
    return {
        "score": score,
        "strong": sorted(strong),
        "medium": sorted(medium),
        "negative": sorted(neg),
        "veto": [],
        "negative_score": neg_score,
        "matched": sorted(list(strong) + list(medium)),
    }


def is_offer_text(text: str, threshold: int = DEFAULT_THRESHOLD) -> bool:
    s = score_text(text)
    if s["veto"]:
        return False
    if s["negative_score"] >= 3 and not s["strong"]:
        return False
    return s["score"] >= threshold


PRODUCT_PREFIX = re.compile(r"^\s*(?:show|ask|tell)\s+hn\s*[:\-]\s*(.+)$", re.I)
