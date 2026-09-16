"""Configuration loader for TwitterRadar.

Loads a YAML config and overlays environment variables (secrets) so the
same file works in dev and on a VPS.  All secrets come from env, never YAML.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# Default curated accounts that frequently post about AI deals, launches,
# and free offerings.  These are monitored via the no-auth FxTwitter timeline
# endpoint, so no login is required to pull their latest tweets.
DEFAULT_WATCH_ACCOUNTS: list[str] = [
    "levelsio",          # indie hacker, posts AI tool deals/launches
    "xdevelopers",       # X platform / API updates
    "OpenAI",            # official OpenAI
    "AnthropicAI",       # official Anthropic / Claude
    "GoogleDeepMind",    # Gemini / DeepMind
    "huggingface",       # open-source models, free tier offers
    "cursor_ai",         # Cursor editor
    "peraborodin",       # AI tools aggregator
    "AIBreakfast",       # daily AI news digest
    "TheAIGRID",         # AI news
    "MattVidpro",        # AI tool reviews / free tiers
    "emollick",          # Ethan Mollick, AI use-cases
]

# Keyword groups — each is a "topic" the radar searches for.
DEFAULT_TOPICS: dict[str, dict] = {
    "free_ai_services": {
        "keywords": [
            "free AI tool",
            "free credits AI",
            "free tier AI",
            "free API access",
            "no cost AI",
            "free LLM access",
        ],
        "finding_type": "free_ai_service",
    },
    "subscription_offers": {
        "keywords": [
            "subscription discount",
            "lifetime deal AI",
            "AI promo code",
            "free trial unlimited",
            "limited time offer AI",
            "save on AI subscription",
        ],
        "finding_type": "subscription_offer",
    },
    "ai_launches": {
        "keywords": [
            "just launched AI",
            "new AI model release",
            "open source model",
            "AI announcement",
            "now available AI",
        ],
        "finding_type": "launch",
    },
    "ai_discounts": {
        "keywords": [
            "AI discount code",
            "deal on AI",
            "percent off AI",
            "black friday AI",
            "education discount AI",
        ],
        "finding_type": "discount",
    },
}

DEFAULT_VPN_COUNTRIES: list[str] = [
    "US", "UK", "NL", "DE", "JP", "CA", "FR", "CH", "SE", "SG",
]


@dataclass
class VPNConfig:
    enabled: bool = True
    countries: list[str] = field(default_factory=lambda: list(DEFAULT_VPN_COUNTRIES))
    rotate_every_batches: int = 1     # rotate IP after N collection batches
    # OpenVPN credentials come from env (account.protonvpn.com/account):
    protonvpn_bin: str = "protonvpn"
    init_done: bool = False


@dataclass
class YouComConfig:
    enabled: bool = True
    api_key_env: str = "YDC_API_KEY"
    mcp_url: str = "https://api.you.com/mcp"
    max_verify_results: int = 4
    # Min credibility to even attempt web verification (skip low-signal tweets)
    min_credibility_for_verify: float = 0.35


@dataclass
class ScheduleConfig:
    interval_minutes: int = 180       # run a full collection cycle every N min
    per_backend_timeout: int = 20    # seconds per HTTP call
    delay_between_requests: float = 1.5
    max_tweets_per_topic: int = 40
    max_tweets_per_account: int = 25


@dataclass
class Config:
    # General
    watch_accounts: list[str] = field(default_factory=lambda: list(DEFAULT_WATCH_ACCOUNTS))
    topics: dict[str, dict] = field(default_factory=lambda: dict(DEFAULT_TOPICS))
    data_dir: str = "data"
    db_path: str = "data/twitter_radar.db"

    # Backends — order = priority.  Router tries in this order, falls back.
    backend_order: list[str] = field(default_factory=lambda: [
        "fxtwitter",       # no-auth timelines + rich single tweets
        "syndication",     # no-auth single tweets + thread reconstruction
        "oembed",          # no-auth, official, limited fields
        "twifork",         # login-based keyword search (needs cookies)
        "nitter",          # self-hosted fallback
    ])

    # Auth (optional — only for twifork keyword search)
    twifork_cookies: str = ""        # path to cookies.json, or "" to skip
    nitter_url: str = ""             # e.g. http://127.0.0.1:8788, or "" to skip

    vpn: VPNConfig = field(default_factory=VPNConfig)
    youcom: YouComConfig = field(default_factory=YouComConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)

    # Digest
    digest_dir: str = "data/digests"
    digest_format: str = "html"       # "html" | "markdown" | "json"
    top_n_findings: int = 20

    @property
    def youcom_api_key(self) -> str:
        return os.environ.get(self.youcom.api_key_env, "")


def _coerce(data: dict, default: Any):
    """Shallow-merge a dict into a dataclass field default."""
    return data if data else default


def load_config(path: str | Path = "config.yaml") -> Config:
    """Load YAML config, apply defaults, overlay env for secrets."""
    path = Path(path)
    cfg = Config()

    if not path.exists():
        return cfg

    raw: dict = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    cfg.watch_accounts = raw.get("watch_accounts", cfg.watch_accounts)
    cfg.topics = raw.get("topics", cfg.topics)
    cfg.data_dir = raw.get("data_dir", cfg.data_dir)
    cfg.db_path = raw.get("db_path", cfg.db_path)
    cfg.backend_order = raw.get("backend_order", cfg.backend_order)
    cfg.twifork_cookies = os.environ.get(
        "TR_TWIFORK_COOKIES", raw.get("twifork_cookies", "")
    )
    cfg.nitter_url = os.environ.get(
        "TR_NITTER_URL", raw.get("nitter_url", "")
    )
    cfg.digest_dir = raw.get("digest_dir", cfg.digest_dir)
    cfg.digest_format = raw.get("digest_format", cfg.digest_format)
    cfg.top_n_findings = int(raw.get("top_n_findings", cfg.top_n_findings))

    # VPN
    vpn = raw.get("vpn", {}) or {}
    cfg.vpn.enabled = vpn.get("enabled", cfg.vpn.enabled)
    cfg.vpn.countries = vpn.get("countries", cfg.vpn.countries)
    cfg.vpn.rotate_every_batches = int(
        vpn.get("rotate_every_batches", cfg.vpn.rotate_every_batches)
    )
    cfg.vpn.protonvpn_bin = vpn.get("protonvpn_bin", cfg.vpn.protonvpn_bin)
    cfg.vpn.init_done = bool(
        os.environ.get("PVPN_INIT_DONE", vpn.get("init_done", False))
    )

    # You.com
    yc = raw.get("youcom", {}) or {}
    cfg.youcom.enabled = yc.get("enabled", cfg.youcom.enabled)
    cfg.youcom.api_key_env = yc.get("api_key_env", cfg.youcom.api_key_env)
    cfg.youcom.mcp_url = yc.get("mcp_url", cfg.youcom.mcp_url)
    cfg.youcom.max_verify_results = int(
        yc.get("max_verify_results", cfg.youcom.max_verify_results)
    )
    cfg.youcom.min_credibility_for_verify = float(
        yc.get("min_credibility_for_verify", cfg.youcom.min_credibility_for_verify)
    )

    # Schedule
    sch = raw.get("schedule", {}) or {}
    cfg.schedule.interval_minutes = int(
        sch.get("interval_minutes", cfg.schedule.interval_minutes)
    )
    cfg.schedule.per_backend_timeout = int(
        sch.get("per_backend_timeout", cfg.schedule.per_backend_timeout)
    )
    cfg.schedule.delay_between_requests = float(
        sch.get("delay_between_requests", cfg.schedule.delay_between_requests)
    )
    cfg.schedule.max_tweets_per_topic = int(
        sch.get("max_tweets_per_topic", cfg.schedule.max_tweets_per_topic)
    )
    cfg.schedule.max_tweets_per_account = int(
        sch.get("max_tweets_per_account", cfg.schedule.max_tweets_per_account)
    )

    return cfg
