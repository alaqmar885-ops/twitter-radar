# HANDOFF — AIOfferRadar (twitter-radar repo)

**Status:** working, tested, and verified live. Last updated 2026-09-17.
**Repo:** https://github.com/alaqmar885-ops/twitter-radar (private)
**Workspace:** `D:\scrapper` · Python 3.12 venv at `.venv`
**Owner context:** the goal is finding *free* AI offers (free tiers, credits, promo codes,
lifetime deals) that are reachable and payable from India, with honest evidence for every claim.

---

## 1. Quick start

```bash
cd D:\scrapper
.venv\Scripts\python.exe run_radar.py doctor      # preflight: config, secrets, deps, sources
.venv\Scripts\python.exe run_radar.py run         # collect across all platforms (parallel)
.venv\Scripts\python.exe run_radar.py verify      # refine + verify every finding (--workers N)
.venv\Scripts\python.exe run_radar.py notify      # alert on the best findings (--min-score 0.7)
.venv\Scripts\python.exe scripts\interactive_report.py   # interactive audit HTML
.venv\Scripts\python.exe scripts\discover_providers.py   # find providers nobody told us about
```

`run_radar.py` auto-loads `secrets.env`, so no shell setup is needed.
Secrets: `YDC_API_KEY` (You.com MCP, web verification + page extraction),
optional `ALERT_WEBHOOK_URL`, optional `DISCOVER_MAX` (discovery candidate cap, default 60).

The legacy X-only tool still works unchanged: `python run.py {once,loop,digest,status,test}`.

---

## 2. Architecture

```
airadar/
  models.py        Item, Offer
  config.py        AIConfig (reads the `airadar:` block of config.yaml)
  signals.py       weighted offer-evidence engine + AI-relevance scoring
  classify.py      is_offer / classify (offer type, value, promo code, product)
  verify.py        per-page verification: free / no-card / card / UPI / India evidence
  scoring.py       5-signal score + verdict-weighted final score
  refine.py        title hygiene + field refinement
  store.py         SQLite: items, offers (verdict), verifications
  router.py        SourceRouter (parallel fetch, per-source fallback)
  sources/         11 platform sources (see below)
  agents/          Scout → Triage → Analyst → Verifier → Curator → Reporter
run_radar.py       CLI: doctor | sources | run | verify | notify | report | status
run.py             legacy X-only CLI (untouched)
scripts/           research drivers, report generators, discovery
twitter_radar/     original X engine (router/backends/store/confidence/digest)
```

### Platform sources (live status 2026-09-17)

| Source | Method | Status |
|---|---|---|
| twitter | existing no-auth router (FxTwitter/Syndication/oEmbed) | working |
| hackernews | Algolia search_by_date | working |
| telegram | `t.me/s/<channel>` public preview | working |
| mastodon | tag timelines | working |
| rss | vendor blogs (Hugging Face, Google AI) | working |
| html | watch pages — **also captures the page itself when it is the offer** | working |
| reddit | old.reddit `.rss` → PullPush | blocked (login redirect) |
| youtube | channel RSS (id resolution works; feed blocked from this host) | blocked here |
| bluesky | `public.api.bsky.app` | 403 from this host |
| threads | public HTML | coded, no handles configured |
| instagram | optional lazy (instaloader) | not installed |

---

## 3. Evidence model — read this before trusting a number

Every finding carries a **verdict** and the raw evidence behind it. The same evidence
is exposed in the interactive report so a human can override the machine.

| Verdict | Means |
|---|---|
| `VERIFIED_NO_CC` | page shows a specific free signal **and** explicit no-card wording |
| `VERIFIED` | page shows a specific free signal (card policy unstated) |
| `PARTIAL` | only medium signals (pricing/trial/discount/credits) |
| `CARD_REQUIRED` | page requires a card and has no no-card evidence |
| `DERIVATIVE` | discussion/aggregator page (HN, Reddit…) — **not authoritative evidence** |
| `WEAK` / `NOT_AN_OFFER` | only the bare word "free", or no offer signal at all |
| `UNREACHABLE` / `NO_URL` | link dead or missing |

Rules that matter and are easy to regress:
1. **Negation.** `"no credit card required"` must never count as card-required evidence.
   `find_card_signals()` handles this — do not replace it with substring matching.
2. **Precedence.** Explicit no-card wording beats generic card wording (pricing pages
   list "free tier: no card / Pro: card required" — the free tier still counts).
3. **Discussion pages are never proof.** Comments contain "free tier" too.
4. **AI relevance is required.** Distinct AI-concept scoring (threshold `min_ai_relevance`,
   default 2). A single mention of "AI" is not enough — that is what let a hardware
   telemetry product rank first.
5. **Score respects evidence.** `OfferScorer.apply_verdict()` blends the raw score with
   the verdict and hard-caps unproven findings at 35%, forcing label LOW.
