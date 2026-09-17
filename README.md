# 📡 TwitterRadar — Self-Hosted X/Twitter Intelligence Scraper

A **free, self-hosted** Twitter/X scraper that monitors top accounts, discovers AI deals/offers/launches, scores them for **confidence**, and verifies claims against the web via **You.com MCP** — all with **ProtonVPN headless IP rotation**.

Built from two deep-research reports on the 2026 Twitter-scraping landscape. The architecture uses the **multi-backend fallback router** pattern (inspired by x-tweet-fetcher's 3-backend design) so no single endpoint failure can bring the system down.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        SCHEDULER (cron / daemon)             │
│   rotates ProtonVPN IP before each cycle                     │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼───────────┐     ┌─────────────────────────────────┐
│   COLLECTOR          │     │  ROUTER (fallback priority)      │
│  search + timelines  │────►│  1. FxTwitter (no-auth) ★       │
│  classify → cluster  │     │  2. Syndication (no-auth) ★      │
│  score + web-verify   │     │  3. oEmbed (official) ★         │
│  save → SQLite        │     │  4. twifork (keyword, login)     │
│  render → HTML digest │     │  5. Nitter (self-hosted)         │
└──────────┬───────────┘     └──────────────┬──────────────────┘
           │                                 │
   ┌───────▼───────┐          ┌──────────────▼───────┐
   │ CONFIDENCE    │          │  You.com MCP         │
   │ ENGINE        │◄─────────│  you-search verifies │
   │ 5-signal score│          │  claims against web  │
   └───────────────┘          └──────────────────────┘
```

### Tiered backend strategy

| Tier | Backend | Auth | Capabilities | Status |
|------|--------|------|-------------|--------|
| 0 | **FxTwitter** | None | Timelines (no login!), single tweets (richest payload) | ✅ Live-verified |
| 0 | **Syndication API** | None | Single tweets + thread reconstruction (`parent` nesting) | ✅ Live-verified |
| 0 | **oEmbed** | None (official) | Minimal fields, X-sanctioned | ✅ Live-verified |
| 1 | **twifork** | Login cookies | **Keyword search** (the only login-gated capability) | Optional |
| 2 | **Nitter** | None (self-hosted) | Timelines, search (HTML scraping) | Optional fallback |

> ★ = always works, no setup needed. Tier 0 alone covers **account monitoring + tweet enrichment + threads** with zero cost and zero auth. Tier 1 adds keyword search (needs a throwaway account's cookies). Tier 2 is the last-resort fallback.

### Confidence scoring (5 signals)

| Signal | Weight | What it measures |
|--------|--------|------------------|
| Source credibility | 30% | Verified badge + follower tier (1-5) |
| Cross-references | 25% | Multiple independent accounts reporting same claim |
| Web verification | 25% | You.com `you-search` finds corroborating sources |
| Recency | 10% | <1hr=1.0, <1day=0.8, <1week=0.3 |
| Engagement | 10% | Log-scaled likes + replies (×3) + quotes (×2) |

Labels: **VERIFIED** ≥80% + web-confirmed · **HIGH** ≥60% · **MEDIUM** ≥40% · **LOW** <40%

## Quick start

```bash
# 1. Install Python deps (the no-auth tier works immediately)
pip install -r requirements.txt

# 2. Set your You.com API key (for web verification)
export YDC_API_KEY=ydc-sk-...

# 3. Test the free endpoints
python3 run.py test

# 4. Run one collection cycle → produces an HTML digest
python3 run.py once

# 5. Run as a daemon (cycles every 3 hours)
python3 run.py loop
```

Or via cron:
```bash
0 */3 * * * cd /path/to/twitter-radar && python3 run.py once --config config.yaml
```

## Full setup (VPS with VPN + keyword search)

```bash
# ProtonVPN headless IP rotation
sudo pip3 install protonvpn-cli
sudo protonvpn init          # OpenVPN creds from account.protonvpn.com/account
export PVPN_INIT_DONE=1

# Keyword search (optional — needs throwaway account cookies)
pip install "twifork[impersonate]"
# Export ct0 + auth_token from a throwaway X account → cookies.json
export TR_TWIFORK_COOKIES=cookies.json

# Nitter fallback (optional)
docker run -d -p 8788:8080 --name nitter zedeus/nitter:latest
export TR_NITTER_URL=http://127.0.0.1:8788

bash scripts/setup.sh    # verifies everything
```

## Commands

| Command | What it does |
|---------|-------------|
| `run.py test` | Live-test the 3 free no-auth endpoints |
| `run.py once` | One full cycle: collect → classify → score → verify → store → digest |
| `run.py loop` | Daemon: cycles every `interval_minutes` with VPN rotation |
| `run.py digest` | Re-render a digest from stored data (no new collection) |
| `run.py status` | Show store stats, VPN status, You.com API key status |

## Configuration

Edit `config.yaml`:

```yaml
# Accounts to monitor (no-auth FxTwitter timelines)
watch_accounts: [levelsio, OpenAI, AnthropicAI, huggingface, ...]

# Keyword topics for classification + (optional) twifork search
topics:
  free_ai_services:
    keywords: ["free AI tool", "free credits AI", ...]
    finding_type: free_ai_service

# VPN rotation
vpn:
  countries: [US, UK, NL, DE, JP, ...]
  rotate_every_batches: 1

# Schedule
schedule:
  interval_minutes: 180
```

## How the free endpoints work

Based on the research reports, these 4 undocumented/official endpoints return structured tweet JSON with **no API key, no login, no cost**:

| Endpoint | URL | Best for |
|----------|-----|----------|
| **Syndication API** | `cdn.syndication.twimg.com/tweet-result?id={id}&token=0` | Single tweets + thread reconstruction (reply includes `parent`) |
| **FxTwitter** | `api.fxtwitter.com/{user}/status/{id}` | Richest payload: followers, bio, media, quotes |
| **FxTwitter timeline** | `api.fxtwitter.com/2/profile/{handle}/statuses` | Free user timeline — no login (rare find) |
| **oEmbed** | `publish.twitter.com/oembed?url=...` | Official, sanctioned, unlimited |

> ⚠ These are undocumented/volunteer endpoints. The router's fallback design means if one goes down, the others take over. Never trust a single endpoint.

## ProtonVPN headless rotation

Uses the community `protonvpn-cli` (OpenVPN-based, no GUI required):

```bash
protonvpn c -r              # random server
protonvpn c --cc NL          # fastest in Netherlands
protonvpn d                  # disconnect
protonvpn s                  # status + IP
```

The `ProtonVPNManager` rotates through a random-shuffled country list before each collection batch. If VPN is unavailable (e.g., in a container without tun access), it logs a warning and continues — but you should disable login-based backends (twifork) to avoid running on a known IP.

## What a digest looks like

Each cycle produces an HTML digest in `data/digests/` with:
- **Stats grid** (tweets collected, findings, verified count)
- **Finding cards** sorted by confidence, each showing:
  - Confidence badge (VERIFIED / HIGH / MEDIUM / LOW) + numeric score
  - Headline + summary
  - Supporting tweets (author, engagement, link to X)
  - Web-verified sources (You.com corroboration links)
  - Topic + finding-type tags

## Project layout

```
twitter-radar/
├── run.py                         # entry point
├── config.yaml                    # topics, accounts, VPN, schedule
├── requirements.txt
├── docker-compose.yml             # Nitter fallback container
├── scripts/setup.sh               # VPS setup script
└── twitter_radar/
    ├── models.py                  # Tweet, Author, Finding, BackendResult
    ├── config.py                  # YAML + env config loader
    ├── router.py                  # multi-backend fallback router
    ├── collector.py               # collection + classification pipeline
    ├── confidence.py              # 5-signal confidence engine
    ├── store.py                   # SQLite (tweets + findings, deduped)
    ├── scheduler.py               # cron-friendly loop + VPN rotation
    ├── backends/                  # fxtwitter, syndication, oembed, twifork, nitter
    ├── vpn/proton.py              # ProtonVPN CLI manager
    ├── enrich/youcom.py           # You.com MCP web verification
    └── digest/report.py           # HTML/Markdown/JSON renderer
```

## Legal & ToS note

Scraping **public** Twitter data is generally legal in the US (hiQ v. LinkedIn), but it breaches X's Terms of Service. This tool only accesses **public** data via endpoints that don't require login (Tier 0) or via your own account's cookies (Tier 1). Don't touch protected accounts, DMs, or anything behind a login you don't own. Not legal advice — consult a lawyer for your use case.

## License

MIT — same as the upstream research reports' source projects.


## AIOfferRadar - multi-platform free-AI-offer radar + agent team

Beyond X/Twitter, `airadar/` adds a multi-platform collector and an autonomous
agent team whose job is finding **free AI tools, credits, free tiers, promo codes
and lifetime deals** across platforms.

**Platforms:** twitter, youtube (channel RSS), reddit (old.reddit .rss / PullPush),
hackernews (Algolia), telegram (t.me/s preview), mastodon (tag timelines),
rss + generic HTML watch pages (deal sites), threads (public HTML, best-effort),
bluesky (public API), instagram (optional, lazy).

**Agent team:** Scout -> Triage -> Analyst -> Verifier -> Curator -> Reporter.
See [AGENT_TEAM.md](AGENT_TEAM.md).

```bash
python run_radar.py sources        # sources + live availability
python run_radar.py run            # full multi-platform cycle
python run_radar.py run --offline  # zero-network smoke run
python run_radar.py report         # re-render digest
python run_radar.py status         # store stats
```

Research backing: [docs/research/03_platform_access_2026.md](docs/research/03_platform_access_2026.md)
and [docs/research/04_free_ai_offer_sources.md](docs/research/04_free_ai_offer_sources.md).
