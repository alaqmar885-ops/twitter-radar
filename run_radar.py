#!/usr/bin/env python3
"""AIOfferRadar entry point - multi-platform free-AI-offer radar + agent team.

Usage:
    python run_radar.py sources            # list sources + live availability
    python run_radar.py run [--offline]    # full agent-team cycle
    python run_radar.py report             # re-render digest from the store
    python run_radar.py status             # store stats
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Windows-safe UTF-8 stdio (same fix as run.py).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from airadar.config import load_ai_config          # noqa: E402
from airadar.classify import OfferClassifier       # noqa: E402
from airadar.scoring import OfferScorer            # noqa: E402
from airadar.store import Store                    # noqa: E402
from airadar.agents.team import AgentTeam          # noqa: E402
from airadar.models import Item                    # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("airadar")


def _router(cfg):
    try:
        from airadar.router import SourceRouter
        return SourceRouter(cfg)
    except Exception as exc:  # noqa: BLE001
        log.warning("SourceRouter unavailable: %s", exc)
        return None


def _enricher(cfg):
    try:
        import os
        key = os.environ.get("YDC_API_KEY", "")
        if not key:
            return None
        from twitter_radar.enrich.youcom import YouComEnricher
        return YouComEnricher(api_key=key, max_results=4)
    except Exception as exc:  # noqa: BLE001
        log.debug("enricher unavailable: %s", exc)
        return None


def _fixtures():
    """Offline fixtures: a couple of offer-bearing items, zero network."""
    return [
        Item(id="tw:fixture1", platform="twitter", author="levelsio",
             title="Free tier", text="Cursor Pro free for 2 weeks with code CURSORFREE - limited time!",
             url="https://example.com/cursor", created_at="2026-09-17T09:00:00Z",
             metrics={"likes": 120}),
        Item(id="hn:fixture2", platform="hackernews", author="pg",
             title="Show HN: Free AI credits for developers",
             text="We give $20 in free credits, no credit card. 50% off first month.",
             url="https://example.com/credits", created_at="2026-09-17T08:00:00Z",
             metrics={"points": 88}),
        Item(id="tg:fixture3", platform="telegram", author="chan",
             title="Lifetime deal", text="Lifetime deal on AI writer - 90% off today only. Promo code: SAVE90",
             url="https://example.com/ltd", created_at="2026-09-16T18:00:00Z", metrics={}),
        Item(id="rss:fixture4", platform="rss", author="blog",
             title="Weekly news", text="Nothing to see here, just a regular product update.",
             url="https://example.com/news", created_at="2026-09-15T10:00:00Z", metrics={}),
    ]


def cmd_sources(cfg):
    router = _router(cfg)
    if router is None:
        print("SourceRouter unavailable (sources package not importable)")
        return 1
    print("=== AIOfferRadar sources ===")
    try:
        names = [s.name for s in router.sources]
    except Exception as exc:  # noqa: BLE001
        print(f"could not list sources: {exc}")
        return 1
    print("configured:", ", ".join(getattr(cfg, "enabled_sources", []) or []) or "(none)")
    print("loaded    :", ", ".join(names) or "(none)")
    print()
    avail = router.available()
    for name, ok in avail.items():
        print(f"  [{'x' if ok else ' '}] {name}")
    return 0


def cmd_run(cfg, offline: bool):
    store = Store(cfg.db_path)
    classifier = OfferClassifier(cfg)
    scorer = OfferScorer(cfg)
    router = None if offline else _router(cfg)
    enricher = None if offline else _enricher(cfg)
    team = AgentTeam(cfg, offline=offline, router=router, store=store,
                     classifier=classifier, scorer=scorer, enricher=enricher,
                     seed_items=_fixtures() if offline else [])
    stats = team.run_once()
    print("\n=== Agent team run ===")
    for k in ("offline", "items", "kept", "offers", "elapsed_s"):
        print(f"  {k}: {stats.get(k)}")
    print("\n  agents:")
    for a in stats.get("agents", []):
        print(f"    {a['agent']:<9} {a['status']:<7} {a['counts']}")
    print("\n  top offers:")
    for o in stats.get("top_offers", []):
        print(f"    [{o['label']}] {o['score']:.0%} {o['title'][:80]}")
    store.close()
    return 0


def cmd_report(cfg):
    store = Store(cfg.db_path)
    offers = store.top_offers(limit=getattr(cfg, "top_n", 25))
    from airadar.agents.reporter import ReporterAgent
    from airadar.agents.base import AgentContext
    ctx = AgentContext(cfg=cfg, store=store, offers=offers, offline=True)
    rep = ReporterAgent().run(ctx)
    print("digest:", rep.counts.get("html"))
    store.close()
    return 0


def cmd_status(cfg):
    store = Store(cfg.db_path)
    print("=== AIOfferRadar store ===")
    for k, v in store.stats().items():
        print(f"  {k}: {v}")
    store.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description="AIOfferRadar - multi-platform free-AI-offer radar")
    ap.add_argument("command", choices=["sources", "run", "report", "status"])
    ap.add_argument("--offline", action="store_true",
                    help="run the agent team on local fixtures with zero network")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg_path = Path(args.config).resolve()
    if cfg_path.parent.exists():
        import os
        os.chdir(cfg_path.parent)

    cfg = load_ai_config(args.config)

    if args.command == "sources":
        return cmd_sources(cfg)
    if args.command == "run":
        return cmd_run(cfg, args.offline)
    if args.command == "report":
        return cmd_report(cfg)
    if args.command == "status":
        return cmd_status(cfg)
    return 1


if __name__ == "__main__":
    sys.exit(main())
