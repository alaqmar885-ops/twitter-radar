# Report 6 - Frontier model free access (2026)

> You.com MCP sweep, 18 queries x 8 hits (raw: `data/research_raw/batch4_*`),
> plus live verification of each access route in `scripts/frontier_report.py`.

"Frontier model" here means the current top of the line: GPT-5.x, Claude
Opus/Sonnet 4.x, Gemini 3.x, Grok 4, plus the open-weight frontier family
(DeepSeek V4, Qwen 3.x, Kimi K2.x, GLM, Llama). The blunt finding first:

> **No vendor gives unlimited free API access to its top model.** What exists is
> (a) free *chat* tiers with caps, (b) free *API* tiers for smaller/Flash models,
> (c) free *pools* of open-weight frontier models via aggregators, and
> (d) open weights you can self-host at zero marginal cost.

## The five routes

| Route | What it actually gives | Best examples |
|---|---|---|
| **1. Vendor free tier (chat)** | Capped chat access to the frontier model itself | ChatGPT free, Claude free (low tens of messages / 5h), Gemini free, Grok free on grok.com/X (no card, weekly quota) |
| **2. Vendor free API tier** | Rate-limited API, usually smaller/Flash models | Google AI Studio (Gemini Flash, ~1500 req/day, no card), Mistral free experiment tier |
| **3. Free playgrounds & arenas** | Direct use of frontier models, no key | LMArena side-by-side, MCPJam free frontier playground (GPT-5, Claude Sonnet, Gemini, Grok), vendor playgrounds |
| **4. Aggregators serving free pools** | `:free` model pools, incl. open-weight frontier | OpenRouter free-router; Kimi K2 `:free`, DeepSeek, Qwen, GLM entries; free model directories (free-model.com, freellmapi.co) |
| **5. Open weights (self-host)** | Unlimited local inference at zero marginal cost | DeepSeek V4 (MIT, 1.6T MoE), Qwen, Kimi K2, GLM, Llama; via Ollama / vLLM / llama.cpp |

## Per-family notes

| Family | Free access that exists | Reality check |
|---|---|---|
| **GPT-5 class** | ChatGPT free tier; GitHub Models free quota; free playgrounds (MCPJam); third-party trial gateways | OpenAI publishes **no free API tier** for GPT-5 (confirmed by multiple 2026 sources) |
| **Claude** | Claude free plan (capped messages per 5h); developer free routes; some aggregator pools | Anthropic changed free-tier limits in 2026; caps are enforced per rolling window |
| **Gemini** | AI Studio free (Gemini 3 Flash, no card), free API tier (~1500 req/day), free in Antigravity | Pro-class moves to paid; enabling billing silently removes the free tier |
| **Grok** | Free on grok.com and X, **no credit card** | Weekly quota counts everything; image/voice caps differ |
| **DeepSeek** | **Open weights (MIT)** + free API quota + free gateways (22 free models, no card) | The strongest genuinely-free frontier option |
| **Qwen** | Free Qwen Chat app; free Qwen Code CLI; open weights; free via Puter.js | No free API tier for the newest Max-class model |
| **Kimi** | Open weights; served `:free` on OpenRouter; free via gateways |  |
| **Llama** | Free inference providers (Groq, NVIDIA NIM, Cloudflare Workers AI); open weights | Quality trails the closed frontier |

## Recommended cheap-and-legit stack

1. **Gemini via Google AI Studio** - best free *API* tier (no card).
2. **DeepSeek / Qwen / Kimi via OpenRouter `:free` or a free gateway** - frontier-class open weights at zero cost.
3. **Grok + ChatGPT + Claude free chat tiers** - no-card access to closed frontier models, capped.
4. **LMArena / MCPJam** - when you need to *use* or compare frontier models without an account.
5. **Ollama + open weights** - unlimited local runs when you have the hardware.

## Caveats

- Free tiers change fast and are often quietly reduced; every route in
  `scripts/frontier_report.py` is re-verified by HTTP on each run.
- Many "free GPT-5 API" pages are SEO gateways or proxies of unclear legality -
  the report marks the route type so you can tell a vendor tier from a reseller.
- "Free" almost always means *rate-limited*; nothing here is unlimited API access
  to a closed frontier model.
