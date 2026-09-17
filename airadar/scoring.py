"""Offer scoring - 5 weighted signals -> 0..1 score + label."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

log = logging.getLogger(__name__)

W_FREE = 0.30
W_CORROB = 0.25
W_CRED = 0.20
W_RECENCY = 0.15
W_LINK = 0.10

TYPE_STRENGTH = {
    "free_tier": 1.0, "free_credits": 1.0, "free_trial": 0.95,
    "open_source": 0.9, "lifetime_deal": 0.85, "giveaway": 0.8,
    "discount": 0.7, "other": 0.35,
}

PLATFORM_CRED = {
    "hackernews": 0.75, "twitter": 0.65, "bluesky": 0.55, "mastodon": 0.5,
    "youtube": 0.6, "telegram": 0.5, "reddit": 0.6, "rss": 0.65,
    "html": 0.7, "threads": 0.5, "instagram": 0.5,
}


class OfferScorer:
    def __init__(self, cfg):
        self.cfg = cfg

    def label(self, score: float, verified: bool) -> str:
        if verified and score >= 0.80:
            return "VERIFIED"
        if score >= 0.60:
            return "HIGH"
        if score >= 0.40:
            return "MEDIUM"
        return "LOW"

    def score(self, o) -> "object":
        free = self._free_strength(o)
        corr = self._corroboration(o)
        cred = self._credibility(o)
        rec = self._recency(o)
        link = 1.0 if getattr(o, "link_ok", False) else 0.0
        total = (W_FREE * free + W_CORROB * corr + W_CRED * cred +
                 W_RECENCY * rec + W_LINK * link)
        o.score = round(min(max(total, 0.0), 1.0), 3)
        o.label = self.label(o.score, bool(getattr(o, "web_verified", False)))
        o.last_updated = time.time()
        return o

    @staticmethod
    def _free_strength(o) -> float:
        base = TYPE_STRENGTH.get(getattr(o, "offer_type", "other"), 0.35)
        blob = f"{getattr(o, 'title', '')} {getattr(o, 'value', '')}".lower()
        if "free" in blob or "$0" in blob or "100% off" in blob:
            base = min(1.0, base + 0.1)
        return base

    @staticmethod
    def _corroboration(o) -> float:
        items = getattr(o, "items", []) or []
        n = len(items)
        plats = {getattr(i, "platform", "") for i in items}
        if n <= 0:
            return 0.1
        if n == 1:
            base = 0.3
        elif n == 2:
            base = 0.6
        else:
            base = 1.0
        if len(plats) >= 2:
            base = min(1.0, base + 0.2)
        return base

    @staticmethod
    def _credibility(o) -> float:
        plats = getattr(o, "platforms", []) or []
        if not plats:
            return 0.4
        vals = [PLATFORM_CRED.get(p, 0.5) for p in plats]
        base = max(vals)
        if getattr(o, "promo_code", ""):
            base = min(1.0, base + 0.1)
        return base

    @staticmethod
    def _recency(o) -> float:
        stamps = [getattr(i, "created_at", "") for i in (getattr(o, "items", []) or [])]
        stamps = [s for s in stamps if s]
        if not stamps:
            return 0.4
        best = 0.0
        now = time.time()
        for s in stamps:
            try:
                dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age = now - dt.timestamp()
            except Exception:
                try:
                    age = now - float(s)
                except Exception:
                    continue
            if age < 86400:
                v = 1.0
            elif age < 3 * 86400:
                v = 0.7
            elif age < 7 * 86400:
                v = 0.5
            elif age < 30 * 86400:
                v = 0.3
            else:
                v = 0.15
            best = max(best, v)
        return best or 0.4
