"""Provider discovery: find free AI providers the radar was never told about.

Harvests candidate provider domains from (a) a seed list of known-free providers,
(b) the aggregator/directory pages already configured, (c) the store's own findings
and (d) a You.com MCP research sweep. Each candidate is then probed live for
free-tier / no-card / UPI / India evidence and ranked.

Writes data/discovered/providers_<ts>.{json,md,html} plus a config snippet
(data/discovered/suggested_config.txt) of the strongest providers to watch.
"""
from __future__ import annotations

import html as H
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, r"D:\scrapper")
from airadar.config import load_ai_config      # noqa: E402
from airadar.models import Offer               # noqa: E402
from airadar.store import Store                # noqa: E402
from airadar.verify import FindingVerifier     # noqa: E402

OUT = Path(r"D:\scrapper\data\discovered")
DB = r"D:\scrapper\data\airadar.db"

# Providers a naive keyword sweep misses. AgentRouter was the one that exposed
# this whole gap: an OpenRouter-like gateway handing out free credits.
SEED_PROVIDERS = [
    "agentrouter.org", "openrouter.ai", "aimlapi.com", "bazaarlink.ai",
    "freellmapi.co", "itsfree.ai", "free-model.com", "groq.com", "cerebras.ai",
    "together.ai", "deepinfra.com", "novita.ai", "hyperbolic.xyz", "kluster.ai",
    "featherless.ai", "glama.ai", "pollinations.ai", "puter.com", "chutes.ai",
    "nvidia.com", "cloudflare.com", "ollama.com", "huggingface.co",
    "fireworks.ai", "perplexity.ai", "mistral.ai", "deepseek.com",
    "qwen.ai", "moonshot.ai", "z.ai", "siliconflow.com", "modelscope.cn",
]

# Domains that are publishers/aggregators, not providers - never propose them.
BLOCK = ("reddit.com", "youtube.com", "youtu.be", "medium.com", "facebook.com",
         "x.com", "twitter.com", "linkedin.com", "gist.github.com", "news.ycombinator.com",
         "wikipedia.org", "producthunt.com", "stackoverflow.com", "quora.com",
         "microsoft.com", "google.com", "apple.com", "amazon.com", "w3.org")

RESEARCH_QUERIES = [
    "free AI gateway provider free credits no credit card 2026",
    "OpenRouter alternative free API credits",
    "free LLM API providers list 2026 gateway",
    "AI coding agent free provider Claude Code free API",
    "free claude code api provider gateway 2026",
]


def domain_of(url: str) -> str:
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


def harvest_from_pages(cfg) -> set:
    """Pull candidate domains out of the aggregator pages we already watch."""
    import httpx
    from airadar.sources.base import BROWSER_UA
    found = set()
    link = re.compile(r'href="(https?://[^"\\s>]+)"', re.I)
    for page in list(getattr(cfg, "html_watch", []) or []) + list(getattr(cfg, "rss_feeds", []) or []):
        try:
            r = httpx.get(page, headers={"User-Agent": BROWSER_UA}, timeout=20, follow_redirects=True)
            if r.status_code != 200:
                continue
            for m in link.finditer(r.text):
                d = domain_of(m.group(1))
                if d and d not in BLOCK:
                    found.add(d)
            time.sleep(0.5)
        except Exception:
            continue
    return found


def harvest_from_store() -> set:
    found = set()
    try:
        store = Store(DB)
        for o in store.top_offers(limit=2000):
            d = domain_of(o.url or "")
            if d and d not in BLOCK:
                found.add(d)
        store.close()
    except Exception:
        pass
    return found


def harvest_from_research(enricher) -> set:
    found = set()
    if enricher is None:
        return found
    for q in RESEARCH_QUERIES:
        try:
            for r in enricher.search(q, max_results=8) or []:
                d = domain_of(r.get("url", ""))
                if d and d not in BLOCK:
                    found.add(d)
        except Exception:
            continue
        time.sleep(1.0)
    return found


