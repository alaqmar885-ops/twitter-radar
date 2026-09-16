# Documentation

This directory contains the research materials and sample outputs that informed
and demonstrate the TwitterRadar project.

## `research/` — Source research reports

These two deep-dive reports were the basis for the architecture. They are
included here for reference and future iteration.

| File | What it covers |
|------|----------------|
| `01_scraper_landscape.html` | Full landscape of X/Twitter scraping tools: twscrape, twikit/twifork, Playwright+GraphQL, commercial APIs, and dead/deprecated tools. Maps auth requirements, maintenance status, and rate limits. |
| `02_free_noauth_endpoints.html` | Surfaces 4 verified free no-auth endpoints (Syndication API, FxTwitter, oEmbed), anti-detect browsers (Camoufox, Patchright), and the smart 3-backend router pattern from `x-tweet-fetcher`. |

## `examples/` — Sample outputs from a real run

These files were produced by a live collection cycle on 2026-09-16.

| File | Description |
|------|-------------|
| `sample_digest.html` | Styled HTML digest from cycle 2 — 208 tweets collected from 11 AI-news accounts, 180 findings scored (4 VERIFIED, 242 HIGH) with You.com web-verification source links. Open in a browser to view. |
| `sample_twitter_radar.db` | SQLite snapshot of that run — `tweets` and `findings` tables with confidence scores, dedup state, and web sources. Inspect with `sqlite3 sample_twitter_radar.db ".tables"` |

## How these informed the build

- The **3-tier fallback router** (`twitter_radar/router.py`) directly implements
  the resilience pattern from report 02 — Tier 0 = free no-auth (FxTwitter,
  Syndication, oEmbed), Tier 1 = login-gated keyword search (twifork), Tier 2 =
  self-hosted HTML fallback (Nitter).
- The **confidence scoring engine** (`twitter_radar/confidence.py`) applies the
  source-credibility + cross-reference signals that both reports emphasize as
  critical for distinguishing real deal announcements from noise.
- The **ProtonVPN rotation manager** (`twitter_radar/vpn/proton.py`) uses the
  community CLI commands documented in the research (OpenVPN-based, headless,
  `c -r` for random server, `--cc` for country selection).
