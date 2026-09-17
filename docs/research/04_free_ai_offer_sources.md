# Report 4 — Where Free-AI Offers Surface (2026)

> Source: You.com MCP sweep (38 queries, raw JSON in `data/research_raw/`) +
> prior repo research. This is the targeting layer for the agent team: what to
> watch, with which exact handles/queries/URLs.

## 1. X / Twitter accounts (via existing no-auth router)

**Deal/launch aggregators & curators:** @AIHighlight, @LinusEkenstam (posts vendor
promo codes), @mreflow (Matt Wolfe), @theresanaiforthat, @FutureStacked,
@mikenevermiss (free-AI compilations), @AIBreakfast, @TheAIGRID, @MattVidpro.

**Vendor accounts that post promos:** @OpenAI, @sama, @AnthropicAI, @GoogleDeepMind,
@GoogleAI, @perplexity_ai, @AravSrinivas, @MistralAI, @xai, @grok, @logankilpatrick,
@huggingface, @cursor_ai, @karpathy, @alliekmiller, @levelsio.

## 2. Subreddits

Niche deal subs found in this sweep (higher signal than generic AI subs):
- **r/aisubscriptions** — dedicated to AI subscription deals/giveaways
- **r/toolsdeals**, **r/discountools** — tool/app discounts incl. AI
- **r/appsumo** — lifetime deals
- Broad subs where free-credit roundups go viral: r/PromptEngineering,
  r/learnmachinelearning, r/generativeAI, r/LocalLLaMA, r/SideProject,
  r/artificial, r/ChatGPTCoding.
- Access: `.rss` or PullPush (Report 3 §3); `.json` is deprecated/403 in 2026.

## 3. Hacker News queries (Algolia, no key)

`"Show HN free"`, `"free tier AI"`, `"free credits"`, `"lifetime deal AI"`,
`"open source model"` — `search_by_date` with `tags=story` (optionally
`(story,show_hn)` and `numericFilters=points>20` to cut noise).

## 4. YouTube channels (channel RSS)

Matt Wolfe (@mreflow), FutureTools, The AI Advantage, TheAIGRID, Wes Roth,
AI Explained, Two Minute Papers, Skill Leap AI + vendor channels (OpenAI,
Google DeepMind, Anthropic, Hugging Face). Feed = channel RSS (Report 3 §2).

## 5. Free-tier / free-credits tracking pages (HTML watch — new, very high signal)

| Site | URL | Why |
|------|-----|-----|
| Free LLM API Hub | freellmapihub.com/programs/startups | application-based credit programs |
| free-model.com | free-model.com | 147+ verified free LLM APIs, live-tested |
| awesome-freellm-apis (GitHub) | github.com/open-free-llm-api/awesome-freellm-apis | 134+ free APIs, raw README fetchable |
| CostGoat | costgoat.com/pricing/openrouter-free-models | live-updated free model lists |
| getaiperks.com | getaiperks.com/en/blogs/27-ai-api-free-tier-credits-2026 | provider-by-provider credits |
| perkstack.co | perkstack.co/blog/free-ai-api-credits | 11 providers compared |
| creditforstartups.com | creditforstartups.com/credits/ai | startup AI credit programs |
| pricepertoken.com | pricepertoken.com/endpoints/groq/free | per-provider free-tier snapshots |
| yangmao.ai deals | yangmao.ai/en/deals | free-tier changes with dates |

Known 2026 free tiers worth baseline-watching (for change detection):
Groq (30–60 RPM free), Google AI Studio Gemini (1,500 req/day, no card),
Mistral La Plateforme (free experiment tier), OpenRouter (~25 free models,
$10-threshold rule), GitHub Models (50 req/day high-tier / 150 mini),
Cerebras ($5 trial / 1M tokens-day historical), NVIDIA Inception (GPU credits),
startup stacks: AWS Activate / Google for Startups / Microsoft for Startups
(cloudkompas.com comparison; orbitmoney.io $500k+ stack),
Parallel.ai $80 credits (resourify.com), Anthropic via FounderPass ($300 credits).

## 6. Lifetime-deal & coupon aggregators (HTML watch)

| Site | URL | Notes |
|------|-----|-------|
| zplatform.ai | zplatform.ai/ai-deal | 395 hand-tested AI deals w/ verdicts |
| AppSumo AI collection | appsumo.com/collections/features/ai/ | official AI LTD shelf |
| 99signals AppSumo roundup | 99signals.com/appsumo-deals | weekly-updated list |
| StackSocial AI | stacksocial.com/collections/artificial-intelligence | AI LTD subscriptions |
| dealkeep.io | dealkeep.io/best-lifetime-deal-tools | verified LTDs + expiry |
| predrop.ai | predrop.ai/best-ai-lifetime-deals | curator working list |
| alstonantony.com | alstonantony.com/seo-deals/best-ai-lifetime-deal-sites/ | 15+ sites tested |
| SimplyCodes | simplycodes.com/category/artificial-intelligence | 6k+ verified promo codes |
| felloai.com/ai-deals | felloai.com/ai-deals | deal roundup incl. student discounts |

## 7. Vendor blogs / changelogs (mixed availability)

- **No official RSS (use HTML watch or community feeds):** Anthropic News
  (windflash.us/rss-sources; github.com/CorjanBos/ai-rss-feed), OpenAI blog
  (RSS broken after site revamp — community.openai.com/t/733747), Perplexity
  changelog (perplexity.ai/changelog, HTML).
- **RSS available:** Hugging Face blog (huggingface.co/blog/feed.xml); HF Daily
  Papers via community feeds (github.com/AzureSilent/hf-paper-rss,
  takara-ai/papers-api); Google AI blog (blog.google/technology/ai/rss/);
  aggregated AI feed lists: rss.feedspot.com/ai_rss_feeds, windflash.us/rss-sources,
  github.com/Olshansk/rss-feeds, github.com/0xSMW/rss-feeds.
- RSSHub can cover most gaps when self-hosted (rsshub.rssforever.com public
  instance; Railway 1-click deploy templates verified in search).

## 8. Newer channels worth a source each

- **Bluesky** public search (queries: "free credits", "free tier", "lifetime deal" + AI terms).
- **Telegram** channels via t.me/s preview: @Best_AI_tools, @DeepLearning_ai.
- **Mastodon** hashtag timelines (#AI, #OpenSource, #FreeSoftware).
- **Newsletters index** for manual expansion: github.com/alternbits/awesome-ai-newsletters;
  The Rundown AI, TLDR AI, Superhuman AI, TAAFT (readless.app ranking verified).

## Prioritized top-10 for the automated radar

1. X/Twitter router (existing, no-auth) — highest launch-signal density.
2. HN Algolia queries — instant, structured, launch-heavy.
3. Free-tier tracker pages (costgoat, free-model.com, freellmapihub) — the exact "free" claims, few sources, high signal.
4. Deal aggregators (zplatform, AppSumo AI, StackSocial) — LTDs, weekly churn.
5. Niche subreddits via .rss/PullPush (r/aisubscriptions, r/appsumo, r/toolsdeals).
6. YouTube channel RSS (deal reviewers + vendor channels).
7. Bluesky public search.
8. Telegram t.me/s previews.
9. Vendor blogs/changelogs (RSS where it exists, HTML watch otherwise).
10. Mastodon tags (cheap, low noise-floor).
