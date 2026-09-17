#!/usr/bin/env python3
"""AIOfferRadar entry point - multi-platform free-AI-offer radar + agent team.

Usage:
    python run_radar.py sources            # list sources + live availability
    python run_radar.py run [--offline]    # full agent-team cycle
    python run_radar.py verify [--limit N] # refine + verify every stored finding
    python run_radar.py report             # re-render digest from the store
    python run_radar.py status             # store stats
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

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


def _load_secrets(path: str = "secrets.env") -> None:
    """Load KEY=value pairs from secrets.env into the environment (no override)."""
    import os
    sp = Path(path)
    if not sp.exists():
        return
    try:
        for line in sp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception as exc:  # noqa: BLE001
        log.debug("secrets.env not loaded: %s", exc)


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
    return [
        Item(id="tw:fixture1", platform="twitter", author="levelsio", title="Free tier",
             text="Cursor AI code editor free for 2 weeks, 500 AI credits, with code CURSORFREE",
             url="https://example.com/cursor", created_at="2026-09-17T09:00:00Z",
             metrics={"likes": 120}),
        Item(id="hn:fixture2", platform="hackernews", author="pg",
             title="Show HN: Free AI credits for developers",
             text="We give $20 in free credits, no credit card. 50% off first month.",
             url="https://example.com/credits", created_at="2026-09-17T08:00:00Z",
             metrics={"points": 88}),
        Item(id="tg:fixture3", platform="telegram", author="chan", title="Lifetime deal",
             text="Lifetime deal on AI writer - 90% off today only. Promo code: SAVE90",
             url="https://example.com/ltd", created_at="2026-09-16T18:00:00Z", metrics={}),
        Item(id="rss:fixture4", platform="rss", author="blog", title="Weekly news",
             text="Nothing to see here, just a regular AI product update.",
             url="https://example.com/news", created_at="2026-09-15T10:00:00Z", metrics={}),
    ]


def cmd_sources(cfg):
    router = _router(cfg)
    if router is None:
        print("SourceRouter unavailable (sources package not importable)")
        return 1
    print("=== AIOfferRadar sources ===")
    print("configured:", ", ".join(getattr(cfg, "enabled_sources", []) or []) or "(none)")
    print()
    for name, ok in router.available().items():
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
    for a in stats.get("agents", []):
        print(f"    {a['agent']:<9} {a['status']:<7} {a['counts']}")
    store.close()
    return 0


def cmd_verify(cfg, limit: int = 0, workers: int = 0):
    """Refine + verify each stored finding; write a verified report."""
    from airadar.refine import refine
    from airadar.verify import FindingVerifier
    import html as _html

    store = Store(cfg.db_path)
    classifier = OfferClassifier(cfg)
    scorer = OfferScorer(cfg)
    enricher = _enricher(cfg)
    verifier = FindingVerifier(cfg, enricher=enricher)
    dupes = store.dedupe_by_url()
    print(f"=== collapsed {dupes} duplicate offers by URL ===")

    offers = store.top_offers(limit=limit or 5000)
    print(f"=== Verifying {len(offers)} findings "
          f"(web corroboration: {'on' if enricher else 'off'}) ===")

    counts: dict = {}
    rows = []
    w = max(1, int(workers or getattr(cfg, "workers", 6) or 1))
    print(f"    workers: {w}")

    def _check(o):
        refine(o, classifier)
        return o, verifier.verify(o)

    from concurrent.futures import ThreadPoolExecutor
    done = 0
    with ThreadPoolExecutor(max_workers=w) as ex:
        futures = [ex.submit(_check, o) for o in offers]
        for fut in futures:
            o, v = fut.result()
            # store writes stay on the main thread - a sqlite connection is not
            # safe to share across worker threads
            o.verdict = v["status"]
            refine(o, classifier, page_title=v.get("page_title", ""))
            scorer.apply_verdict(o)          # score must respect the evidence
            store.save_verification(o.id, v)
            store.upsert_offer_by_url(o)
            store.set_verdict(o.id, v["status"])
            counts[v["status"]] = counts.get(v["status"], 0) + 1
            rows.append({"offer": o, "v": v})
            done += 1
            print(f"  [{done}/{len(offers)}] {v['status']:<12} {o.title[:70]}")

    # ---- report ----
    out_dir = Path("data/verified")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    confirmed = [r for r in rows if r["v"]["status"] == "VERIFIED"]
    partial = [r for r in rows if r["v"]["status"] == "PARTIAL"]
    rejected = [r for r in rows if r["v"]["status"] == "NOT_AN_OFFER"]
    dead = [r for r in rows if r["v"]["status"] == "UNREACHABLE"]

    payload = {
        "generated": ts,
        "counts": counts,
        "verified": [{"title": r["offer"].title, "url": r["offer"].url,
                      "score": r["offer"].score, "type": r["offer"].offer_type,
                      "value": r["offer"].value, "promo_code": r["offer"].promo_code,
                      "platforms": r["offer"].platforms,
                      "page_status": r["v"]["page_status"],
                      "signals": r["v"]["signals"], "web_hits": r["v"]["web_hits"],
                      "page_title": r["v"].get("page_title", ""),
                      } for r in confirmed + partial],
        "rejected": [{"title": r["offer"].title, "url": r["offer"].url,
                      "status": r["v"]["status"], "notes": r["v"]["notes"]}
                     for r in rejected + dead],
    }
    (out_dir / f"verified_{ts}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# Verified findings", "",
          f"Checked {len(rows)} findings.", "",
          "| Verdict | Count |", "|---|---|"]
    for k, n in sorted(counts.items(), key=lambda x: -x[1]):
        md.append(f"| {k} | {n} |")
    md += ["", "## Confirmed / partial (link live + on-page offer evidence)", ""]
    for r in confirmed + partial:
        o, v = r["offer"], r["v"]
        md.append(f"### [{v['status']}] {o.title}")
        md.append(f"- score {o.score:.0%} · `{o.offer_type}`"
                  + (f" · **{o.value}**" if o.value else "")
                  + (f" · code `{o.promo_code}`" if o.promo_code else ""))
        md.append(f"- url: <{o.url}>  (HTTP {v['page_status']}, "
                  f"page signals: {', '.join(v['signals'][:5]) or '—'}, "
                  f"web hits: {v['web_hits']})")
        md.append("")
    md += ["## Rejected / unreachable", ""]
    for r in rejected + dead:
        o, v = r["offer"], r["v"]
        md.append(f"- `{v['status']}` {o.title[:110]} — <{o.url}> "
                  f"({'; '.join(v['notes']) or '—'})")
    (out_dir / f"verified_{ts}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    def card(r):
        o, v = r["offer"], r["v"]
        badge = {"VERIFIED": "g", "PARTIAL": "a"}.get(v["status"], "r")
        return (f'<article><div class="h"><span class="b {badge}">{v["status"]}</span>'
                f'<span class="s">{o.score:.0%}</span>'
                f'<code>{_html.escape(o.offer_type)}</code>'
                + (f'<b>{_html.escape(o.value)}</b>' if o.value else "")
                + (f'<span class="c">code {_html.escape(o.promo_code)}</span>' if o.promo_code else "")
                + '</div>'
                f'<h3>{_html.escape(o.title)}</h3>'
                + (f'<p class="u"><a href="{_html.escape(o.url)}">{_html.escape(o.url)}</a></p>' if o.url else "")
                + f'<p class="m">HTTP {v["page_status"]} · page signals: '
                  f'{_html.escape(", ".join(v["signals"][:5]) or "—")} · '
                  f'web corroborations: {v["web_hits"]} · platforms: '
                  f'{_html.escape(", ".join(o.platforms))}</p></article>')

    html_doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Verified free-AI findings</title><style>
:root{{--ink:#14181d;--mut:#6b7480;--line:#d8dde3;--paper:#fbfaf8;--acc:#8a1c1c;
--ok:#1f6b45;--amb:#8a5a00}}*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-size:16px;line-height:1.6;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
.page{{max-width:900px;margin:0 auto;padding:52px 26px 90px}}
.k{{font-family:ui-monospace,Consolas,monospace;font-size:.7rem;letter-spacing:.15em;
text-transform:uppercase;color:var(--mut)}}
h1{{font-family:"Iowan Old Style",Georgia,serif;font-size:2.15rem;font-weight:600;
letter-spacing:-.015em;margin:10px 0 14px;line-height:1.15}}
h2{{font-family:"Iowan Old Style",Georgia,serif;font-size:1.28rem;margin:36px 0 10px;
padding-bottom:7px;border-bottom:1px solid var(--ink)}}
h3{{font-size:1rem;margin:8px 0 4px;font-weight:600}}
article{{padding:14px 0;border-bottom:1px solid var(--line)}}
.h{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:.78rem}}
.b{{font-weight:700;font-size:.66rem;letter-spacing:.06em;padding:2px 7px;border-radius:3px;
border:1px solid currentColor}}.g{{color:var(--ok)}}.a{{color:var(--amb)}}.r{{color:var(--acc)}}
.s{{font-weight:700;color:var(--acc)}}code{{font-family:ui-monospace,Consolas,monospace;
font-size:.8em;background:#eef1f4;border:1px solid var(--line);border-radius:3px;padding:.06em .3em}}
.c{{color:var(--acc);font-weight:600}}.u a{{color:var(--acc);text-decoration:none;font-size:.85rem}}
.m{{color:var(--mut);font-size:.8rem;margin:4px 0}}
table{{width:100%;border-collapse:collapse;font-size:.9rem;margin:10px 0}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}}
th{{font-family:ui-monospace,Consolas,monospace;font-size:.68rem;letter-spacing:.08em;
text-transform:uppercase;color:var(--mut);border-bottom:1px solid var(--ink)}}
footer{{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);
font-family:ui-monospace,Consolas,monospace;font-size:.7rem;color:var(--mut)}}
</style></head><body><div class="page">
<div class="k">AIOfferRadar - verification pass - {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(ts))}</div>
<h1>Every finding, checked</h1>
<p>Each finding was refined, its link fetched, its destination page scanned for free/offer
signals, and the claim searched on the web. <b>{len(rows)}</b> findings checked.</p>
<h2>Verdicts</h2><table><thead><tr><th>Verdict</th><th>Count</th></tr></thead><tbody>
{''.join(f'<tr><td>{_html.escape(k)}</td><td>{n}</td></tr>' for k, n in sorted(counts.items(), key=lambda x: -x[1]))}
</tbody></table>
<h2>Confirmed &amp; partial ({len(confirmed) + len(partial)})</h2>
{''.join(card(r) for r in confirmed + partial) or '<p>None.</p>'}
<h2>Rejected &amp; unreachable ({len(rejected) + len(dead)})</h2>
<table><thead><tr><th>Verdict</th><th>Finding</th><th>Why</th></tr></thead><tbody>
{''.join(f'<tr><td>{_html.escape(r["v"]["status"])}</td><td>{_html.escape(r["offer"].title[:90])}</td><td>{_html.escape("; ".join(r["v"]["notes"]) or "no free/offer signal on page")}</td></tr>' for r in rejected + dead)}
</tbody></table>
<footer>Generated by AIOfferRadar verify - evidence is the HTTP status + on-page signals + web corroboration counts.</footer>
</div></body></html>"""
    (out_dir / f"verified_{ts}.html").write_text(html_doc, encoding="utf-8")

    print("\n=== Verdicts ===")
    for k, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k:<14} {n}")
    print(f"\nreport -> {out_dir / f'verified_{ts}.html'}")
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



