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


JUNK = ("skip to content", "menu", "sign in", "log in", "cookie", "javascript")


def _looks_like_scrape(text: str) -> bool:
    t = (text or "").lower()
    if len(text or "") > 140:
        return True
    if any(j in t for j in JUNK):
        return True
    # nav/listing noise: many single-letter or very short tokens
    words = (text or "").split()
    if words and sum(1 for w in words if len(w) <= 2) / len(words) > 0.4:
        return True
    return False


def refine(offer, classifier, page_title: str = "") -> object:
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
    # If the headline looks like scraped navigation/listing text, prefer the
    # destination page's own <title> - that is usually the real product name.
    if page_title and _looks_like_scrape(offer.title):
        offer.title = clean_title(page_title)
    if not offer.title:
        offer.title = clean_title(offer.product or offer.url)
    return offer
