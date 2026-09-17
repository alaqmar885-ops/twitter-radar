"""Frontier-model free-access report.

Verifies a curated set of access routes live (HTTP + on-page free signals + card
policy + web corroboration) and merges them with frontier-related findings from
the radar store.
"""
from __future__ import annotations

import html as H
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\scrapper")
from airadar.models import Offer, Item           # noqa: E402
from airadar.store import Store                  # noqa: E402
from airadar.verify import FindingVerifier       # noqa: E402
from airadar.config import load_ai_config        # noqa: E402

DB = r"D:\scrapper\data\airadar.db"
OUT = Path(r"D:\scrapper\data\verified")

# (model family, access route, url, how it works)
FRONTIER_ROUTES = [
    ("GPT-5 class", "vendor pricing page", "https://openai.com/chatgpt/pricing/",
     "ChatGPT free tier vs Plus/Pro - free tier documented on the pricing page"),
    ("GPT-5 class", "model marketplace docs", "https://docs.github.com/en/github-models/about-github-models",
     "GitHub Models free usage quota for frontier models"),
    ("GPT-5 class", "free playground", "https://www.mcpjam.com/blog/frontier-models",
     "MCPJam exposes GPT-5 / Claude / Gemini / Grok in a free MCP playground"),
    ("Claude", "vendor pricing page", "https://www.anthropic.com/pricing",
     "Claude Free / Pro / Max tiers - free plan caps documented"),
    ("Gemini", "API free-tier docs", "https://ai.google.dev/gemini-api/docs/rate-limits",
     "Gemini API free tier limits (no card)"),
    ("Gemini", "vendor studio", "https://aistudio.google.com/",
     "Google AI Studio - free access to Gemini Flash models"),
    ("Grok", "vendor page", "https://x.ai/grok",
     "Grok access tiers incl. free access on X / grok.com"),
    ("DeepSeek", "open weights + API docs", "https://api-docs.deepseek.com/",
     "DeepSeek API docs; weights open-sourced (MIT)"),
    ("DeepSeek", "free API directory", "https://freellmapi.co/free-deepseek-api",
     "22 free DeepSeek-family models across providers, no card"),
    ("Qwen", "vendor chat app", "https://chat.qwen.ai/",
     "Qwen Chat app - free tier"),
    ("Kimi", "free model listing", "https://openrouter.ai/moonshotai/kimi-k2:free",
     "Kimi K2 served as a :free model on OpenRouter"),
    ("Llama / open", "free inference provider", "https://build.nvidia.com/",
     "NVIDIA NIM hosts open frontier models with free credits"),
    ("Any frontier", "arena", "https://lmarena.ai/",
     "LMArena - free side-by-side frontier model access"),
    ("Any frontier", "aggregator free router", "https://openrouter.ai/models?max_price=0",
     "OpenRouter model list filtered to free models"),
    ("Any frontier", "open weights self-host", "https://ollama.com/",
     "Run open-weight frontier models locally for free"),
    ("Any frontier", "open weights hub", "https://huggingface.co/models",
     "Download open-weight frontier models (DeepSeek/Qwen/Kimi/GLM/Llama)"),
    ("Any frontier", "free API directory", "https://www.free-model.com/providers/",
     "147+ verified free LLM APIs, live-tested, no credit card"),
]

FRONTIER_TERMS = ["gpt-5", "gpt5", "gpt-4", "o3", "o4", "claude", "opus", "sonnet",
                  "gemini", "grok", "deepseek", "qwen", "kimi", "glm", "llama",
                  "mistral", "nemotron", "frontier", "reasoning", "opus 4"]