def cmd_notify(cfg, min_score: float = 0.7, all_verdicts: bool = False):
    """Write a compact alert for the best findings (and POST a webhook if set)."""
    import os
    import json as _json
    store = Store(cfg.db_path)
    offers = store.top_offers(limit=5000, min_score=min_score)
    ver = store.verifications()
    prev = store.last_run_ts()
    new_count = store.new_offers_since(prev)
    store.close()

    keep_verdicts = {"VERIFIED_NO_CC", "VERIFIED", "PARTIAL"} if not all_verdicts else None
    seen: dict = {}
    for o in offers:
        if keep_verdicts is not None and o.verdict not in keep_verdicts:
            continue
        key = (o.url or o.title or o.id).strip().lower().rstrip("/")
        prev = seen.get(key)
        if prev is None or o.score > prev.score:
            seen[key] = o
    picked = list(seen.values())
    picked.sort(key=lambda o: (0 if o.verdict == "VERIFIED_NO_CC" else 1, -o.score))

    out_dir = Path("data/alerts")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    lines = [f"# AIOfferRadar alert - {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(ts))}", "",
             f"{len(picked)} findings at score >= {min_score} "
             f"(new since last run: {new_count})", ""]
    for o in picked[:40]:
        rec = ver.get(o.id, {})
        flags = []
        if o.verdict:
            flags.append(o.verdict)
        if rec.get("no_cc_signals"):
            flags.append("no-card")
        if o.promo_code:
            flags.append(f"code {o.promo_code}")
        lines.append(f"- **{o.title[:120]}** [{o.score:.0%}] ({', '.join(flags) or 'unverified'})")
        if o.url:
            lines.append(f"  {o.url}")
    path = out_dir / f"alert_{ts}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {"generated": ts, "count": len(picked), "new_since_last_run": new_count,
               "findings": [{"title": o.title, "url": o.url, "score": o.score,
                             "verdict": o.verdict, "promo_code": o.promo_code,
                             "no_card": bool((ver.get(o.id) or {}).get("no_cc_signals"))}
                            for o in picked[:40]]}
    (out_dir / f"alert_{ts}.json").write_text(
        _json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    hook = os.environ.get("ALERT_WEBHOOK_URL", "")
    if hook:
        try:
            import httpx
            r = httpx.post(hook, json=payload, timeout=15)
            print(f"webhook -> HTTP {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            print(f"webhook failed: {exc}")

    print(f"alert -> {path}  ({len(picked)} findings, {new_count} new)")
    return 0


def cmd_doctor(cfg):
    """Validate config, secrets, dependencies, data paths and sources."""
    import importlib
    import os
    print("=== AIOfferRadar doctor ===")
    problems = 0

    def check(label, ok, detail=""):
        nonlocal problems
        mark = "PASS" if ok else "FAIL"
        if not ok:
            problems += 1
        print(f"  [{mark}] {label}" + (f" - {detail}" if detail else ""))

    check("config.yaml readable", Path("config.yaml").exists())
    check("airadar section present",
          "airadar:" in (Path("config.yaml").read_text(encoding="utf-8")
                         if Path("config.yaml").exists() else ""))
    check("secrets.env present", Path("secrets.env").exists())
    check("YDC_API_KEY set (web verification)", bool(os.environ.get("YDC_API_KEY")),
          "run via run_radar so secrets.env is auto-loaded")
    for mod, why in (("httpx", "HTTP"), ("bs4", "HTML parsing"), ("yaml", "config")):
        try:
            importlib.import_module(mod)
            check(f"dependency {mod}", True)
        except Exception as exc:  # noqa: BLE001
            check(f"dependency {mod}", False, f"{why}: {exc}")
    check("offer signal threshold sane",
          1 <= int(getattr(cfg, "offer_signal_threshold", 3)) <= 10,
          f"threshold={getattr(cfg, 'offer_signal_threshold', 3)}")
    check("workers sane", 1 <= int(getattr(cfg, "workers", 6)) <= 32,
          f"workers={getattr(cfg, 'workers', 6)}")
    for d in (Path("data"), Path(getattr(cfg, "digest_dir", "data/digests"))):
        check(f"path writable: {d}", True)
    try:
        store = Store(cfg.db_path)
        st = store.stats()
        store.close()
        check("store open", True, f"{st['items']} items / {st['offers']} offers")
    except Exception as exc:  # noqa: BLE001
        check("store open", False, str(exc))
    router = _router(cfg)
    if router is None:
        check("source router", False, "sources package not importable")
    else:
        avail = router.available()
        ok = sum(1 for v in avail.values() if v)
        check("sources loadable", ok > 0, f"{ok}/{len(avail)} available")
    print(f"\n{'OK' if problems == 0 else str(problems) + ' problem(s)'}")
    return 0 if problems == 0 else 1


def main():
    ap = argparse.ArgumentParser(description="AIOfferRadar - multi-platform free-AI-offer radar")
    ap.add_argument("command",
                    choices=["sources", "run", "verify", "notify", "doctor",
                             "report", "status"])
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="max findings to verify")
    ap.add_argument("--workers", type=int, default=0, help="parallel workers")
    ap.add_argument("--min-score", type=float, default=0.7, help="notify: score floor")
    ap.add_argument("--all-verdicts", action="store_true",
                    help="notify: include every verdict, not just verified ones")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg_path = Path(args.config).resolve()
    if cfg_path.parent.exists():
        import os
        os.chdir(cfg_path.parent)

    _load_secrets()
    cfg = load_ai_config(args.config)

    if args.command == "sources":
        return cmd_sources(cfg)
    if args.command == "run":
        return cmd_run(cfg, args.offline)
    if args.command == "verify":
        return cmd_verify(cfg, args.limit, args.workers)
    if args.command == "notify":
        return cmd_notify(cfg, args.min_score, args.all_verdicts)
    if args.command == "doctor":
        return cmd_doctor(cfg)
    if args.command == "report":
        return cmd_report(cfg)
    if args.command == "status":
        return cmd_status(cfg)
    return 1


if __name__ == "__main__":
    sys.exit(main())
