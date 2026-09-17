"""Precision tests: the classifier must reject non-offers that contain 'free'."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from airadar.config import load_ai_config      # noqa: E402
from airadar.models import Item                # noqa: E402
from airadar.signals import is_offer_text, score_text   # noqa: E402

NEGATIVES = [
    "Mojo compiler is open for open source contributions",
    "Taxes while living abroad as a US citizen",
    "How I built a debugging tool and found bugs in it",
    "Compute:Arena - Community submitted local AI benchmarks",
    "Grok is no longer free and here is what to use instead",
    "This plan is paid only, no free tier available",
    "Weekly AI news roundup",
]

POSITIVES = [
    "Cursor Pro free for 2 weeks, no credit card required",
    "Free tier available, start free today",
    "Get $20 in free credits, no card needed",
    "Lifetime deal: 90% off with promo code SAVE90",
    "Open source model released, self-hosted for free",
]


def test_negatives_rejected():
    bad = [t for t in NEGATIVES if is_offer_text(t)]
    assert not bad, f"false positives: {bad}"


def test_positives_accepted():
    bad = [t for t in POSITIVES if not is_offer_text(t)]
    assert not bad, f"false negatives: {bad}"


def test_negative_evidence_vetoes():
    text = "Grok is no longer free and the free tier is gone"
    s = score_text(text)
    assert s["veto"], f"expected a hard veto, got {s}"
    assert s["score"] == 0, s
    assert is_offer_text(text) is False


def test_classifier_full_flow():
    cfg = load_ai_config(ROOT / "config.yaml")
    from airadar.classify import OfferClassifier
    c = OfferClassifier(cfg)
    good = Item(id="1", platform="x", title="Free tier, no credit card",
                text="Start free with 500 free credits today")
    bad = Item(id="2", platform="x", title="Compiler contribution guide",
               text="Open for open source contributions")
    assert c.is_offer(good) is True
    assert c.is_offer(bad) is False
    info = c.classify(good)
    assert info and info["signal_score"] >= 3 and info["offer_type"]


if __name__ == "__main__":
    test_negatives_rejected()
    test_positives_accepted()
    test_negative_evidence_vetoes()
    test_classifier_full_flow()
    print("OK: precision tests passed")
