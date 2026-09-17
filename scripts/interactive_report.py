"""Interactive audit report: filter + inspect every finding's evidence.

Single self-contained HTML (no remote assets, no localStorage). Purpose: let a
human verify that no good source was mislabelled as card-required or as lacking
UPI/India support, by exposing the raw evidence behind each verdict.
"""
from __future__ import annotations

import html as H
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\scrapper")
from airadar.store import Store   # noqa: E402

DB = r"D:\scrapper\data\airadar.db"
OUT = Path(r"D:\scrapper\data\reports")


def main() -> int:
    store = Store(DB)
    ver = store.verifications()
    offers = store.top_offers(limit=5000)
    stats = store.stats()
    store.close()

    rows = []
    for o in offers:
        rec = ver.get(o.id, {})
        rows.append({
            "title": o.title or o.product or "",
            "url": o.url or "",
            "score": round(o.score, 3),
            "label": o.label,
            "verdict": o.verdict or "",
            "type": o.offer_type,
            "value": o.value or "",
            "code": o.promo_code or "",
            "platforms": o.platforms,
            "page_status": rec.get("page_status"),
            "page_title": (rec.get("page_title") or "")[:120],
            "signals": rec.get("signals") or [],
            "no_cc": rec.get("no_cc_signals") or [],
            "card": rec.get("card_signals") or [],
            "upi": rec.get("upi_signals") or [],
            "india": rec.get("india_signals") or [],
            "web_hits": rec.get("web_hits", 0),
            "notes": rec.get("notes") or [],
            "items": [{"p": i.platform, "a": i.author, "t": (i.text or i.title)[:180],
                       "u": i.url} for i in (o.items or [])[:4]],
        })

    # review flags: places where a human should double-check the machine
    for r in rows:
        flags = []
        if r["no_cc"] and r["card"]:
            flags.append("card AND no-card wording on the same page")
        if r["verdict"] == "CARD_REQUIRED" and (r["no_cc"] or "free" in (r["title"] + r["value"]).lower()):
            flags.append("marked card-required but reads like a free offer")
        if r["verdict"] in ("VERIFIED", "VERIFIED_NO_CC") and not r["upi"] and not r["india"]:
            flags.append("verified but no India/UPI evidence found")
        if r["verdict"] == "DERIVATIVE":
            flags.append("discussion page - evidence not authoritative")
        if not r["signals"] and r["verdict"] not in ("NO_URL", "UNREACHABLE"):
            flags.append("no on-page signal recorded")
        r["flags"] = flags

    data = {"generated": int(time.time()), "stats": stats, "rows": rows}
    ts = int(time.time())
    OUT.mkdir(parents=True, exist_ok=True)

    doc = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIOfferRadar - interactive audit</title>
