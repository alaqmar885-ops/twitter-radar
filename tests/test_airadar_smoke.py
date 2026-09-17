"""Offline smoke test for AIOfferRadar. Zero network.

Run:  python tests/test_airadar_smoke.py     (or via pytest)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from airadar.config import load_ai_config          # noqa: E402
from airadar.classify import OfferClassifier       # noqa: E402
from airadar.scoring import OfferScorer            # noqa: E402
from airadar.models import Item, Offer             # noqa: E402
from airadar.agents.team import AgentTeam          # noqa: E402


def _cfg(tmp_db: str):
    cfg = load_ai_config(ROOT / "config.yaml")
    cfg.db_path = tmp_db
    cfg.digest_dir = str(ROOT / "data" / "digests_test")
    cfg.top_n = 10
    return cfg


def test_classifier_extracts_promo_code():
    cfg = _cfg(":memory:")
    c = OfferClassifier(cfg)
    text = "Cursor Pro free for 2 weeks with code CURSORFREE - limited time!"
    it = Item(id="t1", platform="twitter", text=text, title="Free tier",
              url="https://example.com/x")
    assert c.is_offer(it) is True
    assert c.extract_promo_code(text) == "CURSORFREE"
    info = c.classify(it)
    assert info is not None and info["offer_type"]


def test_scorer_labels():
    cfg = _cfg(":memory:")
    s = OfferScorer(cfg)
    o = Offer(title="Free credits for AI API", offer_type="free_credits",
              value="$20 credits", platforms=["twitter"], link_ok=True)
    o.items = [Item(id="a", platform="twitter", author="x", text="free credits")]
    s.score(o)
    assert 0.0 < o.score <= 1.0
    assert o.label in ("LOW", "MEDIUM", "HIGH", "VERIFIED")


def test_offline_pipeline_produces_offer():
    cfg = _cfg(":memory:")
    from run_radar import _fixtures
    from airadar.store import Store
    store = Store(":memory:")
    team = AgentTeam(cfg, offline=True, store=store,
                     classifier=OfferClassifier(cfg), scorer=OfferScorer(cfg),
                     seed_items=_fixtures())
    stats = team.run_once()
    assert stats["items"] >= 3
    assert stats["offers"] >= 1, stats
    assert any(o["score"] > 0 for o in stats["top_offers"])
    store.close()


if __name__ == "__main__":
    test_classifier_extracts_promo_code()
    test_scorer_labels()
    test_offline_pipeline_produces_offer()
    print("OK: all offline smoke tests passed")
