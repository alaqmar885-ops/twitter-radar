"""Base class for all AIOfferRadar sources."""
from __future__ import annotations

import abc
import logging
import time

log = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class BaseSource(abc.ABC):
    name: str = "base"
    platform: str = "base"

    def __init__(self, cfg):
        self.cfg = cfg
        self._last = 0.0

    def available(self) -> bool:
        return True

    @abc.abstractmethod
    def fetch(self, limit: int = 25) -> list:
        """Return a list of Items. MUST NOT raise."""
        raise NotImplementedError

    # -- helpers ---------------------------------------------------------------
    def _sleep(self) -> None:
        d = getattr(self.cfg, "delay_between_requests", 1.0) or 0.0
        if d <= 0:
            return
        wait = d - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def _timeout(self) -> int:
        return int(getattr(self.cfg, "request_timeout", 20) or 20)

    def _get(self, url: str, **kw):
        import httpx
        headers = {"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"}
        extra = kw.pop("headers", None)
        if extra:
            headers.update(extra)
        return httpx.get(url, headers=headers, timeout=self._timeout(),
                         follow_redirects=True, **kw)

    @staticmethod
    def _clean(html_text: str) -> str:
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(html_text or "", "html.parser").get_text(" ", strip=True)
        except Exception:
            return (html_text or "").strip()
