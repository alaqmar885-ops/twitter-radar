"""Re-score verification verdicts with stricter evidence rules and rebuild the report."""
from __future__ import annotations

import html as H
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\scrapper")
from airadar.store import Store  # noqa: E402

STRONG = {"free tier", "free plan", "free trial", "start free", "try free",
          "free credits", "free forever", "always free", "no credit card",
          "free access"}
MEDIUM = {"pricing", "trial", "discount", "credits"}
WEAK = {"free", "off"}


def verdict(rec: dict) -> str:
    sig = set(rec.get("signals") or [])
    if not sig:
        return "NOT_AN_OFFER"
    strong = sig & STRONG
    medium = sig & MEDIUM
    if strong:
        return "VERIFIED"
    if len(medium) >= 2:
        return "PARTIAL"
    return "WEAK"


def main() -> int:
    store = Store(r"D:\scrapper\data\airadar.db")
    ver = store.verifications()
    offers = store.top_offers(limit=5000)
    counts: dict = {}
    rows = []
    for o in offers:
        rec = ver.get(o.id)
        if not rec:
            continue
        v = verdict(rec)
        counts[v] = counts.get(v, 0) + 1
        store.set_verdict(o.id, v)
        rows.append((o, rec, v))
    store.close()

    order = {"VERIFIED": 0, "PARTIAL": 1, "WEAK": 2, "NOT_AN_OFFER": 3,
             "UNREACHABLE": 4, "NO_URL": 5}
    rows.sort(key=lambda r: (order.get(r[2], 9), -r[0].score))

    out = Path(r"D:\scrapper\data\verified")
    out.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    keep = [r for r in rows if r[2] in ("VERIFIED", "PARTIAL")]
    drop = [r for r in rows if r[2] not in ("VERIFIED", "PARTIAL")]

    payload = {"generated": ts, "counts": counts,
               "findings": [{"verdict": v, "title": o.title, "url": o.url,
                             "score": o.score, "type": o.offer_type, "value": o.value,
                             "promo_code": o.promo_code, "platforms": o.platforms,
                             "page_status": rec.get("page_status"),
                             "page_title": rec.get("page_title", ""),
                             "signals": rec.get("signals"), "web_hits": rec.get("web_hits")}
                            for o, rec, v in rows]}
    (out / f"verified_final_{ts}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md = ["# Verified findings (strict evidence rules)", "",
          f"Checked {len(rows)} findings. VERIFIED requires a specific on-page signal "
          "(free tier / free trial / free credits / no credit card ...) - the bare word "
          "\"free\" is not enough.", "", "| Verdict | Count |", "|---|---|"]
    for k, n in sorted(counts.items(), key=lambda x: order.get(x[0], 9)):
        md.append(f"| {k} | {n} |")
    md += ["", f"## Confirmed & partial ({len(keep)})", ""]
    for o, rec, v in keep:
        md.append(f"### [{v}] {o.title}")
        md.append(f"- score {o.score:.0%} · `{o.offer_type}`"
                  + (f" · **{o.value}**" if o.value else "")
                  + (f" · code `{o.promo_code}`" if o.promo_code else ""))
        md.append(f"- <{o.url}> — HTTP {rec.get('page_status')}, signals: "
                  f"{', '.join((rec.get('signals') or [])[:6]) or '—'}")
        md.append("")
    md += ["", f"## Not confirmed ({len(drop)})", ""]
    for o, rec, v in drop:
        md.append(f"- `{v}` {o.title[:110]} — <{o.url}>")
    (out / f"verified_final_{ts}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    def art(r):
        o, rec, v = r
        cls = {"VERIFIED": "g", "PARTIAL": "a"}.get(v, "r")
        return (f'<article><div class="h"><span class="b {cls}">{v}</span>'
                f'<span class="s">{o.score:.0%}</span><code>{H.escape(o.offer_type)}</code>'
                + (f'<b>{H.escape(o.value)}</b>' if o.value else "")
                + (f'<span class="c">code {H.escape(o.promo_code)}</span>' if o.promo_code else "")
                + "</div>"
                + f'<h3>{H.escape(o.title)}</h3>'
                + (f'<p class="u"><a href="{H.escape(o.url or "")}">{H.escape(o.url or "")}</a></p>' if o.url else "")
                + f'<p class="m">HTTP {rec.get("page_status")} · on-page signals: '
                  f'{H.escape(", ".join((rec.get("signals") or [])[:6]) or "—")} · '
                  f'web corroborations: {rec.get("web_hits")} · '
                  f'platforms: {H.escape(", ".join(o.platforms))}</p></article>')

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
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
letter-spacing:-.015em;margin:10px 0 12px;line-height:1.15}}
h2{{font-family:"Iowan Old Style",Georgia,serif;font-size:1.26rem;margin:36px 0 10px;
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
.lede{{color:#3d4650;max-width:66ch}}
table{{width:100%;border-collapse:collapse;font-size:.9rem;margin:10px 0}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}}
th{{font-family:ui-monospace,Consolas,monospace;font-size:.68rem;letter-spacing:.08em;
text-transform:uppercase;color:var(--mut);border-bottom:1px solid var(--ink)}}
footer{{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);
font-family:ui-monospace,Consolas,monospace;font-size:.7rem;color:var(--mut)}}
</style></head><body><div class="page">
<div class="k">AIOfferRadar · verification pass · {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(ts))}</div>
<h1>Every finding, refined and verified</h1>
<p class="lede">Each finding was refined, its link fetched, the destination page scanned for
specific free/offer signals, and the claim searched on the web. "VERIFIED" requires a specific
signal on the page (free tier, free trial, free credits, no credit card …) — the bare word
"free" is not treated as evidence. <b>{len(rows)}</b> findings checked.</p>
<h2>Verdicts</h2><table><thead><tr><th>Verdict</th><th>Count</th></tr></thead><tbody>
{''.join(f'<tr><td>{H.escape(k)}</td><td>{n}</td></tr>' for k, n in sorted(counts.items(), key=lambda x: order.get(x[0], 9)))}
</tbody></table>
<h2>Confirmed &amp; partial ({len(keep)})</h2>
{''.join(art(r) for r in keep) or '<p>None.</p>'}
<h2>Not confirmed ({len(drop)})</h2>
<table><thead><tr><th>Verdict</th><th>Finding</th><th>Signals</th></tr></thead><tbody>
{''.join(f'<tr><td>{H.escape(v)}</td><td>{H.escape(o.title[:80])}</td><td>{H.escape(", ".join((rec.get("signals") or [])[:4]) or "—")}</td></tr>' for o, rec, v in drop)}
</tbody></table>
<footer>Generated by AIOfferRadar `verify` — evidence is HTTP status + specific on-page signals + web corroboration counts.</footer>
</div></body></html>"""
    (out / f"verified_final_{ts}.html").write_text(doc, encoding="utf-8")

    print("counts:", json.dumps(counts))
    print("kept:", len(keep), "dropped:", len(drop))
    print("report ->", out / f"verified_final_{ts}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
