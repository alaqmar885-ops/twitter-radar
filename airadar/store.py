"""SQLite store for AIOfferRadar items + offers + per-finding verifications."""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path

from .models import Item, Offer

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY, platform TEXT, author TEXT, title TEXT, text TEXT,
    url TEXT, created_at TEXT, metrics TEXT, source TEXT, query TEXT, fetched_at REAL
);
CREATE TABLE IF NOT EXISTS offers (
    id TEXT PRIMARY KEY, title TEXT, summary TEXT, offer_type TEXT, value TEXT,
    promo_code TEXT, product TEXT, url TEXT, platforms TEXT, score REAL, label TEXT,
    link_ok INTEGER DEFAULT 0, web_verified INTEGER DEFAULT 0, web_sources TEXT,
    item_ids TEXT, first_seen REAL, last_updated REAL, verdict TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS verifications (
    offer_id TEXT PRIMARY KEY, status TEXT, page_status INTEGER,
    signals TEXT, no_cc_signals TEXT, card_signals TEXT,
    web_hits INTEGER, page_title TEXT, notes TEXT, checked_at REAL
);
CREATE INDEX IF NOT EXISTS idx_items_platform ON items(platform);
CREATE INDEX IF NOT EXISTS idx_offers_score ON offers(score DESC);
"""


class Store:
    def __init__(self, db_path: str = "data/airadar.db"):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        # migrate older DBs that predate the verdict column
        try:
            self._conn.execute("ALTER TABLE offers ADD COLUMN verdict TEXT DEFAULT ''")
        except Exception:
            pass
        for col in ("no_cc_signals", "card_signals"):
            try:
                self._conn.execute(f"ALTER TABLE verifications ADD COLUMN {col} TEXT")
            except Exception:
                pass
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # -- items -----------------------------------------------------------------
    def save_item(self, it: Item) -> bool:
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO items (id, platform, author, title, text, url, "
            "created_at, metrics, source, query, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            it.as_row())
        self._conn.commit()
        return cur.rowcount > 0

    def seen_item(self, item_id: str) -> bool:
        return self._conn.execute("SELECT 1 FROM items WHERE id = ?",
                                  (item_id,)).fetchone() is not None

    def all_items(self) -> list:
        cur = self._conn.execute("SELECT * FROM items")
        out = []
        for row in cur.fetchall():
            out.append(Item(
                id=row["id"], platform=row["platform"] or "", author=row["author"] or "",
                title=row["title"] or "", text=row["text"] or "", url=row["url"] or "",
                created_at=row["created_at"] or "",
                metrics=json.loads(row["metrics"] or "{}"),
                source=row["source"] or "", query=row["query"] or "",
                fetched_at=float(row["fetched_at"] or 0.0)))
        return out

    # -- offers ----------------------------------------------------------------
    def save_offer(self, o: Offer) -> bool:
        cur = self._conn.execute(
            "INSERT OR REPLACE INTO offers (id, title, summary, offer_type, value, "
            "promo_code, product, url, platforms, score, label, link_ok, web_verified, "
            "web_sources, item_ids, first_seen, last_updated, verdict) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (o.id, o.title, o.summary, o.offer_type, o.value, o.promo_code, o.product,
             o.url, json.dumps(o.platforms or []), o.score, o.label, int(bool(o.link_ok)),
             int(bool(o.web_verified)), json.dumps(o.web_sources[:6] if o.web_sources else []),
             json.dumps([i.id for i in o.items]), o.first_seen, o.last_updated,
             getattr(o, "verdict", "") or ""))
        self._conn.commit()
        return cur.rowcount > 0

    def set_verdict(self, offer_id: str, verdict: str) -> None:
        self._conn.execute("UPDATE offers SET verdict = ? WHERE id = ?", (verdict, offer_id))
        self._conn.commit()

    def save_verification(self, offer_id: str, v: dict) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO verifications (offer_id, status, page_status, "
            "signals, no_cc_signals, card_signals, web_hits, page_title, notes, checked_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (offer_id, v.get("status", ""), int(v.get("page_status") or 0),
             json.dumps(v.get("signals") or []),
             json.dumps(v.get("no_cc_signals") or []),
             json.dumps(v.get("card_signals") or []),
             int(v.get("web_hits") or 0),
             v.get("page_title", ""), json.dumps(v.get("notes") or []), time.time()))
        self._conn.commit()

    def verifications(self) -> dict:
        cur = self._conn.execute("SELECT * FROM verifications")
        out = {}
        for r in cur.fetchall():
            d = dict(r)
            out[r["offer_id"]] = {
                "status": r["status"],
                "page_status": r["page_status"],
                "signals": json.loads(r["signals"] or "[]"),
                "no_cc_signals": json.loads(d.get("no_cc_signals") or "[]"),
                "card_signals": json.loads(d.get("card_signals") or "[]"),
                "web_hits": r["web_hits"],
                "page_title": r["page_title"] or "",
                "notes": json.loads(r["notes"] or "[]"),
            }
        return out

    def top_offers(self, limit: int = 25, min_score: float = 0.0,
                   verdicts: list | None = None) -> list:
        sql = "SELECT * FROM offers WHERE score >= ?"
        args: list = [min_score]
        if verdicts:
            sql += " AND verdict IN (%s)" % ",".join("?" * len(verdicts))
            args.extend(verdicts)
        sql += " ORDER BY score DESC, last_updated DESC LIMIT ?"
        args.append(limit)
        out = []
        for row in self._conn.execute(sql, args).fetchall():
            ids = json.loads(row["item_ids"] or "[]")
            o = Offer(
                id=row["id"], title=row["title"] or "", summary=row["summary"] or "",
                offer_type=row["offer_type"] or "other", value=row["value"] or "",
                promo_code=row["promo_code"] or "", product=row["product"] or "",
                url=row["url"] or "", platforms=json.loads(row["platforms"] or "[]"),
                items=self._load_items(ids[:5]), score=float(row["score"] or 0.0),
                label=row["label"] or "LOW", link_ok=bool(row["link_ok"]),
                web_verified=bool(row["web_verified"]),
                web_sources=json.loads(row["web_sources"] or "[]"),
                first_seen=float(row["first_seen"] or time.time()),
                last_updated=float(row["last_updated"] or time.time()))
            o.verdict = row["verdict"] or ""
            out.append(o)
        return out

    def _load_items(self, ids: list) -> list:
        if not ids:
            return []
        q = ",".join("?" * len(ids))
        cur = self._conn.execute(f"SELECT * FROM items WHERE id IN ({q})", ids)
        return [Item(id=r["id"], platform=r["platform"] or "", author=r["author"] or "",
                     title=r["title"] or "", text=r["text"] or "", url=r["url"] or "",
                     created_at=r["created_at"] or "",
                     metrics=json.loads(r["metrics"] or "{}"), source=r["source"] or "",
                     query=r["query"] or "", fetched_at=float(r["fetched_at"] or 0.0))
                for r in cur.fetchall()]

    def stats(self) -> dict:
        c = self._conn
        by_verdict = {r[0] or "(none)": r[1] for r in c.execute(
            "SELECT verdict, COUNT(*) FROM offers GROUP BY verdict").fetchall()}
        return {
            "items": c.execute("SELECT COUNT(*) FROM items").fetchone()[0],
            "offers": c.execute("SELECT COUNT(*) FROM offers").fetchone()[0],
            "items_by_platform": {r[0]: r[1] for r in c.execute(
                "SELECT platform, COUNT(*) FROM items GROUP BY platform").fetchall()},
            "offers_by_label": {r[0]: r[1] for r in c.execute(
                "SELECT label, COUNT(*) FROM offers GROUP BY label").fetchall()},
            "offers_by_verdict": by_verdict,
        }
