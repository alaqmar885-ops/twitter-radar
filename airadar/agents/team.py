"""AgentTeam: orchestrates the pipeline and writes a run report."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .analyst import AnalystAgent
from .base import AgentContext
from .curator import CuratorAgent
from .reporter import ReporterAgent
from .scout import ScoutAgent
from .triage import TriageAgent
from .verifier import VerifierAgent

log = logging.getLogger("airadar.team")


class AgentTeam:
    """Runs Scout -> Triage -> Analyst -> Verifier -> Curator -> Reporter."""

    def __init__(self, cfg, offline: bool = False, router=None, store=None,
                 classifier=None, scorer=None, enricher=None, seed_items=None):
        self.cfg = cfg
        self.offline = offline
        self.router = router
        self.store = store
        self.classifier = classifier
        self.scorer = scorer
        self.enricher = enricher
        self.seed_items = seed_items or []
        self.agents = [ScoutAgent(), TriageAgent(), AnalystAgent(),
                       VerifierAgent(), CuratorAgent(), ReporterAgent()]

    def run_once(self) -> dict:
        t0 = time.time()
        ctx = AgentContext(cfg=self.cfg, store=self.store, router=self.router,
                           classifier=self.classifier, scorer=self.scorer,
                           enricher=self.enricher, offline=self.offline,
                           items=list(self.seed_items), log=log)
        reports = []
        for agent in self.agents:
            try:
                rep = agent.run(ctx)
            except Exception as exc:  # noqa: BLE001
                log.error("agent %s crashed: %s", agent.name, exc)
                rep = agent.report("error", {}, [str(exc)])
            reports.append(rep)
            log.info("agent %-9s %-7s %s", rep.agent, rep.status, rep.counts)

        stats = {
            "offline": self.offline,
            "elapsed_s": round(time.time() - t0, 2),
            "items": len(ctx.items),
            "kept": len(ctx.kept),
            "offers": len(ctx.offers),
            "top_offers": [
                {"title": o.title[:100], "score": o.score, "label": o.label,
                 "type": o.offer_type, "platforms": o.platforms, "url": o.url}
                for o in ctx.offers[:5]
            ],
            "agents": [r.as_dict() for r in reports],
        }

        try:
            # Configurable so tests never pollute the live run history (which
            # change detection reads to answer "what is new since last run?").
            runs = Path(getattr(self.cfg, "run_dir", "data/runs"))
            runs.mkdir(parents=True, exist_ok=True)
            (runs / f"run_{int(time.time())}.json").write_text(
                json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            log.warning("could not write run report: %s", exc)

        return stats
