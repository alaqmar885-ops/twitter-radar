# AIOfferRadar — FROZEN INTERFACE CONTRACT (v1)

Repo: D:\scrapper (twitter-radar). Package: `airadar/`. Entry: `run_radar.py`.
Python 3.12 venv: `D:\scrapper\.venv\Scripts\python.exe`. Required deps: httpx, beautifulsoup4, pyyaml.
Everything must be additive — the existing `twitter_radar` package and `run.py` must keep working.

Files are materialized by running a builder script with the venv python (Windows-safe: use pathlib,
write with encoding="utf-8"). Never crash a whole run because one source fails.

## airadar/models.py
```python
@dataclass
class Item:
    id: str              # "tw:<id>" / "yt:<videoId>" / "rd:<name>" / "hn:<objectID>" / "tg:<ch>:<msgid>" / "rss:<guid>" / "ma:<id>" / "th:<code>" / "ig:<shortcode>"
    platform: str        # twitter|youtube|reddit|hackernews|telegram|mastodon|rss|html|threads|instagram|bluesky
    author: str = ""
    title: str = ""
    text: str = ""
    url: str = ""
    created_at: str = ""          # ISO8601 when known, else ""
    metrics: dict = field(default_factory=dict)   # likes/points/views/etc
    source: str = ""              # source name that produced it (e.g. "youtube", "hn")
    query: str = ""               # watch term that matched
    raw: dict | None = None
    fetched_at: float = field(default_factory=time.time)
    @property
    def blob(self) -> str: ...    # lowercased title+text for matching

@dataclass
class Offer:
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    summary: str = ""
    offer_type: str = "other"     # free_tier|free_credits|free_trial|lifetime_deal|discount|open_source|giveaway|other
    value: str = ""               # "2 weeks free", "50% off", "$20 credits"
    promo_code: str = ""
    product: str = ""
    url: str = ""
    platforms: list[str] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    score: float = 0.0
    label: str = "LOW"            # LOW|MEDIUM|HIGH|VERIFIED
    link_ok: bool = False
    web_verified: bool = False
    web_sources: list[dict] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
```

## airadar/config.py
```python
@dataclass
class AIConfig:
    enabled_sources: list[str]
    x_accounts: list[str]
    subreddits: list[str]
    hn_queries: list[str]
    youtube_channel_ids: list[str]
    bluesky_queries: list[str]
    telegram_channels: list[str]
    mastodon_instance: str
    mastodon_tags: list[str]
    rss_feeds: list[str]
    html_watch: list[str]
    threads_usernames: list[str]
    instagram_usernames: list[str]
    offer_keywords: list[str]
    min_offer_score: float = 0.35
    per_source_limit: int = 25
    request_timeout: int = 20
    delay_between_requests: float = 1.0
    db_path: str = "data/airadar.db"
    digest_dir: str = "data/digests"
    top_n: int = 25

def load_ai_config(path="config.yaml") -> AIConfig   # reads the `airadar:` YAML section; sane defaults if absent
```

## airadar/store.py
```python
class Store:
    def __init__(self, db_path: str = "data/airadar.db"): ...
    def save_item(self, it: Item) -> bool          # INSERT OR IGNORE; True if new
    def seen_item(self, item_id: str) -> bool
    def save_offer(self, o: Offer) -> bool         # INSERT OR REPLACE by id
    def top_offers(self, limit=25, min_score=0.0) -> list[Offer]   # rebuild items from rows
    def stats(self) -> dict                        # {"items":n,"offers":n,"items_by_platform":{...},"offers_by_label":{...}}
    def close(self) -> None
```

## airadar/sources/base.py
```python
class BaseSource(abc.ABC):
    name: str = "base"; platform: str = "base"
    def __init__(self, cfg: AIConfig): self.cfg = cfg
    def available(self) -> bool: return True
    @abc.abstractmethod
    def fetch(self, limit: int = 25) -> list[Item]: ...   # MUST NOT raise; log + return []
```
Registry in `airadar/sources/__init__.py`: `SOURCE_REGISTRY: dict[str, type[BaseSource]]`.

## airadar/router.py
```python
class SourceRouter:
    def __init__(self, cfg: AIConfig): ...
    @property
    def sources(self) -> list[BaseSource]
    def available(self) -> dict[str, bool]
    def fetch_all(self, limit: int | None = None) -> list[Item]   # dedupe by Item.id across sources
```

## airadar/classify.py
```python
class OfferClassifier:
    def __init__(self, cfg: AIConfig): ...
    def is_offer(self, it: Item) -> bool
    def extract_promo_code(self, text: str) -> str
    def classify(self, it: Item) -> dict | None
        # None if not an offer; else {"offer_type","value","promo_code","product","summary"}
```

## airadar/scoring.py
```python
W_FREE=0.30; W_CORROB=0.25; W_CRED=0.20; W_RECENCY=0.15; W_LINK=0.10
class OfferScorer:
    def __init__(self, cfg: AIConfig): ...
    def score(self, o: Offer) -> Offer    # sets o.score (0..1) and o.label
    def label(self, score: float, verified: bool) -> str
```

## airadar/agents/base.py
```python
@dataclass
class AgentReport:
    agent: str; role: str; status: str = "ok"    # ok|skipped|error
    counts: dict = field(default_factory=dict); notes: list[str] = field(default_factory=list)
    elapsed: float = 0.0
@dataclass
class AgentContext:
    cfg: AIConfig; store: Store; router: SourceRouter
    classifier: OfferClassifier; scorer: OfferScorer; enricher: object | None
    offline: bool = False; items: list[Item] = field(default_factory=list)
    offers: list[Offer] = field(default_factory=list); log: logging.Logger = ...
class Agent(abc.ABC):
    name: str = "agent"; role: str = ""
    @abc.abstractmethod
    def run(self, ctx: AgentContext) -> AgentReport: ...
```

## airadar/agents/* (each subclasses Agent)
- scout.py  ScoutAgent      : router.fetch_all -> ctx.items, store.save_item each, counts per platform
- triage.py TriageAgent     : keep items where classifier.is_offer; counts in/out
- analyst.py AnalystAgent   : classify + cluster into Offer objects (cluster key = normalized product/url); ctx.offers
- verifier.py VerifierAgent : HTTP liveness on offer url (HEAD then GET) -> link_ok; optional You.com corroboration only if YDC_API_KEY set; offline => skip network, link_ok False
- curator.py CuratorAgent   : merge duplicate offers by product/url, scorer.score, store.save_offer, counts new/updated
- reporter.py ReporterAgent : write digest (html+md+json) to cfg.digest_dir via reusing twitter_radar.digest.report styling where reasonable; return path in counts
- team.py `class AgentTeam: __init__(cfg, offline=False); def run_once(self) -> dict` — runs agents in order, writes `data/runs/<ts>.json` report, returns stats dict

## run_radar.py (root)
```
python run_radar.py sources            # list sources + availability (live check)
python run_radar.py run [--offline]    # full agent-team cycle (offline = fixtures, no network)
python run_radar.py report             # re-render digest from store
python run_radar.py status             # store stats
```
UTF-8 stdio fix at top (same as run.py). `--config` flag like run.py.

## Rules
- Never raise out of a source/agent `fetch`/`run`; catch broadly, log, return partial.
- Polite: honour cfg.delay_between_requests between requests; per-request cfg.request_timeout.
- Windows-safe: no POSIX-only paths; use pathlib; force utf-8 when writing.
- Tests: `tests/test_airadar_smoke.py` must run with zero network using in-package fixtures
  (a FakeSource returning fixture Items), asserting >=1 Offer with score>0 and a promo code extracted.
