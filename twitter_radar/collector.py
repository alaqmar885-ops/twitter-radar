"""Collection pipeline — orchestrates a single radar sweep.

A cycle:
  1. For each configured topic: keyword search (twifork, if available).
  2. For each watch account: pull timeline (FxTwitter, no-auth).
  3. Enrich high-value tweets with Syndication thread context.
  4. Classify tweets into Findings by topic + entity clustering.
  5. Score findings via the confidence engine (+ You.com web verify).
  6. Persist tweets + findings to SQLite.

This module is the glue between router, confidence, and store.  The scheduler
calls `run_cycle()` on a routine; `run_cycle_once()` is the one-shot entry
point for cron.
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from typing import Optional

from .config import Config
from .confidence import ConfidenceEngine
from .enrich.youcom import YouComEnricher
from .models import Finding, FindingType, Tweet
from .router import Router
from .store import Store

log = logging.getLogger(__name__)

# Patterns for extracting "claim entities" — the thing a deal/offer is about.
# E.g. "Cursor is offering 2 weeks free Pro" → entities: {cursor, pro, free, 2 weeks}
ENTITY_RE = re.compile(
    r"(?:[A-Z][a-zA-Z0-9]+(?:\s[A-Z][a-zA-Z0-9]+)?)"  # capitalized words
    r"|(?:free|discount|off|deal|offer|trial|lifetime|unlimited|save)",  # deal terms
    re.IGNORECASE,
)
# Deal-amount patterns: "2 weeks", "50% off", "$10 off", "3 months"
DEAL_AMOUNT_RE = re.compile(
    r"(\d+\s*(?:%|USD|EUR|\$|€|£)\s*(?:off|discount))"  # "50% off", "$10 off"
    r"|(\d+\s*(?:days?|weeks?|months?|hours?)\s*(?:free|trial|access))",  # "2 weeks free"
    re.IGNORECASE,
)


class Collector:
    """Runs one collection cycle end-to-end."""

    def __init__(
        self,
        cfg: Config,
        router: Router,
        store: Store,
        confidence: ConfidenceEngine,
    ):
        self.cfg = cfg
        self.router = router
        self.store = store
        self.confidence = confidence

    def run_cycle(self) -> dict:
        """Execute a full sweep.  Returns a stats dict."""
        t0 = time.time()
        all_tweets: list[Tweet] = []
        seen_ids: set[str] = set()

        # ---- Phase 1: keyword search per topic (twifork, if available) ----
        for topic, spec in self.cfg.topics.items():
            ftype = FindingType(spec.get("finding_type", "general"))
            for kw in spec.get("keywords", []):
                if len(all_tweets) >= self.cfg.schedule.max_tweets_per_topic * len(self.cfg.topics):
                    break
                result = self.router.search(kw, limit=self.cfg.schedule.max_tweets_per_topic)
                if result.ok:
                    for tw in result.tweets:
                        if tw.tweet_id not in seen_ids:
                            seen_ids.add(tw.tweet_id)
                            tw._topic = topic  # type: ignore[attr-defined]
                            tw._finding_type = ftype  # type: ignore[attr-defined]
                            all_tweets.append(tw)
                            self.store.save_tweet(tw, topic=topic)
                elif result.rate_limited:
                    log.warning("Rate-limited on keyword '%s' — backing off", kw)
                    break  # move to next topic; don't hammer the rate limit

        # ---- Phase 2: watch-account timelines (FxTwitter, no-auth) --------
        for handle in self.cfg.watch_accounts:
            result = self.router.get_timeline(
                handle, limit=self.cfg.schedule.max_tweets_per_account
            )
            if result.ok:
                for tw in result.tweets:
                    if tw.tweet_id in seen_ids:
                        continue
                    seen_ids.add(tw.tweet_id)
                    # Match to a topic by keyword presence, else "news".
                    topic, ftype = self._classify(tw.text)
                    tw._topic = topic  # type: ignore[attr-defined]
                    tw._finding_type = ftype  # type: ignore[attr-defined]
                    all_tweets.append(tw)
                    self.store.save_tweet(tw, topic=topic)
            elif result.rate_limited:
                log.warning("Rate-limited on timeline @%s — backing off", handle)
                break

        log.info("Collected %d unique tweets in %.1fs", len(all_tweets), time.time() - t0)

        # ---- Phase 3: build + score findings -------------------------------
        findings = self._build_findings(all_tweets)
        scored = 0
        for f in findings:
            self.confidence.score_finding(f, verify=True)
            self.store.save_finding(f)
            scored += 1

        elapsed = time.time() - t0
        stats = {
            "tweets_collected": len(all_tweets),
            "findings_built": len(findings),
            "findings_scored": scored,
            "elapsed_s": round(elapsed, 1),
            **self.store.stats(),
        }
        log.info("Cycle complete: %s", stats)
        return stats, findings

    # -- classification + clustering ------------------------------------------

    def _classify(self, text: str) -> tuple[str, FindingType]:
        """Match a tweet's text to a topic by keyword presence."""
        low = text.lower()
        for topic, spec in self.cfg.topics.items():
            for kw in spec.get("keywords", []):
                if kw.lower() in low:
                    return topic, FindingType(spec.get("finding_type", "general"))
        return "news", FindingType.NEWS

    def _build_findings(self, tweets: list[Tweet]) -> list[Finding]:
        """Group tweets into findings by topic + shared entities.

        Strategy: within a topic, cluster tweets that share a "claim key"
        (a normalized set of significant entities).  This groups tweets
        reporting the same deal/launch even with different wording.
        """
        clusters: dict[tuple, list[Tweet]] = defaultdict(list)
        for tw in tweets:
            topic = getattr(tw, "_topic", "news")
            ftype = getattr(tw, "_finding_type", FindingType.GENERAL)
            entities = self._extract_entities(tw.text)
            deal = DEAL_AMOUNT_RE.search(tw.text)
            deal_str = (deal.group(0) if deal else "").lower()
            # Claim key: (topic, sorted-top-entity, deal-amount) — coarse but
            # effective for grouping "X free AI service" mentions.
            primary = entities[0].lower() if entities else ""
            key = (topic, primary, deal_str)
            clusters[key].append(tw)

        findings: list[Finding] = []
        for (topic, primary, deal), group in clusters.items():
            if not group:
                continue
            ftype = getattr(group[0], "_finding_type", FindingType.GENERAL)
            top = max(group, key=lambda t: t.engagement_score)
            headline = self._make_headline(top.text, primary, deal)
            summary = self._make_summary(top, group)
            f = Finding(
                finding_type=ftype,
                headline=headline,
                summary=summary,
                tweets=group,
                topic=topic,
            )
            findings.append(f)

        # Sort by source count + engagement so the strongest surface first.
        findings.sort(
            key=lambda f: (f.source_count, f.top_tweet.engagement_score if f.top_tweet else 0),
            reverse=True,
        )
        return findings

    @staticmethod
    def _extract_entities(text: str) -> list[str]:
        """Extract significant capitalized entities + deal terms."""
        found = ENTITY_RE.findall(text)
        # flatten (regex has alternation groups producing tuples)
        flat: list[str] = []
        for item in found:
            if isinstance(item, tuple):
                flat.extend(x for x in item if x)
            else:
                flat.append(item)
        # Dedupe, drop generic words, keep order.
        seen: set[str] = set()
        out: list[str] = []
        stopwords = {"the", "a", "an", "i", "is", "are", "this", "that", "just", "new"}
        for e in flat:
            el = e.lower()
            if el in stopwords or len(el) < 2:
                continue
            if el not in seen:
                seen.add(el)
                out.append(e)
        return out

    @staticmethod
    def _make_headline(text: str, primary: str, deal: str) -> str:
        """Generate a concise headline from the tweet text + extracted entities."""
        # Take first ~100 chars of the tweet, clean up.
        clean = text.replace("\n", " ").strip()
        # If we found a deal amount, prepend it for clarity.
        if deal:
            clean = f"[{deal}] {clean}"
        return clean[:140]

    @staticmethod
    def _make_summary(top: Tweet, group: list[Tweet]) -> str:
        """1-2 sentence summary: the top tweet's text + source count."""
        text = top.text.replace("\n", " ").strip()[:200]
        n = len(group)
        authors = {t.author.screen_name for t in group if t.author.screen_name}
        author_str = ", ".join(f"@{a}" for a in list(authors)[:3])
        if n == 1:
            return f"{text}"
        return f"{text}  (reported by {n} sources: {author_str})"
