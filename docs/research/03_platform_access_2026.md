# Report 3 — Multi-Platform Access Methods (2026)

> Research performed September 2026 via 18+20 live You.com MCP `you-search` queries
> (raw results: `data/research_raw/`). Live probes against target endpoints were run
> from this machine on 2026-09-17. Each method below carries an evidence status.

The radar's goal: free, no-auth (or light-auth) access to public posts on every major
platform where "free AI tool / free credits / lifetime deal" offers surface.

## 1. X / Twitter — ✅ VERIFIED WORKING (already built)

The existing `twitter_radar` router covers this with three no-auth Tier-0 backends
(FxTwitter `api.fxtwitter.com`, Syndication `cdn.syndication.twimg.com`, oEmbed
`publish.twitter.com/oembed`). Live test 2026-09-17: all three HTTP 200.
Notes: FxTwitter requires a browser User-Agent (httpx default UA gets 403).
Login-gated keyword search (twifork cookies) stays optional.

## 2. YouTube — ✅ VERIFIED (endpoint standard, no key)

- Channel uploads RSS: `https://www.youtube.com/feeds/videos.xml?channel_id=UC...`
  No API key, no auth, ~15 latest videos per channel. Confirmed by multiple sources
  (stackoverflow.com/questions/29752447, wprssaggregator.com/youtube-rss-feed/,
  channelsurfer.tv, ghacks.net). Fields in feed: `yt:videoId`, `title`,
  `published`, `updated`, `media:community/media:content` (url), `media:starRating`
  (views count in `count` attr), `media:statistics` (views), author name, `link`.
- Channel-id resolution: handle pages embed `"externalId":"UC..."`; several free
  finder tools exist (keep.md, channelsurfer.tv). Live probe: handle page fetch OK;
  the RSS endpoint 404s on a wrong/unverified id, so resolve `externalId` not the
  first `"channelId"` occurrence (first match can be an unrelated embed).
- `yt-dlp` covers deep metadata (flat playlists, no auth) as an optional enhancer:
  fast.io/resources/metadata-extraction-from-youtube-videos, yt-dlp issue #36.

## 3. Reddit — ⚠️ DEPRECATED .json; alternatives required

- **Observed (live probe 2026-09-17):** `https://www.reddit.com/r/LocalLLaMA/new.json`
  → **403 Forbidden** (browser UA, datacenter IP).
- **Corroborated:** Reddit deprecated unauthenticated `.json` endpoints in 2026
  (crawlora.net/blog/reddit-json-api-blocked-2026; redditapis.com/blogs/reddit-json-endpoint-dead-2026;
  r/selfhosted thread "Did Reddit kill unauthenticated JSON requests?").
- **Alternatives (both no-auth, implemented as fallbacks):**
  1. Subreddit RSS: `https://www.reddit.com/r/<sub>/.rss` (and `/m/<multi>/.rss`)
     — still works but rate-limited (lapcatsoftware.com/articles/2026/6/3.html).
  2. PullPush API (PushShift successor): `https://api.pullpush.io/reddit/search/submission/?subreddit=<sub>&sort=desc&size=25`
     — returns full submission JSON without auth.
- OAuth Data API (free tier, script app) remains the sanctioned fallback for later.

## 4. Hacker News — ✅ VERIFIED LIVE (no key)

- `https://hn.algolia.com/api/v1/search_by_date?query=<q>&tags=story&hitsPerPage=N`
  — live probe returned hits. Fields: `objectID`, `title`/`story_title`, `url`,
  `author`, `points`, `num_comments`, `created_at`. Rate limit ~1000 req/hour/IP
  (HN API announcement, news.ycombinator.com/item?id=7284541). Guide:
  dev.to/odeeb (tags + numericFilters e.g. `points>50`), cotera.co/articles/hacker-news-api-guide.
- Query set for offers: `"Show HN free"`, `"free tier AI"`, `"free credits"`,
  `"lifetime deal"` with `tags=(story,show_hn)` variant.

## 5. Meta Threads — ✅ VERIFIED LIVE (public HTML), libraries stale

