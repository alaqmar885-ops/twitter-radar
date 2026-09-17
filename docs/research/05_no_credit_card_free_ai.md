# Report 5 - Free AI offers that need NO credit card (2026)

> Source: You.com MCP sweep, 16 queries x 8 hits (raw: `data/research_raw/batch3_*`),
> 2026-09-17. Cross-checked against the radar's own live verification pass.

The question: which AI services give something genuinely free **without a payment
method on file**? Below, "no card" means the source explicitly states no credit
card is required (or "no signup"), as opposed to a trial that demands billing.

## Confirmed no-card free tiers

| Service | What you get | Card? | Source |
|---|---|---|---|
| **Google AI Studio / Gemini API** | ~1,500 requests/day, 1M TPM, Flash + Flash-Lite | No card | tokenmix.ai/blog/gemini-api-free-tier-limits; yangmao.ai/en/providers/google/no-credit-card/ |
| **Groq** | Free developer tier, ~1,000 req/day (30k TPM), 500+ tok/s | No card | itsfree.ai/provider/groq/; getaiperks.com/en/ai/groq-free-tier-2026 |
| **Cloudflare Workers AI** | 10,000 neurons/day across ~82 models | No card | toolfreebie.com/cloudflare-workers-ai/ |
| **OpenRouter** | Free-model routing (`:free` models, ~14-25 at a time) | No card | openrouter.ai/docs/guides/routing/routers/free-router |
| **GitHub Models** | High-tier ~50 req/day, mini ~150 req/day | No card (GitHub account) | github.com/marketplace/models |
| **Hugging Face Inference** | Free inference API quota | No card | yangmao.ai/en/providers/huggingface/no-credit-card/ |
| **Mistral La Plateforme** | Free "Experiment" tier, rate-limited | No card | (report 4) console.mistral.ai |

## Directories that track no-card free tiers (monitored by the radar)

| Directory | Why it matters |
|---|---|
| free-model.com / free-model.com/providers | 147+ verified free LLM APIs, live-tested, explicitly "no credit card" |
| tokenmix.ai/blog/free-llm-api | 15 best free LLM APIs, ranked by verified limits + no-card access |
| itsfree.ai | per-provider free-tier cards incl. card policy |
| toolfreebie.com | no-card reviews incl. Cloudflare Workers AI |
| yangmao.ai | per-provider "without credit card?" guides (Google, HF, Cloudflare, …) |
| freellm.net / freeapihub.com / aimlapi.com | provider directories + step-by-step key guides |
| usagebox.com/articles/free-ai-apis-2026-no-credit-card-real-rate-limits | "stays free, no expiring credits" analysis |
| comparegen.ai / toolcenter.ai | "best free AI tools, no signup, no credit card" roundups |

## Caveats (evidence discipline)

- Several sources in this space are themselves SEO/affiliate pages; the *claim*
  "no credit card" is only trustworthy when the vendor's own pricing page says so.
  This is exactly why the radar's verification pass now scans the vendor page for
  explicit card policy rather than trusting the article that linked it.
- Free tiers change often (Cerebras removed its no-card free tier in favour of a
  card-gated $5 trial). Re-verify before relying on any row.
- "No card" and "no expiry" are different claims. Gemini's free tier does not
  expire; most trial credits do (often 30 days).

## Radar changes made for this mission

- `airadar/verify.py` now detects **no-card evidence** (`no credit card`,
  `no card required`, `no payment method`, ...) and card-required evidence
  (`credit card required`, `add a payment method`, ...), producing a
  `VERIFIED_NO_CC` verdict when a page shows a specific free signal *and* a
  no-card policy, and `CARD_REQUIRED` when the page demands a card.
- `config.yaml` gained no-card HN/Bluesky queries plus the tracker pages above.
- `scripts/no_cc_report.py` renders the no-card shortlist from the store.
