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

    def fetch_all(self, limit: int | None = None, workers: int | None = None) -> list:
        """Fetch every available source, in parallel, then dedupe by item id.

        Network-bound sources are the slowest part of a cycle; running them
        concurrently cuts wall-clock time several-fold. Each source still
        honours its own polite delay between *its* requests.
        """
        from concurrent.futures import ThreadPoolExecutor

        n = limit or getattr(self.cfg, "per_source_limit", 25)
        w = max(1, int(workers or getattr(self.cfg, "workers", 6) or 1))
        active = []
        for s in self._sources:
            try:
                if s.available():
                    active.append(s)
                else:
                    log.info("source %s unavailable - skipped", s.name)
            except Exception as exc:  # noqa: BLE001
                log.warning("source %s availability check failed: %s", s.name, exc)

        results: dict = {}

        def _one(src):
            try:
                return src.name, src.fetch(limit=n)
            except Exception as exc:  # noqa: BLE001
                log.warning("source %s failed: %s", src.name, exc)
                return src.name, []

        if len(active) > 1 and w > 1:
            with ThreadPoolExecutor(max_workers=w) as ex:
                for name, got in ex.map(_one, active):
                    results[name] = got
        else:
            for src in active:
                name, got = _one(src)
                results[name] = got

        seen = set()
        items = []
        for src in active:
            new = 0
            for it in results.get(src.name, []) or []:
                if it.id in seen:
                    continue
                seen.add(it.id)
                items.append(it)
                new += 1
            log.info("source %-10s -> %d items", src.name, new)
        return items
