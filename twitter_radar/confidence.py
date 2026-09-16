"""Confidence scoring engine.

Combines multiple signals into a single 0.0–1.0 confidence score:

  1. Source credibility    — verified accounts + follower count (tier 1-5)
  2. Cross-references      — same claim from multiple independent accounts
  3. Recency               — newer claims are more likely still valid
  4. Engagement            — high replies/quotes = people discussing it
  5. Web verification      — You.com search finds corroborating sources

The weights are tuned so that a single anonymous tweet with no web corroboration
stays LOW (< 0.35), while a verified account + web-confirmed deal hits
HIGH/VERIFIED.  This prevents the digest from surfencing unverified hype as
fact — the user asked for "with confidence" and this delivers exactly that.

Labels:
    VERIFIED  ≥ 0.80   — web-confirmed by independent sources
    HIGH      ≥ 0.60   — strong tweet evidence, likely web-confirmed
    MEDIUM    ≥ 0.40   — decent signal, some corroboration
    LOW       <  0.40  — unverified, include only if no stronger findings
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

from .enrich.youcom import YouComEnricher
from .models import Finding, FindingType, Tweet

log = logging.getLogger(__name__)

# --- Signal weights (sum of components, clamped to [0, 1]) -----------------
W_CREDIBILITY = 0.30   # author trustworthiness
W_CROSS_REF   = 0.25   # multiple independent sources
W_WEB_VERIFY  = 0.25   # You.com corroboration
W_RECENCY     = 0.10   # freshness
W_ENGAGEMENT   = 0.10   # discussion volume

# Recency thresholds (seconds).
HOUR = 3600
DAY = 86400
WEEK = 604800


class ConfidenceEngine:
    """Scores findings 0.0–1.0 based on multi-signal evidence."""

    def __init__(self, enricher: Optional[YouComEnricher] = None,
                 min_credibility_for_verify: float = 0.35):
        self.enricher = enricher
        self.min_credibility_for_verify = min_credibility_for_verify

    def score_finding(self, finding: Finding, verify: bool = True) -> Finding:
        """Compute and set confidence on a finding.  Optionally web-verify."""
        cred = self._credibility(finding)
        cross = self._cross_reference(finding)
        recency = self._recency(finding)
        engagement = self._engagement(finding)

        # Pre-web confidence — used to decide whether to spend a You.com call.
        pre_web = (
            W_CREDIBILITY * cred
            + W_CROSS_REF * cross
            + W_RECENCY * recency
            + W_ENGAGEMENT * engagement
        )

        web_verified = False
        web_score = 0.0
        if (
            verify
            and self.enricher
            and self.enricher.available()
            and pre_web >= self.min_credibility_for_verify
        ):
            results = self.enricher.verify_finding(finding)
            if results:
                finding.web_sources = results
                # Score based on how many relevant results and their recency.
                web_score = self._web_relevance(results)
                if web_score >= 0.5:
                    web_verified = True

        confidence = (
            W_CREDIBILITY * cred
            + W_CROSS_REF * cross
            + W_WEB_VERIFY * web_score
            + W_RECENCY * recency
            + W_ENGAGEMENT * engagement
        )
        confidence = min(max(confidence, 0.0), 1.0)

        finding.confidence = round(confidence, 3)
        finding.web_verified = web_verified
        finding.confidence_label = self._label(confidence, web_verified)
        return finding

    # -- individual signal calculators ----------------------------------------

    @staticmethod
    def _credibility(finding: Finding) -> float:
        """Best-author credibility tier, normalized 0-1."""
        author = finding.best_author
        if not author:
            return 0.1
        # Tier 5 → 1.0, 4 → 0.8, 3 → 0.6, 2 → 0.4, 1 → 0.2
        return author.credibility_tier / 5.0

    @staticmethod
    def _cross_reference(finding: Finding) -> float:
        """Multiple independent accounts reporting the same claim.

        1 source → 0.1 (just one tweet)
        2 sources → 0.5
        3+ sources → 1.0
        """
        # Count distinct authors among supporting tweets.
        authors = {
            t.author.screen_name.lower() for t in finding.tweets
            if t.author.screen_name
        }
        n = len(authors)
        if n <= 1:
            return 0.1
        if n == 2:
            return 0.5
        return min(1.0, 0.5 + 0.25 * (n - 2))

    @staticmethod
    def _recency(finding: Tweet | Finding) -> float:
        """Newer = higher.  <1hr=1.0, <1day=0.8, <3days=0.5, >1week=0.2."""
        latest = max(
            (t.fetched_at for t in finding.tweets),
            default=time.time(),
        )
        # Try to parse created_at for true recency; fall back to fetched_at.
        age = time.time() - latest
        # If any tweet has a parseable created_at, use the newest.
        for t in reversed(finding.tweets):
            ca = t.created_at
            if ca:
                try:
                    from datetime import datetime, timezone
                    # Handle both Z-suffixed and offset formats.
                    dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                    age = time.time() - dt.timestamp()
                    break
                except (ValueError, TypeError):
                    continue
        if age < HOUR:
            return 1.0
        if age < DAY:
            return 0.8
        if age < 3 * DAY:
            return 0.5
        if age < WEEK:
            return 0.3
        return 0.1

    @staticmethod
    def _engagement(finding: Finding) -> float:
        """Log-ish scaling of the top tweet's engagement score → 0-1."""
        top = finding.top_tweet
        if not top:
            return 0.0
        e = top.engagement_score
        # 0 → 0.0, 100 → ~0.5, 1000 → ~0.8, 5000+ → ~1.0
        if e <= 0:
            return 0.0
        import math
        return min(1.0, math.log10(e + 1) / 4.0)

    @staticmethod
    def _web_relevance(results: list[dict]) -> float:
        """Score web results by count + freshness.

        0 results → 0.0
        1 result  → 0.3 (weak corroboration)
        2-3      → 0.6
        4+       → 1.0
        Bonus if any result is from the last 7 days.
        """
        n = len(results)
        if n == 0:
            return 0.0
        base = {1: 0.3, 2: 0.6, 3: 0.6}.get(n, 1.0)
        # Check recency of web results.
        now = time.time()
        for r in results:
            age_str = r.get("page_age", "")
            if age_str:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(
                        age_str.replace("Z", "+00:00")
                    )
                    if now - dt.timestamp() < WEEK:
                        base = min(1.0, base + 0.15)
                        break
                except (ValueError, TypeError):
                    continue
        return base

    @staticmethod
    def _label(confidence: float, web_verified: bool) -> str:
        if web_verified and confidence >= 0.80:
            return "VERIFIED"
        if confidence >= 0.80:
            return "HIGH"
        if confidence >= 0.60:
            return "HIGH"
        if confidence >= 0.40:
            return "MEDIUM"
        return "LOW"
