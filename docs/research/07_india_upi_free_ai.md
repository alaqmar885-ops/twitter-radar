# Report 7 - India & UPI: free AI offers an Indian user can actually reach

> You.com MCP sweep, 18 queries x 8 hits (raw: `data/research_raw/batch5_*`), 2026-09-17.
> Live route verification: `scripts/india_report.py`.

Two different questions matter for an Indian user, and they are not the same:

1. **Can I get the offer from India?** (regional availability, telco bundles)
2. **Can I pay for an upgrade without a foreign card?** (UPI, netbanking, Play billing)

## The strongest India-specific free offers found

| Offer | What you get | Evidence |
|---|---|---|
| **Jio x Google AI Pro** | **18 months of Google AI Pro free** for Jio users | vendor page `jio.com/google-gemini-offer/`; widely reported (timesofai, technosports) |
| **Airtel x Perplexity Pro** | Perplexity Pro free for Airtel users, reported worth ~Rs 17,000 | timesofindia coverage of the Airtel/Perplexity bundle |
| **Jio x Canva Pro** | Canva Pro / Pro Lite worth ~Rs 4,000 for Jio users | timesofindia |
| **Gemini free tier** | Gemini Flash free in India via AI Studio, no card | ai.google.dev rate-limit docs |
| **Free LLM API pools** | Open-weight frontier models (DeepSeek/Qwen/Kimi) free via aggregators | free-model.com/providers (no card) |

Telco bundles are the single biggest lever for India: they hand out premium AI
subscriptions that would otherwise be card-gated.

## UPI: the payment side

- **NPCI is building the "Unified Agent Protocol"** so AI agents can initiate
  small UPI payments - i.e. UPI is becoming the default rail for AI-agent
  purchases in India (multiple 2026 sources: digitimes, thepaypers, startupfortune).
- **RBI announced UPI tap-and-pay and MyUPI** with AI support (indiatoday, Sep 2026).
- Practically today: **Google Play billing supports UPI in India**, so any AI
  subscription bought *in-app* on Android can be paid by UPI even when the
  vendor's own web checkout only takes a card.
- Web checkouts vary a lot: Google (Google One / AI Pro) has India pricing and
  multiple local methods; OpenAI and Anthropic web billing are card-first, so an
  Indian user typically needs either an international-enabled card, Play billing,
  or a telco bundle.

## The practical Indian playbook

1. **Claim the telco bundles first** - Jio (Google AI Pro, 18 months) and Airtel
   (Perplexity Pro) are free and card-free.
2. **Use free API tiers that need no card** - Google AI Studio for Gemini Flash,
   and the free gateway pools for open-weight frontier models.
3. **Prefer in-app purchases on Android** when you must pay, so UPI is available
   through Play billing.
4. **Self-host open weights** (Ollama) when hardware allows - no payment rail at all.

## Caveats

- Telco offers are eligibility- and time-bound (plan, new/existing user, launch
  window) and have repeatedly been extended or narrowed - verify on the vendor page.
- "India pricing" does not automatically mean "UPI accepted"; Play billing is the
  most reliable UPI path today.
- The radar's India check is term-based (it looks for India/UPI terms on the page).
  That is a *signal*, not proof that a given checkout accepts UPI - treat the
  report as a lead list, then confirm at payment time.
