"""Render the no-credit-card free-offer shortlist from the verified store."""
from __future__ import annotations

import html as H
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\scrapper")
from airadar.store import Store  # noqa: E402

DB = r"D:\scrapper\data\airadar.db"
OUT = Path(r"D:\scrapper\data\verified")


def main() -> int:
    store = Store(DB)
    ver = store.verifications()
    offers = store.top_offers(limit=5000)
    store.close()

    # Precision rules: a finding only qualifies for the no-card list when the
    # destination page shows BOTH a specific free offer signal AND an explicit
    # no-card phrase. A page that merely lacks the words "credit card" is not
    # evidence; a page that says "no credit card" AND "credit card required"
    # (free tier + paid tier) still qualifies for its free tier.
    STRONG_FREE = {"free tier", "free plan", "free trial", "start free", "try free",
                   "free credits", "free forever", "always free", "no credit card",
                   "free access"}
    STRONG_NOCC = {"no credit card", "no credit-card", "no card required",
                   "no card needed", "without a credit card", "without credit card",
                   "no payment method", "no payment required", "no cc required"}

    keep: dict = {}
    rej: dict = {}
    for o in offers:
        rec = ver.get(o.id)
        if not rec:
            continue
        free = set(rec.get("signals") or [])
        nocc = set(rec.get("no_cc_signals") or [])
        card = rec.get("card_signals") or []
        strong_free = free & STRONG_FREE
        strong_nocc = nocc & STRONG_NOCC
        url_key = (o.url or o.title or o.id).strip().lower().rstrip("/")
        if strong_free and strong_nocc:
            prev = keep.get(url_key)
            if prev is None or o.score > prev[0].score:
                keep[url_key] = (o, rec, "NO_CARD")
        elif card:
            rej.setdefault(url_key, (o, rec, "CARD_REQUIRED"))
    rows = list(keep.values()) + list(rej.values())
    rows.sort(key=lambda r: (0 if r[2] == "NO_CARD" else 1, -r[0].score))

    nocard = [r for r in rows if r[2] == "NO_CARD"]
    cardreq = [r for r in rows if r[2] == "CARD_REQUIRED"]

    OUT.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    (OUT / f"no_cc_{ts}.json").write_text(json.dumps({
        "generated": ts, "no_card": len(nocard), "card_required": len(cardreq),
        "findings": [{"verdict": k, "title": o.title, "url": o.url, "score": o.score,
                      "type": o.offer_type, "value": o.value, "promo_code": o.promo_code,
                      "platforms": o.platforms, "page_status": rec.get("page_status"),
                      "no_cc_signals": rec.get("no_cc_signals"),
                      "card_signals": rec.get("card_signals"),
                      "signals": rec.get("signals")} for o, rec, k in rows],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# Free AI offers that need NO credit card", "",
          f"{len(nocard)} findings carry explicit no-card evidence; "
          f"{len(cardreq)} were rejected for requiring a card.", "",
          "## No card required", ""]
    for o, rec, _ in nocard:
        md.append(f"### {o.title}")
        meta = [f"score {o.score:.0%}", f"`{o.offer_type}`"]
        if o.value:
            meta.append(f"**{o.value}**")
        if o.promo_code:
            meta.append(f"code `{o.promo_code}`")
        md.append("- " + " - ".join(meta))
        md.append(f"- <{o.url}>  (HTTP {rec.get('page_status')}; "
                  f"no-card: {', '.join((rec.get('no_cc_signals') or [])[:3]) or '—'})")
        md.append("")
    md += ["## Rejected - page requires a card", ""]
    for o, rec, _ in cardreq:
        md.append(f"- {o.title[:110]} — <{o.url}> "
                  f"({', '.join((rec.get('card_signals') or [])[:2])})")
    (OUT / f"no_cc_{ts}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    def art(r):
        o, rec, k = r
        return (f'<article><div class="h"><span class="b g">NO CARD</span>'
                f'<span class="s">{o.score:.0%}</span>'
                f'<code>{H.escape(o.offer_type)}</code>'
                + (f'<b>{H.escape(o.value)}</b>' if o.value else "")
                + (f'<span class="c">code {H.escape(o.promo_code)}</span>' if o.promo_code else "")
                + "</div>"
                + f'<h3>{H.escape(o.title)}</h3>'
                + (f'<p class="u"><a href="{H.escape(o.url or "")}">{H.escape(o.url or "")}</a></p>' if o.url else "")
                + f'<p class="m">HTTP {rec.get("page_status")} · no-card evidence: '
                  f'{H.escape(", ".join((rec.get("no_cc_signals") or [])[:4]) or "—")} · '
                  f'free signals: {H.escape(", ".join((rec.get("signals") or [])[:5]) or "—")} · '
                  f'platforms: {H.escape(", ".join(o.platforms))}</p></article>')

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Free AI offers - no credit card</title><style>
:root{{--ink:#14181d;--mut:#6b7480;--line:#d8dde3;--paper:#fbfaf8;--acc:#8a1c1c;--ok:#1f6b45}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-size:16px;
line-height:1.6;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
.page{{max-width:900px;margin:0 auto;padding:52px 26px 90px}}
.k{{font-family:ui-monospace,Consolas,monospace;font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--mut)}}
h1{{font-family:"Iowan Old Style",Georgia,serif;font-size:2.2rem;font-weight:600;letter-spacing:-.015em;margin:10px 0 12px;line-height:1.15}}
h2{{font-family:"Iowan Old Style",Georgia,serif;font-size:1.26rem;margin:36px 0 10px;padding-bottom:7px;border-bottom:1px solid var(--ink)}}
h3{{font-size:1rem;margin:8px 0 4px;font-weight:600}}
article{{padding:14px 0;border-bottom:1px solid var(--line)}}
.h{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:.78rem}}
.b{{font-weight:700;font-size:.66rem;letter-spacing:.06em;padding:2px 7px;border-radius:3px;border:1px solid currentColor}}
.g{{color:var(--ok)}}.r{{color:var(--acc)}}.s{{font-weight:700;color:var(--acc)}}
code{{font-family:ui-monospace,Consolas,monospace;font-size:.8em;background:#eef1f4;border:1px solid var(--line);border-radius:3px;padding:.06em .3em}}
.c{{color:var(--acc);font-weight:600}}.u a{{color:var(--acc);text-decoration:none;font-size:.85rem}}
.m{{color:var(--mut);font-size:.8rem;margin:4px 0}}.lede{{color:#3d4650;max-width:66ch}}
table{{width:100%;border-collapse:collapse;font-size:.9rem;margin:10px 0}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}}
th{{font-family:ui-monospace,Consolas,monospace;font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);border-bottom:1px solid var(--ink)}}
footer{{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);font-family:ui-monospace,Consolas,monospace;font-size:.7rem;color:var(--mut)}}
</style></head><body><div class="page">
<div class="k">AIOfferRadar · no-credit-card mission · {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(ts))}</div>
<h1>Free AI offers that need no credit card</h1>
<p class="lede">A finding qualifies only if its destination page shows a specific free
signal (free tier / free trial / free credits …) <b>and</b> explicit no-card evidence
("no credit card", "no card required", "no payment method"). Pages that demand a card
are listed separately as rejected. <b>{len(nocard)}</b> qualified, <b>{len(cardreq)}</b> rejected.</p>
<h2>No card required ({len(nocard)})</h2>
{''.join(art(r) for r in nocard) or '<p>None.</p>'}
<h2>Rejected - card required ({len(cardreq)})</h2>
<table><thead><tr><th>Finding</th><th>Card evidence</th></tr></thead><tbody>
{''.join(f'<tr><td>{H.escape(o.title[:80])}</td><td>{H.escape(", ".join((rec.get("card_signals") or [])[:2]))}</td></tr>' for o, rec, k in cardreq)}
</tbody></table>
<footer>Generated by AIOfferRadar - evidence = HTTP status + on-page free signals + explicit card policy text.</footer>
</div></body></html>"""
    (OUT / f"no_cc_{ts}.html").write_text(doc, encoding="utf-8")

    print(f"no-card: {len(nocard)}  card-required: {len(cardreq)}")
    print("report ->", OUT / f"no_cc_{ts}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
