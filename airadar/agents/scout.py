"""ScoutAgent: pull fresh Items from every enabled source."""
from __future__ import annotations

import time

from .base import Agent, AgentContext, AgentReport


class ScoutAgent(Agent):
    name = "scout"
    role = "collect"

    def run(self, ctx: AgentContext) -> AgentReport:
        t0 = time.time()
        counts: dict = {}
        try:
            if ctx.offline:
                items = list(ctx.items)
            else:
                items = ctx.router.fetch_all(ctx.cfg.per_source_limit) if ctx.router else []
                ctx.items = items
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("scout failed: %s", exc)
            return self.report("error", {"items": 0}, [str(exc)], time.time() - t0)

        new = 0
        for it in items:
            try:
                if ctx.store is not None and ctx.store.save_item(it):
                    new += 1
            except Exception as exc:  # noqa: BLE001
                ctx.log.debug("save_item failed for %s: %s", it.id, exc)
            counts[it.platform] = counts.get(it.platform, 0) + 1

        return self.report("ok", {"items": len(items), "new_items": new, **counts},
                           [], time.time() - t0)
