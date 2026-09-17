"""Configuration for AIOfferRadar (reads the `airadar:` section of config.yaml)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_SOURCES = ["twitter", "hackernews", "telegram", "mastodon", "rss",
                   "html", "reddit", "youtube", "threads", "bluesky", "instagram"]

DEFAULT_X_ACCOUNTS = [
    "AIHighlight", "LinusEkenstam", "mreflow", "theresanaiforthat",
    "OpenAI", "AnthropicAI", "GoogleDeepMind", "perplexity_ai",
    "MistralAI", "huggingface", "cursor_ai", "levelsio",
]

DEFAULT_SUBREDDITS = ["aisubscriptions", "appsumo", "toolsdeals", "discountools",
                      "SideProject", "LocalLLaMA", "PromptEngineering",
                      "generativeAI", "learnmachinelearning"]

DEFAULT_HN_QUERIES = ["Show HN free", "free tier AI", "free credits",
                      "lifetime deal AI", "open source model"]

DEFAULT_BLUESKY_QUERIES = ["free AI credits", "free tier", "lifetime deal AI"]

DEFAULT_TELEGRAM = ["Best_AI_tools", "DeepLearning_ai"]

DEFAULT_MASTODON_TAGS = ["ai", "opensource"]

DEFAULT_RSS = ["https://huggingface.co/blog/feed.xml",
               "https://blog.google/technology/ai/rss/"]

DEFAULT_HTML_WATCH = [
    "https://costgoat.com/pricing/openrouter-free-models",
    "https://free-model.com/",
    "https://zplatform.ai/ai-deal/",
    "https://appsumo.com/collections/features/ai/",
    "https://www.stacksocial.com/collections/artificial-intelligence",
    "https://freellmapihub.com/programs/startups",
    "https://simplycodes.com/category/artificial-intelligence",
    "https://felloai.com/ai-deals/",
]

DEFAULT_OFFER_KEYWORDS = [
    "free", "free tier", "free trial", "free credits", "free access",
    "no cost", "lifetime deal", "ltd", "promo code", "coupon",
    "100% off", "90% off", "discount", "giveaway", "beta access",
    "open source", "$0", "free forever", "student", "startup credits",
]


@dataclass
class AIConfig:
    enabled_sources: list = field(default_factory=lambda: list(DEFAULT_SOURCES))
    x_accounts: list = field(default_factory=lambda: list(DEFAULT_X_ACCOUNTS))
    subreddits: list = field(default_factory=lambda: list(DEFAULT_SUBREDDITS))
    hn_queries: list = field(default_factory=lambda: list(DEFAULT_HN_QUERIES))
    youtube_channel_ids: list = field(default_factory=list)
    bluesky_queries: list = field(default_factory=lambda: list(DEFAULT_BLUESKY_QUERIES))
    telegram_channels: list = field(default_factory=lambda: list(DEFAULT_TELEGRAM))
    mastodon_instance: str = "https://mastodon.social"
    mastodon_tags: list = field(default_factory=lambda: list(DEFAULT_MASTODON_TAGS))
    rss_feeds: list = field(default_factory=lambda: list(DEFAULT_RSS))
    html_watch: list = field(default_factory=lambda: list(DEFAULT_HTML_WATCH))
    threads_usernames: list = field(default_factory=list)
    instagram_usernames: list = field(default_factory=list)
    offer_keywords: list = field(default_factory=lambda: list(DEFAULT_OFFER_KEYWORDS))
    offer_signal_threshold: int = 3    # weighted-evidence floor for triage
    workers: int = 6                   # parallel source / verify workers
    min_offer_score: float = 0.35
    per_source_limit: int = 25
    request_timeout: int = 20
    delay_between_requests: float = 1.0
    db_path: str = "data/airadar.db"
    run_dir: str = "data/runs"
    digest_dir: str = "data/digests"
    top_n: int = 25


def load_ai_config(path="config.yaml") -> AIConfig:
    """Read the `airadar:` section; fall back to defaults when absent."""
    cfg = AIConfig()
    p = Path(path)
    if not p.exists():
        return cfg
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return cfg
    section = raw.get("airadar") or {}
    if not isinstance(section, dict):
        return cfg
    for key in (
        "enabled_sources", "x_accounts", "subreddits", "hn_queries",
        "youtube_channel_ids", "bluesky_queries", "telegram_channels",
        "mastodon_instance", "mastodon_tags", "rss_feeds", "html_watch",
        "threads_usernames", "instagram_usernames", "offer_keywords",
        "db_path", "digest_dir", "run_dir",
    ):
        if key in section and section[key] is not None:
            setattr(cfg, key, section[key])
    for key in ("min_offer_score", "per_source_limit", "request_timeout",
                "delay_between_requests", "top_n", "offer_signal_threshold",
                "workers"):
        if key in section and section[key] is not None:
            setattr(cfg, key, section[key])
    return cfg
