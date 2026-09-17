"""VerifierAgent: link liveness + optional web corroboration."""
from __future__ import annotations

import time

from .base import BROWSER_UA, Agent, AgentContext, AgentReport


class VerifierAgent(Agent):
    name = "verifier"
    role = "verify"

    def run(self, ctx: AgentContext) -> AgentReport:
        t0 = time.time()
        if ctx.offline:
            return self.report("skipped", {"live": 0, "web_verified": 0},
                               ["offline mode: no network verification"],
                               time.time() - t0)

        live = 0
        web = 0
        for o in ctx.offers:
            if o.url:
                try:
                    o.link_ok = self._link_ok(o.url, ctx)
                    if o.link_ok:
                        live += 1
                except Exception as exc:  # noqa: BLE001
                    ctx.log.debug("link check failed %s: %s", o.url, exc)
            enr = ctx.enricher
            if enr is not None and getattr(enr, "available", lambda: False)() and o.link_ok:
                try:
                    q = (o.product or o.title or "")[:110]
                    if q:
                        res = enr.search(q, max_results=4)
                        if res:
                            o.web_sources = res[:4]
                            o.web_verified = len(res) >= 2
                            if o.web_verified:
                                web += 1
                except Exception as exc:  # noqa: BLE001
                    ctx.log.debug("web verify failed: %s", exc)
        return self.report("ok", {"live": live, "web_verified": web,
                                  "offers": len(ctx.offers)}, [], time.time() - t0)

    @staticmethod
    def _link_ok(url: str, ctx: AgentContext) -> bool:
        import httpx
        headers = {"User-Agent": BROWSER_UA}
        timeout = getattr(ctx.cfg, "request_timeout", 20)
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as c:
            r = c.head(url)
            if r.status_code >= 400:
                r = c.get(url)
            return r.status_code < 400
