"""SQLite storage with deduplication.

Stores raw tweets (deduped by tweet_id) and scored findings so we can:
  - track which tweets we've already collected (no re-fetch / re-score)
  - produce historical digests ("what changed since last run")
  - avoid re-verifying findings we've already scored

The schema is intentionally simple — one tweets table, one findings table.
Both use INSERT OR IGNORE so re-runs are idempotent.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

from .models import Finding, FindingType, Tweet

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tweets (
    tweet_id    TEXT PRIMARY KEY,
    text        TEXT NOT NULL,
    author      TEXT NOT NULL,           -- JSON
    created_at  TEXT,
    like_count  INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    retweet_count INTEGER DEFAULT 0,
    quote_count INTEGER DEFAULT 0,
    engagement  INTEGER DEFAULT 0,
    url         TEXT,
    backend     TEXT,
    topic       TEXT,
    fetched_at  REAL
);

CREATE TABLE IF NOT EXISTS findings (
    id          TEXT PRIMARY KEY,
    type        TEXT,
    headline    TEXT,
    summary     TEXT,
    topic       TEXT,
    confidence  REAL,
    label       TEXT,
    web_verified INTEGER DEFAULT 0,
    source_count INTEGER DEFAULT 0,
    tweet_ids   TEXT,                    -- JSON array
    web_sources TEXT,                    -- JSON array
    first_seen  REAL,
    last_updated REAL
);

CREATE INDEX IF NOT EXISTS idx_tweets_topic ON tweets(topic);
CREATE INDEX IF NOT EXISTS idx_tweets_fetched ON tweets(fetched_at);
CREATE INDEX IF NOT EXISTS idx_findings_confidence ON findings(confidence DESC);
"""


class Store:
    """SQLite-backed tweet + finding persistence."""

    def __init__(self, db_path: str = "data/twitter_radar.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        log.info("Store ready at %s", self.db_path)

    def close(self) -> None:
        self._conn.close()

    # -- tweets ----------------------------------------------------------------

    def save_tweet(self, tw: Tweet, topic: str = "") -> bool:
        """Insert a tweet.  Returns True if newly inserted (not a duplicate)."""
        from dataclasses import asdict
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO tweets "
            "(tweet_id, text, author, created_at, like_count, reply_count, "
            " retweet_count, quote_count, engagement, url, backend, topic, fetched_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tw.tweet_id,
                tw.text,
                json.dumps({
                    "screen_name": tw.author.screen_name,
                    "followers": tw.author.followers,
                    "verified": tw.author.verified,
                    "name": tw.author.name,
                }),
                tw.created_at,
                tw.like_count,
                tw.reply_count,
                tw.retweet_count,
                tw.quote_count,
                tw.engagement_score,
                tw.url,
                tw.source_backend.value,
                topic,
                tw.fetched_at,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def seen(self, tweet_id: str) -> bool:
        """Has this tweet already been collected?"""
        cur = self._conn.execute(
            "SELECT 1 FROM tweets WHERE tweet_id = ?", (tweet_id,)
        )
        return cur.fetchone() is not None

    def recent_tweet_ids(self, limit: int = 500) -> set[str]:
        cur = self._conn.execute(
            "SELECT tweet_id FROM tweets ORDER BY fetched_at DESC LIMIT ?", (limit,)
        )
        return {row[0] for row in cur.fetchall()}

    # -- findings --------------------------------------------------------------

    def save_finding(self, f: Finding) -> bool:
        cur = self._conn.execute(
            "INSERT OR REPLACE INTO findings "
            "(id, type, headline, summary, topic, confidence, label, "
            " web_verified, source_count, tweet_ids, web_sources, first_seen, last_updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f.id,
                f.finding_type.value,
                f.headline,
                f.summary,
                f.topic,
                f.confidence,
                f.confidence_label,
                int(f.web_verified),
                f.source_count,
                json.dumps([t.tweet_id for t in f.tweets]),
                json.dumps(f.web_sources[:6]),
                f.first_seen,
                f.last_updated,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def top_findings(self, limit: int = 20, min_confidence: float = 0.0) -> list[Finding]:
        """Load top findings by confidence, for digest generation.

        Also reconstructs minimal Tweet objects (from the tweets table) so
        the digest can show source tweets + authors even when rendering from
        stored data rather than in-memory.
        """
        cur = self._conn.execute(
            "SELECT * FROM findings WHERE confidence >= ? "
            "ORDER BY confidence DESC, last_updated DESC LIMIT ?",
            (min_confidence, limit),
        )
        out: list[Finding] = []
        for row in cur.fetchall():
            tweet_ids = json.loads(row["tweet_ids"] or "[]")
            tweets = self._load_tweets(tweet_ids[:5])
            out.append(Finding(
                id=row["id"],
                finding_type=FindingType(row["type"]),
                headline=row["headline"],
                summary=row["summary"],
                topic=row["topic"],
                confidence=row["confidence"],
                confidence_label=row["label"],
                web_verified=bool(row["web_verified"]),
                web_sources=json.loads(row["web_sources"] or "[]"),
                tweets=tweets,
                first_seen=row["first_seen"],
                last_updated=row["last_updated"],
            ))
        return out

    def _load_tweets(self, tweet_ids: list[str]) -> list[Tweet]:
        """Reconstruct minimal Tweet objects from stored rows."""
        if not tweet_ids:
            return []
        placeholders = ",".join("?" * len(tweet_ids))
        cur = self._conn.execute(
            f"SELECT * FROM tweets WHERE tweet_id IN ({placeholders})",
            tweet_ids,
        )
        from .models import Author, Backend
        tweets = []
        for row in cur.fetchall():
            a = json.loads(row["author"] or "{}")
            tweets.append(Tweet(
                tweet_id=row["tweet_id"],
                text=row["text"],
                author=Author(
                    screen_name=a.get("screen_name", ""),
                    followers=a.get("followers", 0),
                    verified=a.get("verified", False),
                    name=a.get("name", ""),
                ),
                like_count=row["like_count"],
                reply_count=row["reply_count"],
                retweet_count=row["retweet_count"],
                quote_count=row["quote_count"],
                url=row["url"],
                source_backend=Backend(row["backend"]) if row["backend"] else Backend.FXTWITTER,
            ))
        return tweets

    def stats(self) -> dict:
        cur = self._conn.execute("SELECT COUNT(*) FROM tweets")
        tweet_count = cur.fetchone()[0]
        cur = self._conn.execute("SELECT COUNT(*) FROM findings")
        finding_count = cur.fetchone()[0]
        cur = self._conn.execute(
            "SELECT label, COUNT(*) FROM findings GROUP BY label"
        )
        by_label = {row[0]: row[1] for row in cur.fetchall()}
        return {
            "tweets": tweet_count,
            "findings": finding_count,
            "by_label": by_label,
        }
