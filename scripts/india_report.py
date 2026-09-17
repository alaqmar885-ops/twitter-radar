"""India / UPI report: which free AI offers an Indian user can actually reach and pay for."""
from __future__ import annotations

import html as H
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\scrapper")
from airadar.config import load_ai_config      # noqa: E402
from airadar.models import Offer               # noqa: E402
from airadar.store import Store                # noqa: E402
from airadar.verify import FindingVerifier     # noqa: E402

DB = r"D:\scrapper\data\airadar.db"
OUT = Path(r"D:\scrapper\data\verified")

# (what, why it matters for India, url)
INDIA_ROUTES = [
    ("Jio x Google AI Pro (free 18 months)",
     "Reliance Jio offers 18 months of Google AI Pro free to Jio users",
     "https://www.jio.com/google-gemini-offer/"),
    ("Airtel x Perplexity Pro",
     "Airtel bundles Perplexity Pro free for its users (worth ~Rs 17,000)",
     "https://www.airtel.in/"),
    ("Jio free Google AI Pro - explainer",
     "Reporting on the 18-month free Google AI Pro offer for Jio users",
     "https://www.timesofai.com/news/free-google-ai-pro-plan-jio/"),
    ("Jio Gemini offer - coverage",
     "Second source on the Jio/Google AI Pro offer",
     "https://technosports.co.in/jio-offers-google-ai-pro-free-for-18-months/"),
    ("AI tools that work in India",
     "India-tested AI tool roundup with local pricing",
     "https://aiinsider.in/blog/15-ai-tools-that-work-in-india-2026/"),
    ("NPCI Unified Agent Protocol",
     "UPI is being extended so AI agents can make UPI payments",
     "https://www.npci.org.in/what-we-do/upi/product-overview"),
    ("Jio AI bundles", "Indian telco bundles that include premium AI", "https://www.jio.com/"),
    ("Airtel AI bundles", "Airtel frequently bundles Perplexity/other AI", "https://www.airtel.in/"),
    ("Google AI Pro / One plans", "Google One AI plans have India pricing and Play billing", "https://one.google.com/about/plans"),
    ("Perplexity Pro", "Perplexity has run India-specific free/bundled Pro offers", "https://www.perplexity.ai/pro"),
    ("Gemini app", "Gemini free tier available in India", "https://gemini.google.com/"),
    ("Razorpay UPI gateway", "Proof UPI is available as a payment rail for Indian merchants", "https://razorpay.com/payment-gateway/upi/"),
    ("NPCI UPI overview", "Official UPI specification/description", "https://www.npci.org.in/what-we-do/upi/product-overview"),
    ("Google Play payment methods", "Play billing supports UPI in India (in-app subscriptions)", "https://support.google.com/googleplay/answer/2651410"),
    ("ChatGPT pricing", "OpenAI billing is card-based in most regions", "https://openai.com/chatgpt/pricing/"),
    ("Claude pricing", "Anthropic billing is card-based; check Indian card support", "https://www.anthropic.com/pricing"),
    ("Free model provider directory", "Free LLM APIs usable from India without a card", "https://www.free-model.com/providers/"),
    ("Ollama (self-host)", "No payment rail needed at all", "https://ollama.com/"),
]


