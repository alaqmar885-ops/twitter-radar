"""Refine raw offers into clean, presentable findings."""
from __future__ import annotations

import re

PREFIX = re.compile(r"^\s*(?:show|ask|tell)\s+hn\s*[:\-]\s*", re.I)
WS = re.compile(r"\s+")


def clean_title(text: str, limit: int = 130) -> str:
    t = PREFIX.sub("", (text or "").strip())
    t = WS.sub(" ", t)
    t = t.strip(" -–—:|")
    return t[:limit].rstrip()


def refine(offer, classifier) -> object:
    """Clean up an Offer in place using the classifier + its own items."""
    best = None
    for it in (getattr(offer, "items", []) or []):
        if not best or len(it.title or "") > len(best.title or ""):
            best = it
    if best is not None:
        info = classifier.classify(best) or {}
        offer.title = clean_title(best.title or info.get("summary") or best.text)
        if not offer.summary:
            offer.summary = clean_title(best.text[:220], 220)
        for f in ("offer_type", "value", "promo_code", "product"):
            if info.get(f) and (f == "offer_type" or not getattr(offer, f, "")):
                setattr(offer, f, info[f])
        if not offer.url:
            offer.url = best.url or ""
    else:
        offer.title = clean_title(offer.title)
    if not offer.title:
        offer.title = clean_title(offer.product or offer.url)
    return offer