def main() -> int:
    from run_radar import _load_secrets
    _load_secrets(r"D:\scrapper\secrets.env")
    import os
    from twitter_radar.enrich.youcom import YouComEnricher
    key = os.environ.get("YDC_API_KEY", "")
    enr = YouComEnricher(api_key=key, max_results=4) if key else None

    cfg = load_ai_config(r"D:\scrapper\config.yaml")
    ver = FindingVerifier(cfg, enricher=enr)

    print(f"=== verifying {len(FRONTIER_ROUTES)} frontier access routes "
          f"(web corroboration: {'on' if enr else 'off'}) ===")
    routes = []
    for i, (fam, route, url, note) in enumerate(FRONTIER_ROUTES, 1):
        o = Offer(title=f"{fam} via {route}", url=url, product=fam,
                  offer_type="free_tier", platforms=["route"])
        v = ver.verify(o)
        routes.append({"family": fam, "route": route, "url": url, "note": note,
                       "status": v["status"], "page_status": v.get("page_status"),
                       "signals": v.get("signals"), "no_cc_signals": v.get("no_cc_signals"),
                       "card_signals": v.get("card_signals"),
                       "web_hits": v.get("web_hits")})
        print(f"  [{i}/{len(FRONTIER_ROUTES)}] {v['status']:<16} {fam} / {route}")

    # radar findings that mention frontier models, with their verdicts
    store = Store(DB)
    vmap = store.verifications()
    store_offers = store.top_offers(limit=5000)
    store.close()
    hits = []
    for o in store_offers:
        blob = f"{o.title} {o.product} {o.url}".lower()
        if any(t in blob for t in FRONTIER_TERMS):
            rec = vmap.get(o.id, {})
            hits.append({"title": o.title, "url": o.url, "score": o.score,
                         "type": o.offer_type, "verdict": o.verdict,
                         "no_cc": bool(rec.get("no_cc_signals")),
                         "signals": (rec.get("signals") or [])[:5]})
    hits.sort(key=lambda h: (0 if h["verdict"] == "VERIFIED_NO_CC" else 1, -h["score"]))

    OUT.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    (OUT / f"frontier_{ts}.json").write_text(json.dumps(
        {"generated": ts, "routes": routes, "store_findings": hits[:80]},
        indent=2, ensure_ascii=False), encoding="utf-8")

    nocc = [r for r in routes if r["no_cc_signals"]]
    md = ["# Frontier model free access", "",
          f"Verified {len(routes)} access routes live. "
          f"{len(nocc)} show explicit no-card evidence. "
          f"{len(hits)} radar findings mention frontier models.", "",
          "| Model family | Route | Evidence | Card | URL |",
          "|---|---|---|---|---|"]
    for r in routes:
        card = "card required" if r["card_signals"] else (
            "no card" if r["no_cc_signals"] else "unstated")
        md.append(f"| {r['family']} | {r['route']} | {r['status']} "
                  f"(HTTP {r['page_status']}, web {r['web_hits']}) | {card} | <{r['url']}> |")
    md += ["", "## Radar findings mentioning frontier models", ""]
    for h in hits[:40]:
        md.append(f"- `{h['verdict'] or 'unverified'}` "
                  f"{'[no-card] ' if h['no_cc'] else ''}{h['title'][:110]} — <{h['url']}>")
    (OUT / f"frontier_{ts}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    def art(r):
        card = ("card required" if r["card_signals"]
                else ("no card" if r["no_cc_signals"] else "unstated"))
        cls = "g" if r["no_cc_signals"] else ("a" if not r["card_signals"] else "r")
        return (f'<article><div class="h"><span class="b {cls}">{H.escape(card)}</span>'
                f'<span class="s">{H.escape(r["family"])}</span>'
                f'<code>{H.escape(r["route"])}</code>'
                f'<span class="m2">{H.escape(r["status"])} · HTTP {r["page_status"]} · web {r["web_hits"]}</span>'
                f'</div><h3>{H.escape(r["note"])}</h3>'
                f'<p class="u"><a href="{H.escape(r["url"])}">{H.escape(r["url"])}</a></p>'
                f'<p class="m">on-page signals: {H.escape(", ".join((r["signals"] or [])[:5]) or "-")}'
                + (f' · no-card: {H.escape(", ".join((r["no_cc_signals"] or [])[:3]))}' if r["no_cc_signals"] else "")
                + (f' · card: {H.escape(", ".join((r["card_signals"] or [])[:2]))}' if r["card_signals"] else "")
                + "</p></article>")

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Frontier model free access</title><style>
:root{{--ink:#14181d;--mut:#6b7480;--line:#d8dde3;--paper:#fbfaf8;--acc:#8a1c1c;--ok:#1f6b45;--amb:#8a5a00}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-size:16px;line-height:1.6;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
.page{{max-width:900px;margin:0 auto;padding:52px 26px 90px}}
.k{{font-family:ui-monospace,Consolas,monospace;font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--mut)}}
h1{{font-family:"Iowan Old Style",Georgia,serif;font-size:2.2rem;font-weight:600;letter-spacing:-.015em;margin:10px 0 12px;line-height:1.15}}
h2{{font-family:"Iowan Old Style",Georgia,serif;font-size:1.26rem;margin:36px 0 10px;padding-bottom:7px;border-bottom:1px solid var(--ink)}}
h3{{font-size:.98rem;margin:8px 0 4px;font-weight:600}}
article{{padding:14px 0;border-bottom:1px solid var(--line)}}
.h{{display:flex;gap:9px;align-items:center;flex-wrap:wrap;font-size:.78rem}}
.b{{font-weight:700;font-size:.64rem;letter-spacing:.06em;padding:2px 7px;border-radius:3px;border:1px solid currentColor}}
.g{{color:var(--ok)}}.a{{color:var(--amb)}}.r{{color:var(--acc)}}
.s{{font-weight:700;color:var(--acc)}}.m2{{color:var(--mut);font-size:.74rem}}
code{{font-family:ui-monospace,Consolas,monospace;font-size:.8em;background:#eef1f4;border:1px solid var(--line);border-radius:3px;padding:.06em .3em}}
.u a{{color:var(--acc);text-decoration:none;font-size:.85rem}}
.m{{color:var(--mut);font-size:.8rem;margin:4px 0}}.lede{{color:#3d4650;max-width:66ch}}
table{{width:100%;border-collapse:collapse;font-size:.88rem;margin:10px 0}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-family:ui-monospace,Consolas,monospace;font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);border-bottom:1px solid var(--ink)}}
footer{{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);font-family:ui-monospace,Consolas,monospace;font-size:.7rem;color:var(--mut)}}
</style></head><body><div class="page">
<div class="k">AIOfferRadar · frontier access mission · {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(ts))}</div>
<h1>Frontier models: free access routes</h1>
<p class="lede">Five route types matter: the vendor's own free tier, free API/free-tier quotas,
free playgrounds &amp; arenas, aggregators serving <code>:free</code> model pools, and open weights you
self-host. Each route below was fetched live and its page scanned for free-offer signals and card policy.</p>
<h2>Access routes ({len(routes)})</h2>
{''.join(art(r) for r in routes)}
<h2>Radar findings mentioning frontier models ({len(hits)})</h2>
<table><thead><tr><th>Verdict</th><th>Finding</th><th>Card</th><th>URL</th></tr></thead><tbody>
{''.join(f'<tr><td>{H.escape(h["verdict"] or "unverified")}</td><td>{H.escape(h["title"][:80])}</td><td>{"no card" if h["no_cc"] else "-"}</td><td><a href="{H.escape(h["url"] or "")}">{H.escape((h["url"] or "")[:60])}</a></td></tr>' for h in hits[:60])}
</tbody></table>
<footer>Evidence = HTTP status + on-page free signals + explicit card policy + web corroboration count.</footer>
</div></body></html>"""
    (OUT / f"frontier_{ts}.html").write_text(doc, encoding="utf-8")

    print(f"\nno-card routes: {len(nocc)}/{len(routes)} | radar frontier findings: {len(hits)}")
    print("report ->", OUT / f"frontier_{ts}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
