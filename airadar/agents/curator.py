"""CuratorAgent: merge duplicates, score, persist."""
from __future__ import annotations

import time

from .base import Agent, AgentContext, AgentReport


class CuratorAgent(Agent):
    name = "curator"
    role = "rank"

    def run(self, ctx: AgentContext) -> AgentReport:
        t0 = time.time()
        merged: dict = {}
        for o in ctx.offers:
            key = (o.product or o.url or o.title or "").strip().lower()
            if not key:
                key = o.id
            m = merged.get(key)
            if m is None:
                merged[key] = o
                continue
            m.items.extend(o.items)
            for p in o.platforms:
                if p not in m.platforms:
                    m.platforms.append(p)
            m.promo_code = m.promo_code or o.promo_code
            m.value = m.value or o.value
            if not m.url:
                m.url = o.url
            m.link_ok = m.link_ok or o.link_ok
            if o.web_sources and not m.web_sources:
                m.web_sources = o.web_sources
                m.web_verified = o.web_verified
            m.last_updated = time.time()

        offers = list(merged.values())
        new = 0
        for o in offers:
            try:
                ctx.scorer.score(o)
                if ctx.store is not None and ctx.store.save_offer(o):
                    new += 1
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("curate failed for %s: %s", o.id, exc)
        offers.sort(key=lambda x: x.score, reverse=True)
        ctx.offers = offers
        return self.report("ok", {"offers": len(offers), "new_offers": new},
                           [], time.time() - t0)