def probe(ver: FindingVerifier, dom: str) -> dict:
    """Probe a provider: root first, then pricing/docs if the root is thin."""
    best = None
    # Some providers (e.g. agentrouter.org) serve a JS shell at "/" and keep all
    # real content under /docs - probe that as a fallback so they are not scored
    # as NOT_AN_OFFER purely because the root is an app shell.
    paths = ["", "/pricing"]
    for path in paths:
        url = f"https://{dom}{path}"
        o = Offer(title=dom, url=url, product=dom, offer_type="free_tier", platforms=["probe"])
        v = ver.verify(o)
        rec = {"domain": dom, "url": url, "status": v.get("status"),
               "page_status": v.get("page_status"), "signals": v.get("signals"),
               "no_cc_signals": v.get("no_cc_signals"), "card_signals": v.get("card_signals"),
               "upi_signals": v.get("upi_signals"), "india_signals": v.get("india_signals"),
               "page_title": v.get("page_title"), "web_hits": v.get("web_hits")}
        if best is None:
            best = rec
        else:
            # prefer the probe with the strongest evidence
            score = lambda r: (len(r["signals"] or []) + 2 * len(r["no_cc_signals"] or []))  # noqa: E731
            if score(rec) > score(best):
                best = rec
        if best and best.get("no_cc_signals") and len(best.get("signals") or []) >= 2:
            break
    if not (best or {}).get("signals"):
        doc = f"https://{dom}/docs"
        o = Offer(title=dom, url=doc, product=dom, offer_type="free_tier", platforms=["probe"])
        v = ver.verify(o)
        rec = {"domain": dom, "url": doc, "status": v.get("status"),
               "page_status": v.get("page_status"), "signals": v.get("signals"),
               "no_cc_signals": v.get("no_cc_signals"), "card_signals": v.get("card_signals"),
               "upi_signals": v.get("upi_signals"), "india_signals": v.get("india_signals"),
               "page_title": v.get("page_title"), "web_hits": v.get("web_hits")}
        if len(rec.get("signals") or []) > len((best or {}).get("signals") or []):
            best = rec
    return best or {"domain": dom, "status": "SKIPPED"}


