"""Agent primitives: report, shared context, abstract agent."""
from __future__ import annotations

import abc
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class AgentReport:
    """Outcome of one agent run - machine readable for the run report."""
    agent: str
    role: str
    status: str = "ok"          # ok | skipped | error
    counts: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    elapsed: float = 0.0

    def as_dict(self) -> dict:
        return {
            "agent": self.agent,
            "role": self.role,
            "status": self.status,
            "counts": dict(self.counts),
            "notes": list(self.notes),
            "elapsed": round(self.elapsed, 3),
        }


@dataclass
class AgentContext:
    """Shared blackboard the agents read from and write to."""
    cfg: Any
    store: Any = None
    router: Any = None
    classifier: Any = None
    scorer: Any = None
    enricher: Any = None
    offline: bool = False
    items: list = field(default_factory=list)     # scout output
    kept: list = field(default_factory=list)      # triage output
    offers: list = field(default_factory=list)    # analyst output
    log: logging.Logger = field(default_factory=lambda: logging.getLogger("airadar.team"))


class Agent(abc.ABC):
    """One role in the team. run() must never raise."""

    name: str = "agent"
    role: str = ""

    @abc.abstractmethod
    def run(self, ctx: AgentContext) -> AgentReport:
        raise NotImplementedError

    def report(self, status: str = "ok", counts: dict | None = None,
               notes: list | None = None, elapsed: float = 0.0) -> AgentReport:
        return AgentReport(self.name, self.role, status, counts or {}, notes or [], elapsed)

    @staticmethod
    def now() -> float:
        return time.time()