6. **A term is a lead, not proof.** Verification is a static HTTP fetch (plus an MCP
   page-extraction fallback); it cannot see a checkout flow.

---

## 4. Current numbers (2026-09-17, single cycle each)

```
items collected       ~960
offers stored         247   (deduplicated by URL)
VERIFIED_NO_CC         80
VERIFIED               31
PARTIAL                15
CARD_REQUIRED           1   (Hoplite — genuinely gates its trial)
DERIVATIVE              8
WEAK / NOT_AN_OFFER    75
NO_URL / UNREACHABLE   37
no-card evidence       90 findings
UPI evidence           19 findings
India evidence         39 findings
```

Verification throughput: 537 findings in ~115 s with `--workers 8` (was ~600 s serial).

---

## 5. Data layout

```
data/airadar.db            items, offers (with verdict), verifications (raw evidence)
data/digests/              digest html/md/json per cycle
data/verified/             verified_*, no_cc_*, frontier_*, india_* reports
data/discovered/           provider discovery output + suggested config snippet
data/reports/              interactive_* audit reports
data/alerts/               notify output (md + json)
data/runs/                 agent-team run reports (offline runs excluded from change detection)
data/research_raw/         raw You.com MCP research per query (batches 1-5)
```

Research write-ups: `docs/research/01..07` (scraper landscape, no-auth endpoints,
platform access, offer sources, no-credit-card, frontier access, India/UPI).

---

## 6. Known limitations (honest list)

1. **Semantic relevance is still lexical.** Concept scoring rejects most non-AI noise but a
   page that mentions AI *and* free-tier language for an unrelated product can still slip
   through. An LLM relevance pass is the real fix; the blocklist is the cheap one.
2. **Verification is static-HTML first.** JS-only pages need the MCP fallback, which costs
   MCP calls and is only attempted when a page yields nothing.
3. **Reddit / Bluesky / YouTube blocked from this host** — they may work from a residential IP.
4. **Stale promo codes** persist in rows classified before the extractor was tightened;
   they only update when the row is reclassified.
5. **Numbers are single observations**, not averages over many cycles.
6. **IPv6/no-proxy:** discovery and verification run on the bare IP; several vendor sites
   return 403/404 to this host (npci.org.in, razorpay, perplexity.ai/pro, openai.com pricing).
7. **No scheduling yet.** Nothing runs the pipeline automatically — see next steps.

---

## 7. Next steps (in priority order)

1. **Schedule it.** Cron / Task Scheduler: `run` → `verify` → `notify` every few hours.
   Set `ALERT_WEBHOOK_URL` to get pushed the good stuff.
2. **Add an LLM relevance/review step** for the 8-15 ambiguous findings per cycle
   (the review flags in the interactive report are the shortlist).
3. **Reddit via the sanctioned OAuth script app** — the `.json`/`.rss` routes are dead.
4. **Activate YouTube/Threads** by adding channel ids + handles to `config.yaml`.
5. **Grow the discovery seed list** and re-run it monthly; it is how agentrouter.org-class
   providers get found.
6. **Consider a proxy/VPN** for the 403-blocked vendor pages (the repo already has
   `twitter_radar/vpn/proton.py` for the X side).

---

## 8. Session history (this engagement)

| Commit | What |
|---|---|
| `2899157` | fixed UnicodeEncodeError on Windows consoles |
| `584041d` | **airadar** package: 11 platform sources + agent team |
| `d087573` | platform-access + offer-source research |
| `d087573`→`0f0903c` | config watchlists, README/AGENTS updates |
| `1e8affc` | free-offer mission: findings + claim methods |
| `dbe7661` | refine + verify every finding (strict verdicts) |
| `21370fd` | track runtime data + tooling |
| `3106ecf` / `d6865f7` | owner-requested full-workspace tracking (incl. `.venv`) |
| `554d36b` | frontier-model free-access mission |
| `19f1efb` | India/UPI dimension |
| `eb67058` | provider discovery + multilingual signals (found agentrouter.org) |
| `d366ae6` | reliability: verdict-weighted scoring, URL dedupe, AI gate, derivative rule |
| `d91b905` | negation-aware card detection + concept relevance + interactive audit report |

Two defects worth remembering because they explain earlier distrust:
- **URL duplication** — 537 rows held only 246 unique URLs (54% twins).
- **Negation blindness** — `"no credit card required"` matched `"credit card required"`,
  which mislabelled 51 free-tier pages as card-gated.

---

## 9. Ground rules when working here

- Verify before claiming: `doctor` → `run` → `verify`, and read the interactive report.
- Never report a finding as confirmed without its evidence (verdict + signals + HTTP status).
- Keep the legacy `twitter_radar`/`run.py` path working; new work belongs in `airadar/`.
- `data/` is tracked on purpose (the owner asked for everything in git). `.env`,
  `cookies.json`, `secrets.json` patterns are **not** ignored — treat them as public the
  moment they exist. `secrets.env` is tracked; rotate keys if the repo is ever made public.
