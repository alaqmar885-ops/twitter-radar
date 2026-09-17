"""ReporterAgent: render the offer digest (html + md + json)."""
from __future__ import annotations

import html as _html
import json
import time
from pathlib import Path

from .base import Agent, AgentContext, AgentReport


def _esc(s: str) -> str:
    return _html.escape(s or "")


def _badge(label: str) -> str:
    return {"VERIFIED": "b-ver", "HIGH": "b-ok", "MEDIUM": "b-warn"}.get(label, "b-low")


class ReporterAgent(Agent):
    name = "reporter"
    role = "render"

    def run(self, ctx: AgentContext) -> AgentReport:
        t0 = time.time()
        out_dir = Path(getattr(ctx.cfg, "digest_dir", "data/digests"))
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        top = ctx.offers[: getattr(ctx.cfg, "top_n", 25)]

        html_path = out_dir / f"airadar_digest_{ts}.html"
        md_path = out_dir / f"airadar_digest_{ts}.md"
        json_path = out_dir / f"airadar_digest_{ts}.json"

        html_path.write_text(self._render_html(top, ctx), encoding="utf-8")
        md_path.write_text(self._render_md(top, ctx), encoding="utf-8")
        json_path.write_text(json.dumps({
            "generated": ts,
            "offers": [self._offer_dict(o) for o in top],
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        return self.report("ok", {"offers": len(top), "html": str(html_path),
                                  "md": str(md_path), "json": str(json_path)},
                           [], time.time() - t0)

    @staticmethod
    def _offer_dict(o) -> dict:
        return {
            "id": o.id, "title": o.title, "summary": o.summary,
            "offer_type": o.offer_type, "value": o.value, "promo_code": o.promo_code,
            "product": o.product, "url": o.url, "platforms": o.platforms,
            "score": o.score, "label": o.label, "link_ok": o.link_ok,
            "web_verified": o.web_verified,
            "sources": [{"platform": i.platform, "author": i.author,
                         "url": i.url, "text": (i.text or i.title)[:200]}
                        for i in o.items[:5]],
            "web_sources": o.web_sources[:4],
        }

    def _render_md(self, offers, ctx) -> str:
        lines = ["# AIOfferRadar - Free AI Offers Digest", ""]
        lines.append(f"_Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}_")
        lines.append("")
        if not offers:
            lines.append("No offers above threshold yet.")
        for o in offers:
            lines.append(f"## [{o.label}] {o.title[:120]}")
            bits = [f"**Score {o.score:.0%}**", f"`{o.offer_type}`"]
            if o.value:
                bits.append(f"**{o.value}**")
            if o.promo_code:
                bits.append(f"code `{o.promo_code}`")
            lines.append(" - ".join(bits))
            if o.url:
                lines.append(f"<{o.url}>")
            lines.append(f"_platforms: {', '.join(o.platforms)}_")
            lines.append("")
        return "\n".join(lines)

    def _render_html(self, offers, ctx) -> str:
        gen = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        cards = []
        for o in offers:
            srcs = "".join(
                f'<div class="src"><span class="p">{_esc(i.platform)}</span> '
                f'@{_esc(i.author)} - {_esc((i.text or i.title)[:180])} '
                f'{"<a href=\"" + _esc(i.url) + "\">link</a>" if i.url else ""}</div>'
                for i in o.items[:4]
            )
            web = ""
            if o.web_sources:
                web = '<div class="web"><strong>Web sources:</strong>' + "".join(
                    f'<div><a href="{_esc(s.get("url",""))}">{_esc((s.get("title") or "")[:70])}</a></div>'
                    for s in o.web_sources[:4]
                ) + "</div>"
            code = f'<span class="code">code: {_esc(o.promo_code)}</span>' if o.promo_code else ""
            val = f'<span class="val">{_esc(o.value)}</span>' if o.value else ""
            link = f'<a href="{_esc(o.url)}">open offer</a>' if o.url else ""
            cards.append(
                f'<div class="card"><div class="row">'
                f'<span class="badge {_badge(o.label)}">{_esc(o.label)}</span>'
                f'<span class="score">{o.score:.0%}</span>'
                f'<span class="tag">{_esc(o.offer_type)}</span>{val}{code}</div>'
                f'<div class="head">{_esc(o.title[:160])}</div>'
                f'<div class="plat">{" &middot; ".join(_esc(p) for p in o.platforms)} '
                f'{"| link OK" if o.link_ok else ""} {link}</div>'
                f'{srcs}{web}</div>'
            )
        body = "".join(cards) or '<div class="empty">No offers yet.</div>'
        return (
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
            "<title>AIOfferRadar Digest</title><style>"
            ":root{--bg:#0f1419;--panel:#161c26;--panel2:#1c2430;--border:#2a3441;"
            "--txt:#e7e9ea;--muted:#71767b;--accent:#1d9bf0;--grn:#00ba7c;--amb:#ffca3a;--red:#f4212e}"
            "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);"
            "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.55}"
            ".wrap{max-width:900px;margin:0 auto;padding:28px 20px 60px}"
            "h1{font-size:1.6rem;margin:0 0 4px}.sub{color:var(--muted);font-size:.9rem;margin-bottom:22px}"
            ".card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin:12px 0}"
            ".row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}"
            ".badge{font-weight:700;font-size:.66rem;text-transform:uppercase;padding:2px 8px;border-radius:5px}"
            ".b-ver{background:rgba(0,186,124,.15);color:var(--grn);border:1px solid var(--grn)}"
            ".b-ok{background:rgba(0,186,124,.12);color:var(--grn);border:1px solid rgba(0,186,124,.5)}"
            ".b-warn{background:rgba(255,202,58,.15);color:var(--amb);border:1px solid var(--amb)}"
            ".b-low{background:rgba(244,33,46,.12);color:var(--red);border:1px solid rgba(244,33,46,.5)}"
            ".score{font-weight:700;color:var(--accent)}.tag,.val,.code{font-size:.72rem;"
            "background:var(--panel2);border:1px solid var(--border);border-radius:999px;padding:2px 9px}"
            ".val{color:var(--grn)}.code{color:var(--amb)}"
            ".head{font-size:1.02rem;font-weight:600;margin:8px 0 4px}"
            ".plat{color:var(--muted);font-size:.8rem;margin-bottom:8px}"
            ".src{background:var(--panel2);border:1px solid var(--border);border-radius:8px;"
            "padding:8px 10px;margin:6px 0;font-size:.82rem}"
            ".p{color:var(--accent);font-weight:600}"
            ".web{margin-top:8px;padding:8px 10px;border-left:3px solid var(--grn);"
            "background:rgba(0,186,124,.06);font-size:.82rem}"
            "a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}"
            ".empty,.footer{color:var(--muted);text-align:center;padding:24px;font-size:.8rem}"
            "</style></head><body><div class=\"wrap\">"
            f"<h1>AIOfferRadar Digest</h1><div class=\"sub\">{len(offers)} offers - "
            f"multi-platform free-AI-offer radar - {gen}</div>{body}"
            f"<div class=\"footer\">Generated by AIOfferRadar agent team - {gen}</div>"
            "</div></body></html>"
        )
