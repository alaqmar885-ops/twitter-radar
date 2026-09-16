#!/usr/bin/env python3
"""TwitterRadar — entry point.

Usage:
    python run.py once        # single collection cycle (cron-friendly)
    python run.py loop        # run forever, cycling every interval_minutes
    python run.py digest      # just render a digest from existing data
    python run.py status      # show store stats + VPN status
    python run.py test        # test the free no-auth endpoints live

Config: config.yaml (override via --config path/to/config.yaml)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure local package importable when run as a script.
sys.path.insert(0, str(Path(__file__).parent))

from twitter_radar.config import load_config
from twitter_radar.confidence import ConfidenceEngine
from twitter_radar.collector import Collector
from twitter_radar.digest.report import DigestRenderer
from twitter_radar.enrich.youcom import YouComEnricher
from twitter_radar.router import Router
from twitter_radar.scheduler import Scheduler
from twitter_radar.store import Store
from twitter_radar.vpn.proton import ProtonVPNManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("twitter-radar")


def build_components(cfg):
    """Wire up all components from a Config."""
    router = Router(cfg)
    store = Store(cfg.db_path)
    enricher = YouComEnricher(
        api_key=cfg.youcom_api_key,
        mcp_url=cfg.youcom.mcp_url,
        max_results=cfg.youcom.max_verify_results,
    ) if cfg.youcom.enabled else None
    confidence = ConfidenceEngine(
        enricher=enricher,
        min_credibility_for_verify=cfg.youcom.min_credibility_for_verify,
    )
    collector = Collector(cfg, router, store, confidence)
    vpn = ProtonVPNManager(cfg.vpn)
    return router, store, enricher, confidence, collector, vpn


def cmd_test(cfg):
    """Live-test the free no-auth endpoints."""
    from twitter_radar.backends.fxtwitter import FxTwitterBackend
    from twitter_radar.backends.syndication import SyndicationBackend
    from twitter_radar.backends.oembed import OEmbedBackend

    print("=== Testing free no-auth endpoints ===\n")
    for name, backend in [
        ("FxTwitter", FxTwitterBackend(timeout=15, delay=0)),
        ("Syndication", SyndicationBackend(timeout=15, delay=0)),
        ("oEmbed", OEmbedBackend(timeout=15, delay=0)),
    ]:
        print(f"--- {name} available: {backend.available()} ---")

    # FxTwitter timeline
    fx = FxTwitterBackend(timeout=15, delay=0)
    r = fx.get_timeline("levelsio", limit=3)
    print(f"\nFxTwitter timeline @levelsio: ok={r.ok} tweets={len(r.tweets)}")
    if r.tweets:
        tw = r.tweets[0]
        print(f"  first: {tw.text[:80]}...")

    # Syndication single tweet
    sy = SyndicationBackend(timeout=15, delay=0)
    # Use a known tweet id from the research report
    r = sy.get_tweet("2021699240393609717")
    print(f"\nSyndication single tweet: ok={r.ok} tombstones={r.tombstones}")
    if r.tweets:
        tw = r.tweets[0]
        print(f"  author: @{tw.author.screen_name} text: {tw.text[:80]}")

    # oEmbed
    oe = OEmbedBackend(timeout=15, delay=0)
    r = oe.get_tweet("2021699240393609717", handle="levelsio")
    print(f"\noEmbed: ok={r.ok}")
    if r.tweets:
        print(f"  author: @{r.tweets[0].author.screen_name}")

    print("\n✅ Free endpoints test complete.")


def cmd_once(cfg):
    router, store, enricher, confidence, collector, vpn = build_components(cfg)
    scheduler = Scheduler(cfg, collector, vpn)
    stats, findings = scheduler.run_once()
    print("\n=== Cycle Results ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Generate digest from in-memory findings (have full tweet data).
    renderer = DigestRenderer(store, cfg.digest_dir)
    path = renderer.render(findings, top_n=cfg.top_n_findings,
                           fmt=cfg.digest_format, cycle_stats=stats)
    print(f"\n=== Digest → {path} ===")
    return path


def cmd_loop(cfg):
    router, store, enricher, confidence, collector, vpn = build_components(cfg)
    scheduler = Scheduler(cfg, collector, vpn)
    scheduler.run_forever()


def cmd_digest(cfg):
    store = Store(cfg.db_path)
    findings = store.top_findings(limit=cfg.top_n_findings)
    renderer = DigestRenderer(store, cfg.digest_dir)
    path = renderer.render(findings, top_n=cfg.top_n_findings,
                           fmt=cfg.digest_format)
    print(f"Digest → {path}")
    return path


def cmd_status(cfg):
    store = Store(cfg.db_path)
    print("=== Store Stats ===")
    for k, v in store.stats().items():
        print(f"  {k}: {v}")
    vpn = ProtonVPNManager(cfg.vpn)
    print("\n=== VPN ===")
    if vpn.available():
        print(f"  status: {vpn.status()}")
    else:
        print("  not available (install: sudo pip3 install protonvpn-cli && sudo protonvpn init)")
    if cfg.youcom_api_key:
        print(f"\n=== You.com ===\n  API key: set ✓")
    else:
        print(f"\n=== You.com ===\n  API key: NOT SET (export YDC_API_KEY=...)")


def main():
    ap = argparse.ArgumentParser(description="TwitterRadar — self-hosted X intelligence scraper")
    ap.add_argument("command", choices=["once", "loop", "digest", "status", "test"],
                    help="once=single cycle, loop=daemon, digest=render only, status=info, test=live endpoint check")
    ap.add_argument("--config", default="config.yaml", help="config file path")
    args = ap.parse_args()

    # Make data paths absolute relative to the config file's directory,
    # so the tool works no matter what cwd you invoke it from.
    config_path = Path(args.config).resolve()
    if config_path.parent.exists():
        import os
        os.chdir(config_path.parent)

    cfg = load_config(args.config)

    if args.command == "test":
        cmd_test(cfg)
    elif args.command == "once":
        cmd_once(cfg)
    elif args.command == "loop":
        cmd_loop(cfg)
    elif args.command == "digest":
        cmd_digest(cfg)
    elif args.command == "status":
        cmd_status(cfg)


if __name__ == "__main__":
    main()