def main() -> int:
    from run_radar import _load_secrets
    _load_secrets(r"D:\scrapper\secrets.env")
    import os
    key = os.environ["YDC_API_KEY"] if "YDC_API_KEY" in os.environ else ""
    from twitter_radar.enrich.youcom import YouComEnricher
    enr = YouComEnricher(api_key=key, max_results=8) if key else None

    cfg = load_ai_config(r"D:\scrapper\config.yaml")
    ver = FindingVerifier(cfg, enricher=None)      # no web search during probing (cost control)

    print("=== harvesting provider candidates ===")
    cands = set(SEED_PROVIDERS)
    for label, got in (("pages", harvest_from_pages(cfg)),
                       ("store", harvest_from_store()),
                       ("research", harvest_from_research(enr))):
        print(f"  {label:9s} -> {len(got)} domains")
        cands |= got
    cands = {d for d in cands if d and d not in BLOCK and "." in d}
    # Seeds first (they are the providers we know matter), then the rest, capped:
    # a full sweep of every harvested domain is slow and mostly noise.
    ordered = [d for d in SEED_PROVIDERS if d in cands]
    ordered += sorted(cands - set(ordered))
    cap = int(os.environ["DISCOVER_MAX"] if "DISCOVER_MAX" in os.environ else 60)
    ordered = ordered[:cap]
    print(f"  unique candidates: {len(cands)} | probing (capped): {len(ordered)}")

    print(f"=== probing {len(cands)} providers (live) ===")
    results = []
    for i, dom in enumerate(ordered, 1):
        rec = probe(ver, dom)
        results.append(rec)
        print(f"  [{i}/{len(cands)}] {rec.get('status','?'):<16} {dom}")

    def rank(r):
        strong = len(r.get("no_cc_signals") or [])
        sig = len(r.get("signals") or [])
        return (-(strong * 2 + sig), r.get("domain", ""))

    results.sort(key=rank)
    good = [r for r in results if (r.get("signals") or []) and not (r.get("card_signals") or [])]
    noc = [r for r in good if r.get("no_cc_signals")]

    OUT.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    (OUT / f"providers_{ts}.json").write_text(
        json.dumps({"generated": ts, "candidates": len(cands), "probed": len(ordered),
                    "providers": results}, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# Discovered free AI providers", "",
          f"Harvested {len(cands)} candidate domains ({len(ordered)} probed) from a seed list, the aggregator pages, "
          f"the store and a research sweep; {len(good)} show free-tier evidence without card "
          f"requirements, {len(noc)} of them explicitly no-card.", "",
          "| Provider | Evidence | Card | UPI/India | URL |", "|---|---|---|---|---|"]
    for r in good[:60]:
        card = "card" if r.get("card_signals") else ("no-card" if r.get("no_cc_signals") else "unstated")
        extra = ", ".join((r.get("upi_signals") or [])[:2] + (r.get("india_signals") or [])[:2]) or "-"
        md.append(f"| {r['domain']} | {r.get('status')} ({(r.get('signals') or [])[:3]}) | "
                  f"{card} | {extra} | <{r['url']}> |")
    (OUT / f"providers_{ts}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    snippet = ["  # discovered free providers - paste into airadar.html_watch",
               "  html_watch:"]
    for r in noc[:25]:
        snippet.append(f"    - {r['url']}")
    (OUT / "suggested_config.txt").write_text("\n".join(snippet) + "\n", encoding="utf-8")

    rows = "".join(
        f'<tr><td>{H.escape(r["domain"])}</td><td>{H.escape(str(r.get("status")))}</td>'
        f'<td>{H.escape(", ".join((r.get("signals") or [])[:4]))}</td>'
        f'<td>{"no-card" if r.get("no_cc_signals") else ("card" if r.get("card_signals") else "-")}</td>'
        f'<td><a href="{H.escape(r["url"])}">{H.escape(r["url"][:48])}</a></td></tr>'
        for r in results[:120])
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Discovered free AI providers</title><style>
:root{{--ink:#14181d;--mut:#6b7480;--line:#d8dde3;--paper:#fbfaf8;--acc:#8a1c1c;--ok:#1f6b45}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-size:15px;line-height:1.55;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.page{{max-width:980px;margin:0 auto;padding:50px 26px 90px}}
.k{{font-family:ui-monospace,Consolas,monospace;font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--mut)}}
h1{{font-family:"Iowan Old Style",Georgia,serif;font-size:2.1rem;font-weight:600;margin:10px 0 12px;line-height:1.15}}
p{{color:#3d4650;max-width:70ch}}
table{{width:100%;border-collapse:collapse;font-size:.84rem;margin-top:14px}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-family:ui-monospace,Consolas,monospace;font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;
color:var(--mut);border-bottom:1px solid var(--ink)}}
a{{color:var(--acc);text-decoration:none}}
footer{{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);font-family:ui-monospace,Consolas,monospace;
font-size:.7rem;color:var(--mut)}}
</style></head><body><div class="page">
<div class="k">AIOfferRadar · provider discovery · {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(ts))}</div>
<h1>Providers the radar was never told about</h1>
<p>Candidate domains are harvested from a seed list, the aggregator pages, the existing
findings and a research sweep, then each is probed live. <b>{len(ordered)}</b> candidates probed (of {len(cands)} harvested),
<b>{len(good)}</b> with free-tier evidence and no card requirement, <b>{len(noc)}</b> explicitly no-card.</p>
<table><thead><tr><th>Provider</th><th>Status</th><th>Free signals</th><th>Card</th><th>URL</th></tr></thead>
<tbody>{rows}</tbody></table>
<footer>Evidence = HTTP status + on-page free/card/UPI terms. A signal is a lead, not proof.</footer>
</div></body></html>"""
    (OUT / f"providers_{ts}.html").write_text(doc, encoding="utf-8")

    print(f"\\nfree (no card): {len(noc)} / free: {len(good)} / candidates: {len(cands)}")
    print("report ->", OUT / f"providers_{ts}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
