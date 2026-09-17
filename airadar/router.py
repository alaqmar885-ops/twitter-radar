"""SourceRouter: try every enabled source, dedupe, never crash."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class SourceRouter:
    def __init__(self, cfg):
        self.cfg = cfg
        self._sources = []
        try:
            from .sources import SOURCE_REGISTRY
        except Exception as exc:  # noqa: BLE001
            log.warning("sources registry unavailable: %s", exc)
            SOURCE_REGISTRY = {}
        wanted = list(getattr(cfg, "enabled_sources", []) or [])
        for name in wanted:
            cls = SOURCE_REGISTRY.get(name)
            if cls is None:
                log.warning("unknown source '%s' - skipped", name)
                continue
            try:
                self._sources.append(cls(cfg))
            except Exception as exc:  # noqa: BLE001
                log.warning("failed to init source '%s': %s", name, exc)
        log.info("SourceRouter ready with %d sources", len(self._sources))

    @property
    def sources(self) -> list:
        return list(self._sources)

    def available(self) -> dict:
        out = {}
        for s in self._sources:
            try:
                out[s.name] = bool(s.available())
            except Exception:
                out[s.name] = False
        return out

    def fetch_all(self, limit: int | None = None) -> list:
        n = limit or getattr(self.cfg, "per_source_limit", 25)
        seen = set()
        items = []
        for s in self._sources:
            try:
                if not s.available():
                    log.info("source %s unavailable - skipped", s.name)
                    continue
                got = s.fetch(limit=n)
            except Exception as exc:  # noqa: BLE001
                log.warning("source %s failed: %s", s.name, exc)
                continue
            new = 0
            for it in got or []:
                if it.id in seen:
                    continue
                seen.add(it.id)
                items.append(it)
                new += 1
            log.info("source %-10s -> %d items", s.name, new)
        return items
