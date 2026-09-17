"""Research batch 2 over the You.com MCP — free-tier programs + more platforms."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\scrapper")
from twitter_radar.enrich.youcom import YouComEnricher  # noqa: E402

KEY = ""
for line in open(r"D:\scrapper\secrets.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("YDC_API_KEY="):
        KEY = line.split("=", 1)[1].strip()

e = YouComEnricher(api_key=KEY, max_results=8, timeout=40)
OUT = Path(r"D:\scrapper\data\research_raw")
OUT.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "Groq API free tier rate limits 2026",
    "Mistral La Plateforme free tier API key limits",
    "Google AI Studio Gemini API free tier limits 2026",
    "OpenRouter free models API list",
    "Cerebras inference free tier API",
    "GitHub Models free tier API playground",
    "AWS Activate Microsoft for Startups Google for Startups free cloud credits AI",
    "NVIDIA Inception program free credits startups AI",
    "Product Hunt launches API scraping without key 2026",
    "GitHub trending repositories how to scrape API",
    "StackSocial AI lifetime deals subscriptions",
    "Telegram channels AI tools deals free credits",
    "Bluesky AT Protocol public API search posts without auth",
    "Mastodon public API search timelines without auth instance list",
    "Hugging Face blog RSS feed papers RSS URL",
    "LinkedIn public company posts scraping without login 2026 status",
    "TikTok public data scraping without login 2026 status",
    "TheZAI free AI tools newsletter websites aggregator 2026",
    "coupon codes AI subscriptions SaaS reddit twitter 2026",
    "university startup programs free OpenAI Anthropic credits academics",
]

all_results = {}
for i, q in enumerate(QUERIES):
    res = e.search(q, max_results=8)
    all_results[q] = res
    print(f"[{i+1}/{len(QUERIES)}] {len(res):2d} hits | {q}")
    (OUT / f"batch2_{i:02d}.json").write_text(
        json.dumps({"query": q, "results": res}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    time.sleep(1.0)

(OUT / "batch2_all.json").write_text(
    json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8"
)
md = ["# Raw you-search digest — batch 2", ""]
for q, res in all_results.items():
    md.append(f"## Q: {q}")
    if not res:
        md.append("- (no results)")
    for r in res:
        md.append(
            f"- [{(r.get('title') or '')[:110]}]({r.get('url','')}) "
            f"— {(r.get('description') or '')[:230]}"
        )
    md.append("")
(OUT / "batch2_digest.md").write_text("\n".join(md), encoding="utf-8")
print("digest ->", OUT / "batch2_digest.md")
