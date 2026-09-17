# AIOfferRadar — Architecture Spec (design draft)

Goal: extend the existing TwitterRadar repo into a **multi-platform** scraper whose single
purpose is finding **new free AI tool offers / free subscriptions / free credits / lifetime
deals**, run by an **agent team** (autonomous worker pipeline), self-hosted, no paid deps.

## Hard constraints
- Python 3.12, venv at `.venv`. Only stdlib + `httpx`, `beautifulsoup4`, `pyyaml` as REQUIRED deps.
  Any heavier dependency (yt-dlp, instaloader, threads-py, playwright) must be OPTIONAL and
  imported lazily with a graceful `available() == False` when missing.
- Do NOT break the existing `twitter_radar` package or the existing `run.py` subcommands
  (`once|loop|digest|status|test`). The new work is additive.
- Windows-friendly: force UTF-8 stdio already handled in run.py; keep it.

## Package layout (new, additive)
```
airadar/
  __init__.py
  models.py          # Item, Offer, SourceResult
  config.py          # AIConfig loader (reads config.yaml sections, overlays secrets.env)
  store.py           # SQLite: items + offers tables (data/airadar.db)
  sources/
    __init__.py      # SOURCE_REGISTRY
    base.py          # BaseSource ABC
    twitter.py       # wraps twitter_radar.router.Router -> Items
    youtube.py       # channel RSS (xml.etree)
    reddit.py        # /r/SUB/new.json + search.json (httpx)
    hackernews.py    # hn.algolia.com search_by_date
    rss.py           # generic RSS/Atom list
    threads.py       # best-effort public profile (document limits)
    instagram.py     # best-effort public (document limits)
  router.py          # SourceRouter: priority order + fallback + dedupe by item id
  classify.py        # OfferClassifier: offer detection + type + promo-code/number extraction
  scoring.py         # OfferScorer: 0..1 confidence (free-ness, credibility, recency, corroboration)
  enrich/youcom.py   # reuse twitter_radar.enrich.youcom.YouComEnricher if possible
  agents/
    __init__.py
    base.py          # Agent ABC, AgentContext, AgentReport, Blackboard
    scout.py         # ScoutAgent      -> pulls Items from sources
    triage.py        # TriageAgent     -> cheap keyword filter, drops non-offers
    analyst.py       # AnalystAgent    -> classify + extract (offer type, code, value)
    verifier.py      # VerifierAgent   -> link liveness + optional web corroboration
    curator.py       # CuratorAgent    -> dedupe/cluster/rank, persists offers
    reporter.py      # ReporterAgent   -> digest (html/md/json) + run report
    team.py          # AgentTeam       -> orchestrates the pipeline, emits run report
run_radar.py         # NEW entrypoint: `python run_radar.py run|sources|report|status`
```
(Alternative accepted: wire the same commands into the existing `run.py` under new
subcommands; either way keep existing subcommands working.)

## Data model
```python
@dataclass
class Item:            # one normalized post/video/thread/comment
    id: str            # platform-prefixed stable id, e.g. "yt:VIDEOID", "rd:t3_xxx", "tw:1234"
    platform: str      # twitter|youtube|reddit|hackernews|rss|threads|instagram
    author: str
    text: str          # title + body collapsed
    url: str
    created_at: str    # ISO8601 if known
    metrics: dict      # likes/upvotes/views/score (platform-specific)
    raw: dict|None
    fetched_at: float

@dataclass
class Offer:           # a deduped, scored "free AI thing" finding
    id: str
    title: str
    summary: str
    offer_type: str    # free_tier|free_credits|free_trial|lifetime_deal|discount|open_source|giveaway|other
    value: str         # extracted "2 weeks free", "50% off", "$20 credits"
    promo_code: str
    url: str
    items: list[Item]
    topics: list[str]
    score: float
    label: str         # LOW|MEDIUM|HIGH|VERIFIED
    web_verified: bool
    web_sources: list[dict]
    first_seen: float
    last_updated: float
```

## Agent team (roles + contract)
Each agent: `name`, `role`, `run(ctx) -> AgentReport(agent, status, counts, notes, elapsed)`.
The `AgentTeam` runs stages in order and writes a machine-readable run report
(`data/runs/<ts>.json`) + logs. Stages:

1. **ScoutAgent** (one instance per enabled source, run in parallel/threads)
   - pulls latest Items from each source per config (accounts, channels, subs, queries, feeds)
   - writes Items to store (dedupe by id), returns counts per platform.
2. **TriageAgent** — cheap regex/keyword gate: keep Items that look like an offer
   ("free", "free tier", "100% off", "coupon", "promo", "credits", "giveaway",
   "lifetime", "$0", "open source", "beta access"...). Threshold configurable.
3. **AnalystAgent** — classify offer_type; extract `value` (amount/%/duration),
   promo code (uppercase code near "code"/"promo"), canonical product name; build Offers
   by clustering Items that share a product signature.
4. **VerifierAgent** — for Offers above a floor: HTTP liveness check on the offer URL
   (HEAD then GET, follow redirects, detect 404/dead), and optional web corroboration
   via You.com enricher if YDC_API_KEY is set. Records evidence, never invents it.
5. **CuratorAgent** — dedupe/cluster across platforms, merge corroborating Items,
   compute final score/label, persist Offers, mark new vs seen.
6. **ReporterAgent** — render the digest (reuse TwitterRadar dark-theme style) +
   a run report listing each agent's contribution.

## Scoring (offers)
Start from TwitterRadar's 5-signal idea, adapted:
- free_strength (is it genuinely free/0-cost?) 0.30
- corroboration (independent Items across platforms/authors) 0.25
- source_credibility (platform + author signals) 0.20
- recency 0.15
- link_verified / web_verified 0.10
Labels: VERIFIED >=0.80 & web-verified, HIGH >=0.60, MEDIUM >=0.40, LOW <0.40.

## Config additions (config.yaml, new sections; keep old ones)
```yaml
airadar:
  enabled_sources: [twitter, youtube, reddit, hackernews, rss, threads, instagram]
  youtube_channel_ids: []      # UCxxxx ids
  subreddits: [artificial, ArtificialInteligence, SideProject, deals, freebies]
  hn_queries: ["free tier AI", "free credits", "Show HN AI"]
  rss_feeds: []                # vendor blogs / deal sites
  threads_usernames: []
  instagram_usernames: []
  offer_keywords: [...]
  min_offer_score: 0.35
  per_source_limit: 30
```

## Deliverables in repo
- the `airadar/` package + entrypoint
- `docs/research/03_platform_scraping_2026.md` (from research agent A)
- `docs/research/04_free_ai_offer_sources.md` (from research agent B)
- `AGENT_TEAM.md` documenting each agent, its role, inputs/outputs, and files
- README section describing the multi-platform radar + agent team + setup
- updated `config.yaml` (or `config.example.yaml`) with the new sections
- tests/smoke: offline unit checks for classifier + scorer + a mocked source

## Acceptance evidence (offline, no network required)
- `.venv\Scripts\python.exe -m compileall airadar run_radar.py` exit 0
- `.venv\Scripts\python.exe -c "import airadar, airadar.agents.team"` exit 0
- `.venv\Scripts\python.exe run_radar.py sources` lists sources with availability
- a bundled offline smoke test (mocked payloads) that runs the full agent pipeline
  end-to-end on fixture data and asserts an Offer comes out with a score.
- existing `run.py status` still exits 0 (no regression).
```