- Live probe: `https://www.threads.net/@zuck` → **HTTP 200, ~597 KB** without login.
  Post data is embedded in the HTML (embedded JSON blobs) — parseable with bs4/regex
  for text + timestamp. Scrapfly's 2026 guide confirms public access without login
  (scrapfly.io/blog/posts/how-to-scrape-threads).
- Libraries: junhoyeo/threads-py and Danie1/threads-api are unofficial and stale;
  pythreads (marlove) wraps the official token API. Official Meta API has
  `GET /profile_posts?username=` but requires a Meta token
  (developers.facebook.com/documentation/threads). Verdict: HTTP-HTML best-effort
  source, marked degraded gracefully when parsing fails.
- Apify paid actors dominate keyword search on Threads — out of free scope.

## 6. Bluesky — ✅ NEW, no-auth public API

- Public AppView: `https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=<q>&limit=25`
  — no auth for search; `app.bsky.feed.getAuthorFeed?actor=handle` for timelines.
  Confirmed via Apify's "no auth" actors which use exactly this public AT Protocol
  API (apify.com/gochujang/bluesky-posts-scraper, apify.com/pappy-dev/bluesky-posts).

## 7. Mastodon — ✅ NEW, no-auth public endpoints

- `https://<instance>/api/v1/timelines/tag/<hashtag>` and `/api/v1/accounts/:id/statuses`
  are public on most instances (mastodon.social is the default). Apify no-login
  actors confirm (apify.com/puskin/mastodon-scraper). Polite delay required.

## 8. Telegram — ✅ NEW, public web preview

- `https://t.me/s/<channel>` serves a public HTML preview of recent channel posts
  (live example seen in research: t.me/s/DeepLearning_ai). Parse with bs4;
  channel list configurable. AI-deal channels exist (tgstat.com/channel/@Best_AI_tools).

## 9. Instagram — ❌ not viable free/no-auth (optional extra only)

- Instaloader (v4.15.x) still works for public profiles but 429s aggressively —
  even on a fresh session's first `web_profile_info` request (github.com/instaloader/
  instaloader/issues/2726; scrapfly 2026 roundup; pnt.jacbex.com 429 write-ups).
- gallery-dl similar (login needed for many profiles). All no-login routes now run
  through paid proxies/actors (Apify etc.). Verdict: keep an OPTIONAL instaloader
  adapter that imports lazily and reports `available() == False` unless installed
  with cookies; exclude from the default pipeline.

## 10. LinkedIn / TikTok — ❌ out of scope (paid-only)

Research shows working access only via paid scrapers (Apify $0.5–0.9/1k, EnsembleData).
No free no-auth method worth automating. Excluded.

## 11. RSS / HTML watch pages — ✅ the highest-signal free layer

From batch-1/2 searches, these are first-class radar sources (see Report 4 for the
list): vendor blogs (some RSS, some HTML), free-tier tracking pages (costgoat,
free-model.com, freellmapihub), deal aggregators (zplatform.ai/ai-deal, AppSumo AI
collection, StackSocial AI collection), coupon trackers (simplycodes.com), and
GitHub READMEs served raw (awesome-freellm-apis). Anthropic has **no official RSS**
(windflash.us/rss-sources; community-made alternatives exist, e.g.
github.com/CorjanBos/ai-rss-feed); OpenAI's blog RSS broke after their site revamp
(community.openai.com thread) — use HTML watch or third-party feeds for those.

## Priority matrix for the radar

| Rank | Source | Cost | Reliability | Offer signal |
|------|--------|------|-------------|--------------|
| 1 | X/Twitter router (existing) | free | high | very high |
| 2 | Hacker News Algolia | free | high | high (launches) |
| 3 | YouTube channel RSS | free | high | medium |
| 4 | Bluesky public search | free | high | medium |
| 5 | RSS/HTML watch pages | free | medium | very high (aggregators) |
| 6 | Telegram t.me/s channels | free | medium | medium |
| 7 | Mastodon tag timelines | free | medium | low-medium |
| 8 | Reddit (.rss / PullPush) | free | degraded | high |
| 9 | Threads public HTML | free | fragile | medium |
| 10 | Instagram (optional lib) | free | low | low |