def main() -> int:
    from run_radar import _load_secrets
    _load_secrets(r"D:\scrapper\secrets.env")
    import os
    from twitter_radar.enrich.youcom import YouComEnricher
    key = os.environ["YDC_API_KEY"] if "YDC_API_KEY" in os.environ else ""
    enr = YouComEnricher(api_key=key, max_results=4) if key else None
    cfg = load_ai_config(r"D:\scrapper\config.yaml")
    ver = FindingVerifier(cfg, enricher=enr)

    print(f"=== verifying {len(INDIA_ROUTES)} India routes ===")
    routes = []
    for i, (what, why, url) in enumerate(INDIA_ROUTES, 1):
        o = Offer(title=what, url=url, product=what, offer_type="free_tier", platforms=["route"])
        v = ver.verify(o)
        routes.append({"what": what, "why": why, "url": url, "status": v["status"],
                       "page_status": v.get("page_status"),
                       "india_signals": v.get("india_signals"),
                       "upi_signals": v.get("upi_signals"),
                       "no_cc_signals": v.get("no_cc_signals"),
                       "web_hits": v.get("web_hits")})
        print(f"  [{i}/{len(INDIA_ROUTES)}] {v['status']:<16} {what}")

    store = Store(DB)
    vmap = store.verifications()
    offers = store.top_offers(limit=5000)
    store.close()

    india_hits, upi_hits = [], []
    for o in offers:
        rec = vmap.get(o.id) or {}
        if rec.get("upi_signals"):
            upi_hits.append((o, rec))
        elif rec.get("india_signals"):
            india_hits.append((o, rec))
    india_hits.sort(key=lambda t: -t[0].score)
    upi_hits.sort(key=lambda t: -t[0].score)

    OUT.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    payload = {"generated": ts, "routes": routes,
               "upi_findings": [{"title": o.title, "url": o.url, "score": o.score,
                                 "upi": rec.get("upi_signals"),
                                 "india": rec.get("india_signals")} for o, rec in upi_hits],
               "india_findings": [{"title": o.title, "url": o.url, "score": o.score,
                                   "india": rec.get("india_signals")} for o, rec in india_hits]}
    (OUT / f"india_{ts}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                          encoding="utf-8")

    md = ["# India / UPI: free AI offers you can actually reach", "",
          f"Verified {len(routes)} India-relevant routes live. "
          f"{len(upi_hits)} stored findings mention a UPI rail; "
          f"{len(india_hits)} mention India.", "",
          "| Route | Evidence | India signals | UPI signals | URL |", "|---|---|---|---|---|"]
    for r in routes:
        md.append(f"| {r['what']} | {r['status']} (HTTP {r['page_status']}) | "
                  f"{', '.join((r['india_signals'] or [])[:4]) or '-'} | "
                  f"{', '.join((r['upi_signals'] or [])[:3]) or '-'} | <{r['url']}> |")
    md += ["", "## Findings mentioning UPI / India", ""]
    for o, rec in upi_hits + india_hits:
        md.append(f"- [{o.score:.0%}] {o.title[:110]} — <{o.url}> "
                  f"(india: {', '.join((rec.get('india_signals') or [])[:3]) or '-'}; "
                  f"upi: {', '.join((rec.get('upi_signals') or [])[:2]) or '-'})")
    (OUT / f"india_{ts}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    def art(r):
        ok = bool(r["upi_signals"])
        cls = "g" if ok else ("a" if r["india_signals"] else "r")
        label = "UPI" if ok else ("India" if r["india_signals"] else "no India signal")
        return (f'<article><div class="h"><span class="b {cls}">{H.escape(label)}</span>'
                f'<span class="s">{H.escape(r["what"])}</span>'
                f'<span class="m2">{H.escape(r["status"])} · HTTP {r["page_status"]}</span></div>'
                f'<h3>{H.escape(r["why"])}</h3>'
                f'<p class="u"><a href="{H.escape(r["url"])}">{H.escape(r["url"])}</a></p>'
                f'<p class="m">india: {H.escape(", ".join((r["india_signals"] or [])[:5]) or "-")}'
                f' · upi: {H.escape(", ".join((r["upi_signals"] or [])[:4]) or "-")}</p></article>')

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>India / UPI free AI offers</title><style>
:root{{--ink:#14181d;--mut:#6b7480;--line:#d8dde3;--paper:#fbfaf8;--acc:#8a1c1c;--ok:#1f6b45;--amb:#8a5a00}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-size:16px;line-height:1.6;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
.page{{max-width:900px;margin:0 auto;padding:52px 26px 90px}}
.k{{font-family:ui-monospace,Consolas,monospace;font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--mut)}}
h1{{font-family:"Iowan Old Style",Georgia,serif;font-size:2.2rem;font-weight:600;letter-spacing:-.015em;margin:10px 0 12px;line-height:1.15}}
h2{{font-family:"Iowan Old Style",Georgia,serif;font-size:1.26rem;margin:36px 0 10px;padding-bottom:7px;border-bottom:1px solid var(--ink)}}
h3{{font-size:.96rem;margin:8px 0 4px;font-weight:600}}
article{{padding:14px 0;border-bottom:1px solid var(--line)}}
.h{{display:flex;gap:9px;align-items:center;flex-wrap:wrap;font-size:.78rem}}
.b{{font-weight:700;font-size:.64rem;letter-spacing:.06em;padding:2px 7px;border-radius:3px;border:1px solid currentColor}}
.g{{color:var(--ok)}}.a{{color:var(--amb)}}.r{{color:var(--acc)}}
.s{{font-weight:700;color:var(--acc)}}.m2{{color:var(--mut);font-size:.74rem}}
.u a{{color:var(--acc);text-decoration:none;font-size:.85rem}}
.m{{color:var(--mut);font-size:.8rem;margin:4px 0}}.lede{{color:#3d4650;max-width:66ch}}
table{{width:100%;border-collapse:collapse;font-size:.86rem;margin:10px 0}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-family:ui-monospace,Consolas,monospace;font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);border-bottom:1px solid var(--ink)}}
footer{{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);font-family:ui-monospace,Consolas,monospace;font-size:.7rem;color:var(--mut)}}
</style></head><body><div class="page">
<div class="k">AIOfferRadar · India / UPI mission · {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(ts))}</div>
<h1>Free AI offers an Indian user can actually reach</h1>
<p class="lede">Two filters matter: can you <b>get</b> the offer from India, and can you <b>pay</b> for an
upgrade without a foreign card? Each route below was fetched live and scanned for India and UPI signals.</p>
<h2>India routes ({len(routes)})</h2>
{''.join(art(r) for r in routes)}
<h2>Stored findings mentioning UPI ({len(upi_hits)})</h2>
<table><thead><tr><th>Score</th><th>Finding</th><th>UPI evidence</th></tr></thead><tbody>
{''.join(f'<tr><td>{o.score:.0%}</td><td>{H.escape(o.title[:80])}</td><td>{H.escape(", ".join((rec.get("upi_signals") or [])[:3]))}</td></tr>' for o, rec in upi_hits[:40])}
</tbody></table>
<h2>Stored findings mentioning India ({len(india_hits)})</h2>
<table><thead><tr><th>Score</th><th>Finding</th><th>India evidence</th></tr></thead><tbody>
{''.join(f'<tr><td>{o.score:.0%}</td><td>{H.escape(o.title[:80])}</td><td>{H.escape(", ".join((rec.get("india_signals") or [])[:3]))}</td></tr>' for o, rec in india_hits[:40])}
</tbody></table>
<footer>Evidence = HTTP status + on-page occurrence of India/UPI terms. Term presence is a signal, not proof of acceptance.</footer>
</div></body></html>"""
    (OUT / f"india_{ts}.html").write_text(doc, encoding="utf-8")
    print(f"\nupi findings: {len(upi_hits)} | india findings: {len(india_hits)}")
    print("report ->", OUT / f"india_{ts}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
