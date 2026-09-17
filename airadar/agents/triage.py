"""TriageAgent: cheap gate - keep only offer-looking items."""
from __future__ import annotations

import time

from .base import Agent, AgentContext, AgentReport


class TriageAgent(Agent):
    name = "triage"
    role = "filter"

    def run(self, ctx: AgentContext) -> AgentReport:
        t0 = time.time()
        kept = []
        for it in ctx.items:
            try:
                if ctx.classifier is not None and ctx.classifier.is_offer(it):
                    kept.append(it)
            except Exception as exc:  # noqa: BLE001
                ctx.log.debug("triage error on %s: %s", it.id, exc)
        ctx.kept = kept
        return self.report("ok", {"in": len(ctx.items), "kept": len(kept),
                                  "dropped": len(ctx.items) - len(kept)},
                           [], time.time() - t0)
