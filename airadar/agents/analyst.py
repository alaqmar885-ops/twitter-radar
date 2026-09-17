"""AnalystAgent: classify kept items and cluster them into Offers."""
from __future__ import annotations

import time

from ..models import Offer
from .base import Agent, AgentContext, AgentReport


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
                key = (info.get("product") or "").strip().lower()
                if not key:
                    key = (it.url or it.id).strip().lower()
                o = clusters.get(key)
                if o is None:
                    o = Offer(
                        title=(info.get("summary") or it.title or it.text[:140]).strip(),
                        summary=info.get("summary", ""),
                        offer_type=info.get("offer_type", "other"),
                        value=info.get("value", ""),
                        promo_code=info.get("promo_code", ""),
                        product=info.get("product", ""),
                        url=it.url,
                        platforms=[it.platform],
                        items=[it],
                    )
                    clusters[key] = o
                else:
                    o.items.append(it)
                    if it.platform not in o.platforms:
                        o.platforms.append(it.platform)
                    if not o.url and it.url:
                        o.url = it.url
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("analyst failed: %s", exc)
            return self.report("error", {"offers": 0}, [str(exc)], time.time() - t0)

        ctx.offers = list(clusters.values())
        return self.report("ok", {"offers": len(ctx.offers),
                                  "from_items": len(ctx.kept)}, [], time.time() - t0)
