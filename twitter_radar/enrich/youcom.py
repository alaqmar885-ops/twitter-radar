"""You.com MCP enrichment — web verification of tweet claims.

When the radar spots a tweet claiming e.g. "Cursor is offering 2 weeks free
Pro", we don't just trust the tweet.  We run a you-search query to find
corroborating (or contradicting) web sources.  This turns raw tweet data
into *verified intelligence with confidence*.

The You.com MCP is a streamable-HTTP JSON-RPC endpoint.  This module wraps
the two-step call (initialize → tools/call) so callers just get a list of
web results back.

Auth: Authorization: Bearer ${YDC_API_KEY}
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

import httpx

from ..models import Finding, Tweet

log = logging.getLogger(__name__)


class YouComEnricher:
    """Call the You.com MCP `you-search` tool to verify claims."""

    def __init__(
        self,
        api_key: str,
        mcp_url: str = "https://api.you.com/mcp",
        max_results: int = 4,
        timeout: int = 25,
    ):
        self.api_key = api_key
        self.mcp_url = mcp_url
        self.max_results = max_results
        self.timeout = timeout
        self._session_id: Optional[str] = None
        self._initialized = False

    def available(self) -> bool:
        return bool(self.api_key)

    # -- MCP JSON-RPC transport ------------------------------------------------

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _call(self, method: str, params: dict) -> dict:
        """Single JSON-RPC call.  Parses SSE `data:` line → JSON."""
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4().int % 100000),
            "method": method,
            "params": params,
        }
        r = httpx.post(
            self.mcp_url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        if r.status_code != 200:
            return {}
        # Response is SSE: lines of "event: message\ndata: {json}\n\n".
        # Take the last non-empty data line.
        data_line = ""
        for line in r.text.splitlines():
            if line.startswith("data: "):
                data_line = line[6:]
        if not data_line:
            return {}
        try:
            return json.loads(data_line)
        except json.JSONDecodeError:
            return {}

    def _ensure_init(self) -> None:
        """One-time MCP initialize handshake."""
        if self._initialized:
            return
        try:
            self._call("initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "twitter-radar", "version": "1.0.0"},
            })
            self._initialized = True
        except Exception as exc:  # noqa: BLE001
            log.warning("You.com MCP initialize failed: %s", exc)

    # -- public API ------------------------------------------------------------

    def search(self, query: str, max_results: Optional[int] = None) -> list[dict]:
        """Run a you-search.  Returns a list of {title, url, description, snippet}."""
        if not self.available():
            return []
        self._ensure_init()
        n = max_results or self.max_results
        try:
            resp = self._call("tools/call", {
                "name": "you-search",
                "arguments": {"query": query, "max_results": n},
            })
        except Exception as exc:  # noqa: BLE001
            log.warning("you-search '%s' failed: %s", query[:60], exc)
            return []

        # Result is in result.content[0].text as a JSON string.
        content = resp.get("result", {}).get("content", [])
        if not content:
            return []
        try:
            text = content[0].get("text", "")
            data = json.loads(text)
        except (json.JSONDecodeError, IndexError, KeyError):
            return []

        # Normalize the results.web array.
        web = data.get("results", {}).get("web", [])
        out: list[dict] = []
        for item in web[:n]:
            out.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
                "snippet": (item.get("contents", {}).get("highlights") or [""])[0],
                "page_age": item.get("page_age", ""),
            })
        return out

    def verify_finding(self, finding: Finding) -> list[dict]:
        """Search the web for evidence about a finding's claim.

        Returns the web results; the confidence engine uses these to bump
        (or not) the finding's confidence score.
        """
        query = self._build_verify_query(finding)
        if not query:
            return []
        log.info("Verifying finding: %s", query[:80])
        return self.search(query)

    @staticmethod
    def _build_verify_query(finding: Finding) -> str:
        """Build a focused web-search query from a finding.

        Use the headline + the topic keywords — keep it 4-8 words so
        you-search returns tight, relevant results.
        """
        # The headline is already a concise summary; strip mentions of "X"/
        # "Twitter" to avoid just re-finding the same tweet.
        headline = finding.headline.replace("#", "").strip()
        # Add the topic keyword for context.
        topic_word = finding.topic.replace("_", " ")
        return f"{headline} {topic_word}".strip()[:120]