<style>
:root{--ink:#14181d;--ink2:#3d4650;--mut:#6b7480;--line:#d8dde3;--paper:#fbfaf8;
--acc:#8a1c1c;--ok:#1f6b45;--amb:#8a5a00;--bad:#8a1c1c;
--mono:ui-monospace,SFMono-Regular,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.page{max-width:1240px;margin:0 auto;padding:34px 22px 80px}
h1{font-family:"Iowan Old Style",Georgia,serif;font-size:1.9rem;margin:6px 0 4px;font-weight:600}
.k{font-family:var(--mono);font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--mut)}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;padding:14px 0;border-bottom:1px solid var(--ink);border-top:1px solid var(--line);margin:18px 0 6px;position:sticky;top:0;background:var(--paper);z-index:5}
.f{display:flex;flex-direction:column;gap:3px}
.f label{font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
input[type=text],select,input[type=number]{font:inherit;font-size:.85rem;padding:5px 8px;border:1px solid var(--line);border-radius:3px;background:#fff;color:var(--ink)}
input[type=text]{min-width:230px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 4px}
.chip{font-family:var(--mono);font-size:.72rem;padding:3px 9px;border:1px solid var(--line);border-radius:999px;cursor:pointer;background:#fff;user-select:none}
.chip.on{border-color:var(--acc);color:var(--acc);font-weight:700}
.chip .n{color:var(--mut);margin-left:5px}
.counts{font-family:var(--mono);font-size:.76rem;color:var(--mut);margin:10px 0 4px}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-family:var(--mono);font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);border-bottom:1px solid var(--ink);cursor:pointer;white-space:nowrap}
tbody tr:hover{background:#f4f6f8}
tbody tr.open{background:#f0f3f6}
.b{font-family:var(--mono);font-size:.62rem;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid currentColor;white-space:nowrap}
.v-VERIFIED_NO_CC{color:var(--ok)}.v-VERIFIED{color:var(--ok)}.v-PARTIAL{color:var(--amb)}
.v-DERIVATIVE,.v-WEAK,.v-NOT_AN_OFFER,.v-UNREACHABLE,.v-NO_URL{color:var(--mut)}
.v-CARD_REQUIRED{color:var(--bad)}
.sc{font-family:var(--mono);text-align:right;white-space:nowrap}
.flag{display:inline-block;font-size:.66rem;color:var(--amb);border:1px solid var(--amb);border-radius:3px;padding:1px 5px;margin:1px 3px 1px 0}
.ev{background:#f4f6f8;border-left:2px solid var(--acc);padding:10px 14px;margin:6px 0 12px;font-size:.82rem}
.ev b{font-family:var(--mono);font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mut)}
.ev code{font-family:var(--mono);font-size:.78rem;background:#fff;border:1px solid var(--line);border-radius:3px;padding:.06em .3em;margin-right:3px;display:inline-block;margin-bottom:3px}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.muted{color:var(--mut)}
.nores{padding:26px;color:var(--mut);text-align:center}
</style></head><body><div class="page">
<div class="k">AIOfferRadar &middot; interactive audit</div>
<h1>Every finding, with the evidence behind its verdict</h1>
<p class="muted" style="max-width:80ch">Filter and inspect. Each row shows the raw page evidence
(free signals, no-card wording, card wording, UPI/India terms, HTTP status) so you can confirm no good
source was mislabelled as card-required or as lacking UPI. Rows flagged for review are the places where
the machine is least certain.</p>

<div class="bar">
  <div class="f"><label>search</label><input type="text" id="q" placeholder="title, url, code..."></div>
  <div class="f"><label>card policy</label><select id="card">
    <option value="">any</option><option value="nocc">no-card evidence</option>
    <option value="card">card-required evidence</option><option value="none">card policy unstated</option></select></div>
  <div class="f"><label>UPI</label><select id="upi"><option value="">any</option>
    <option value="yes">UPI evidence only</option><option value="none">no UPI evidence</option></select></div>
  <div class="f"><label>India</label><select id="india"><option value="">any</option>
    <option value="yes">India evidence only</option></select></div>
  <div class="f"><label>min score</label><input type="number" id="mins" value="0" min="0" max="1" step="0.05" style="width:80px"></div>
  <div class="f"><label>platform</label><select id="plat"><option value="">any</option></select></div>
  <div class="f"><label>flags</label><select id="flagsel"><option value="">any</option>
    <option value="review">flagged for review only</option></select></div>
</div>

<div class="chips" id="verdicts"></div>
<div class="counts" id="counts"></div>
<table><thead><tr>
  <th data-sort="verdict">verdict</th><th data-sort="score">score</th>
  <th data-sort="title">finding</th><th data-sort="type">type</th>
  <th data-sort="platforms">platforms</th><th data-sort="card">card</th>
  <th data-sort="upi">upi</th><th data-sort="india">india</th><th>flags</th>
</tr></thead><tbody id="tb"></tbody></table>
<div class="nores" id="nores" style="display:none">No findings match these filters.</div>

<footer class="k" style="margin-top:40px">evidence = HTTP status + on-page terms; a term is a lead, not proof &middot; generated by AIOfferRadar</footer>
</div>
<script>
const DATA = __DATA__;
const VERDICTS = ["VERIFIED_NO_CC","VERIFIED","PARTIAL","DERIVATIVE","WEAK","NOT_AN_OFFER","CARD_REQUIRED","UNREACHABLE","NO_URL"];
const state = {q:"",card:"",upi:"",india:"",mins:0,plat:"",flagsel:"",verdicts:new Set(),sort:"score",dir:-1};

const el = id => document.getElementById(id);
const counts = vs => DATA.rows.filter(r=>vs.includes(r.verdict)).length;

function buildChips(){
  el("verdicts").innerHTML = VERDICTS.map(v =>
    `<span class="chip" data-v="${v}">${v}<span class="n">${counts([v])}</span></span>`).join("");
  el("verdicts").querySelectorAll(".chip").forEach(c=>{
    c.onclick = ()=>{ const v=c.dataset.v;
      state.verdicts.has(v)?state.verdicts.delete(v):state.verdicts.add(v);
      c.classList.toggle("on"); render(); };
  });
}
function buildPlatforms(){
  const set = new Set(); DATA.rows.forEach(r=>r.platforms.forEach(p=>set.add(p)));
  [...set].sort().forEach(p=>{ const o=document.createElement("option"); o.value=p; o.textContent=p; el("plat").appendChild(o); });
}
function matches(r){
  if(state.verdicts.size && !state.verdicts.has(r.verdict)) return false;
  if(r.score < state.mins) return false;
  if(state.plat && !r.platforms.includes(state.plat)) return false;
  if(state.card==="nocc" && !r.no_cc.length) return false;
  if(state.card==="card" && !r.card.length) return false;
  if(state.card==="none" && (r.no_cc.length||r.card.length)) return false;
  if(state.upi==="yes" && !r.upi.length) return false;
  if(state.upi==="none" && r.upi.length) return false;
  if(state.india==="yes" && !r.india.length) return false;
  if(state.flagsel==="review" && !r.flags.length) return false;
  if(state.q){ const hay=(r.title+" "+r.url+" "+r.code+" "+r.type).toLowerCase();
    if(!hay.includes(state.q.toLowerCase())) return false; }
  return true;
}
const esc = s => (s||"").replace(/[&<>"]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function chipList(arr, cls){ return (arr||[]).map(s=>`<code>${esc(s)}</code>`).join(""); }

function render(){
  const rows = DATA.rows.filter(matches).sort((a,b)=>{
    const k=state.sort; let av=a[k], bv=b[k];
    if(k==="platforms"){ av=a.platforms.join(); bv=b.platforms.join(); }
    if(k==="card"){ av=a.card.join(); bv=b.card.join(); }
    if(k==="upi"){ av=a.upi.join(); bv=b.upi.join(); }
    if(k==="india"){ av=a.india.join(); bv=b.india.join(); }
    if(typeof av==="number") return (av-bv)*state.dir;
    return String(av).localeCompare(String(bv))*state.dir;
  });
  el("counts").textContent = rows.length + " of " + DATA.rows.length + " findings shown";
  el("nores").style.display = rows.length? "none":"block";
  el("tb").innerHTML = rows.map((r,i)=>`
    <tr data-i="${i}">
      <td><span class="b v-${esc(r.verdict)}">${esc(r.verdict)||"-"}</span></td>
      <td class="sc">${(r.score*100).toFixed(0)}%</td>
      <td>${esc(r.title)}${r.code?` <code>${esc(r.code)}</code>`:""}${r.value?` <span class="muted">${esc(r.value)}</span>`:""}
          <br><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc((r.url||"").slice(0,74))}</a>
          ${recap(r)}</td>
      <td>${esc(r.type)}</td>
      <td class="muted">${esc(r.platforms.join(", "))}</td>
      <td>${r.no_cc.length?'<span class="b v-VERIFIED">no card</span>':(r.card.length?'<span class="b v-CARD_REQUIRED">card</span>':'<span class="muted">-</span>')}</td>
      <td>${r.upi.length?'<span class="b v-VERIFIED">yes</span>':'<span class="muted">-</span>'}</td>
      <td>${r.india.length?'<span class="b v-PARTIAL">yes</span>':'<span class="muted">-</span>'}</td>
      <td>${(r.flags||[]).map(f=>`<span class="flag">${esc(f)}</span>`).join("")}</td>
    </tr>`).join("");
  el("tb").querySelectorAll("tr").forEach(tr=>{
    tr.onclick = ()=> toggle(tr, rows[+tr.dataset.i]);
  });
}
function recap(r){ return ""; }
function toggle(tr, r){
  const nxt = tr.nextElementSibling;
  if(nxt && nxt.classList.contains("evrow")){ nxt.remove(); tr.classList.remove("open"); return; }
  tr.classList.add("open");
  const ev = document.createElement("tr");
  ev.className="evrow";
  ev.innerHTML = `<td colspan="9"><div class="ev">
    <div><b>http</b> <code>${r.page_status}</code> <b>page title</b> ${esc(r.page_title)||"-"}
      <b>web corroborations</b> <code>${r.web_hits}</code> <b>verdict</b> <code>${esc(r.verdict)}</code></div>
    <div><b>free signals</b> ${chipList(r.signals)||"<span class='muted'>none</span>"}</div>
    <div><b>no-card wording</b> ${chipList(r.no_cc)||"<span class='muted'>none</span>"}</div>
    <div><b>card wording</b> ${chipList(r.card)||"<span class='muted'>none</span>"}</div>
    <div><b>upi</b> ${chipList(r.upi)||"<span class='muted'>none</span>"} &nbsp; <b>india</b> ${chipList(r.india)||"<span class='muted'>none</span>"}</div>
    ${(r.notes||[]).length?`<div><b>notes</b> ${(r.notes||[]).map(n=>`<code>${esc(n)}</code>`).join("")}</div>`:""}
    ${(r.flags||[]).length?`<div><b>review</b> ${(r.flags||[]).map(f=>`<span class="flag">${esc(f)}</span>`).join("")}</div>`:""}
    ${(r.items||[]).length?`<div><b>source items</b>${(r.items||[]).map(i=>`<div class="muted">${esc(i.p)} @${esc(i.a)}: ${esc(i.t)}</div>`).join("")}</div>`:""}
  </div></td>`;
  tr.parentNode.insertBefore(ev, tr.nextSibling);
}
["q","card","upi","india","mins","plat","flagsel"].forEach(id=>{
  el(id).addEventListener("input", e=>{
    state[id==="mins"?"mins":id] = id==="mins" ? parseFloat(e.target.value||0) : e.target.value;
    render();
  });
});
document.querySelectorAll("th[data-sort]").forEach(th=>{
  th.onclick = ()=>{ const k=th.dataset.sort; state.dir = (state.sort===k)? -state.dir : -1; state.sort=k; render(); };
});
buildChips(); buildPlatforms(); render();
</script></body></html>"""

    doc = doc.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    path = OUT / f"interactive_{ts}.html"
    path.write_text(doc, encoding="utf-8")

    review = [r for r in rows if r["flags"]]
    print(f"rows: {len(rows)} | flagged for review: {len(review)}")
    print("report ->", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
