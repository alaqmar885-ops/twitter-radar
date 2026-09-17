"""AnalystAgent: classify kept items and cluster them into Offers."""
from __future__ import annotations

import time
from urllib.parse import urlparse

from ..models import Offer
from .base import Agent, AgentContext, AgentReport

GENERIC_KEYS = {"show", "ask", "hn", "show hn", "free", "ai", "news", "tool",
                "app", "update", "model", "launch"}


def _host(url: str) -> str:
    try:
        h = urlparse(url or "").netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


class AnalystAgent(Agent):
    name = "analyst"
    role = "classify"

    def run(self, ctx: AgentContext) -> AgentReport:
        t0 = time.time()
        clusters: dict = {}
        try:
            for it in ctx.kept:
                info = ctx.classifier.classify(it)
                if not info:
                    continue
                product = (info.get("product") or "").strip()
                key = product.lower()
                # Never cluster on a generic word - fall back to the artifact
                # (host + path) or the item id so unrelated posts stay separate.
                if not key or key in GENERIC_KEYS or len(key) < 3:
                    key = ""
                if key:
                    key = "p:" + key
                else:
                    host = _host(it.url)
                    key = "u:" + (host + urlparse(it.url or "").path.lower()
                                  if host else it.id)
                o = clusters.get(key)
                if o is None:
                    o = Offer(
                        title=(info.get("summary") or it.title or it.text[:140]).strip(),
                        summary=info.get("summary", ""),
                        offer_type=info.get("offer_type", "other"),
                        value=info.get("value", ""),
                        promo_code=info.get("promo_code", ""),
                        product=product,
                        url=it.url,
                        platforms=[it.platform],
                        items=[it],
                    )
                    clusters[key] = o
                else:
                    # only genuinely-related items merge: same product key, or
                    # same host when the key is artifact-based
                    o.items.append(it)
                    if it.platform not in o.platforms:
                        o.platforms.append(it.platform)
                    if not o.url and it.url:
                        o.url = it.url
                    if not o.promo_code and info.get("promo_code"):
                        o.promo_code = info["promo_code"]
                    if not o.value and info.get("value"):
                        o.value = info["value"]
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("analyst failed: %s", exc)
            return self.report("error", {"offers": 0}, [str(exc)], time.time() - t0)

        ctx.offers = list(clusters.values())
        return self.report("ok", {"offers": len(ctx.offers),
                                  "from_items": len(ctx.kept)}, [], time.time() - t0)
