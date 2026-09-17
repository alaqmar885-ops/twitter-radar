"""Weighted offer-signal engine.

The first version of the radar used a substring match on a keyword list, which
flagged anything containing the word "free" - the verification pass then threw
away roughly half of it. This module replaces that with a weighted phrase
scorer plus explicit negative evidence, so triage decides on *strength of
evidence* rather than the presence of one word.
"""
from __future__ import annotations

import re

# (phrase, weight) - strong evidence of a real free/offer proposition.
STRONG = {
    "free tier": 3, "free plan": 3, "free trial": 3, "free forever": 3,
    "always free": 3, "no credit card": 3, "no card required": 3,
    "no card needed": 3, "free credits": 3, "free of charge": 3,
    "100% off": 3, "lifetime deal": 3, "lifetime license": 3,
    "free for": 3, "start free": 2, "try free": 2, "free access": 2,
    "free api": 2, "promo code": 2, "coupon code": 2, "giveaway": 2,
    "beta access": 2, "no cost": 2, "$0": 2, "credits": 1,
    "open source": 1, "self-hosted": 1, "free": 1, "trial": 1,
    # Chinese-first providers (SiliconFlow / ModelScope / AgentRouter ...)
    "免费额度": 3, "免费试用": 3, "注册送": 3, "无需信用卡": 3, "免信用卡": 3,
    "赠送额度": 3, "免费": 1, "试用": 1, "赠送": 2, "优惠": 2,
    "discount": 2, "% off": 2, "deal": 2, "launch": 1,
}

# Phrases that cancel a free claim outright - if one of these is present the
# text is treated as NOT an offer regardless of positive signals.
HARD_VETO = [
    "no free tier", "no free plan", "no longer free", "free tier is gone",
    "removed the free", "not free", "paid only", "free tier was removed",
]

# Phrases that contradict or weaken a "free" claim.
NEGATIVE = {
    "not free": 3, "no free tier": 3, "paid only": 3, "requires payment": 3,
    "credit card required": 2, "price increase": 2, "no longer free": 3,
    "free tier is gone": 3, "removed the free": 3, "subscription required": 1,
}

DEFAULT_THRESHOLD = 3


def _hits(text: str, table: dict) -> dict:
    low = (text or "").lower()
    return {p: w for p, w in table.items() if p in low}


def score_text(text: str) -> dict:
    """Return {score, strong, medium, negative, veto, matched} for a blob of text."""
    low = (text or "").lower()
    veto = [v for v in HARD_VETO if v in low]
    if veto:
        return {"score": 0, "strong": [], "medium": [], "negative": [], "veto": veto,
                "negative_score": 0, "matched": []}
    strong = _hits(text, {p: w for p, w in STRONG.items() if w >= 2})
    medium = _hits(text, {p: w for p, w in STRONG.items() if w < 2})
    neg = _hits(text, NEGATIVE)
    strong_score = sum(strong.values())
    medium_score = sum(medium.values())
    neg_score = sum(neg.values())
    # A single weak word ("free") is not evidence; strong phrases dominate,
    # and accumulated medium signals can qualify on their own.
    score = strong_score + (medium_score if medium_score >= 2 else 0)
    return {
        "score": score,
        "strong": sorted(strong),
        "medium": sorted(medium),
        "negative": sorted(neg),
        "veto": [],
        "negative_score": neg_score,
        "matched": sorted(list(strong) + list(medium)),
    }


def is_offer_text(text: str, threshold: int = DEFAULT_THRESHOLD) -> bool:
    s = score_text(text)
    if s["veto"]:
        return False
    if s["negative_score"] >= 3 and not s["strong"]:
        return False
    return s["score"] >= threshold


# The radar hunts *AI* offers. Without this gate a hardware-telemetry tool or
# a general SaaS discount qualifies on the word "free" alone - a large share of
# the noise in early reports.
AI_TERMS = [
    "ai", "a.i.", "llm", "gpt", "claude", "gemini", "grok", "deepseek", "qwen",
    "llama", "mistral", "model", "models", "neural", "machine learning", " ml ",
    "inference", "prompt", "agent", "chatbot", "copilot", "embedding", "rag",
    "diffusion", "transformer", "openai", "anthropic", "hugging face", "huggingface",
    "token", "fine-tune", "generative", "\u5927\u6a21\u578b", "\u6a21\u578b",
]

# Hosts that are unambiguously AI providers - exempt from the keyword gate.
AI_HOSTS = (
    "openrouter.ai", "huggingface.co", "groq.com", "cerebras.ai", "mistral.ai",
    "deepseek.com", "together.ai", "deepinfra.com", "fireworks.ai", "novita.ai",
    "siliconflow.com", "modelscope.cn", "ollama.com", "agentrouter.org",
    "aimlapi.com", "bazaarlink.ai", "chutes.ai", "featherless.ai", "glama.ai",
    "perplexity.ai", "anthropic.com", "openai.com", "google.dev", "aistudio.google.com",
)


# Short tokens ("ai", "ml") must match as whole words, otherwise "available",
# "email" or "said" would satisfy the AI gate.
_AI_WORD = re.compile(r"\b(ai|ml|llm|gpt|rag)\b", re.I)
_AI_HOST_RE = None


def is_ai_related(text: str, min_score: int = 2) -> bool:
    """AI relevance = enough distinct AI concepts, not one keyword match."""
    low = f" {(text or '').lower()} "
    if any(h in low for h in AI_HOSTS):
        return True
    score, _ = ai_relevance(text)
    return score >= max(1, int(min_score))


# AI *concepts*, not just the token "ai". A page that merely says "AI" once
# ("telemetry for hardware teams who could build it") is not an AI offer; a page
# selling model access is. Counting distinct concepts separates the two without
# needing an LLM.
AI_CONCEPTS = {
    "model_access": ["llm", "large language model", "gpt", "claude", "gemini", "grok",
                     "deepseek", "qwen", "llama", "mistral", "kimi", "glm", "phi",
                     "inference", "api key", "api credits", "tokens", "context window",
                     "model", "checkpoint", "fine-tune", "embedding"],
    "ai_product": ["ai assistant", "ai agent", "chatbot", "copilot", "ai tool",
                   "ai writer", "text-to-", "image generation", "generative",
                   "ai coding", "ai powered", "ai-powered", "prompt"],
    "ai_context": ["machine learning", "neural", "diffusion", "transformer",
                   "artificial intelligence", "\u5927\u6a21\u578b", "\u6a21\u578b"],
}
AI_PHRASES = ["free ai", "ai free", "ai api", "ai credit", "ai tier",
              "ai subscription", "ai plan", "ai trial", "ai token"]


def ai_relevance(text: str) -> tuple:
    """Return (score, matched_terms).

    score = number of DISTINCT AI terms present (word-boundary aware for short
    ones), +2 when the URL is a known AI provider. A single passing mention of
    "AI" scores 1; a page actually selling model access scores 3-6. This is what
    separates "telemetry for hardware teams" (0) from "free LLM API credits" (3)
    without needing an LLM in the loop.
    """
    low = f" {(text or '').lower()} "
    hits = set()
    for terms in AI_CONCEPTS.values():
        for t in terms:
            if t in low:
                hits.add(t)
    if _AI_WORD.search(low):
        hits.add("ai")
    for p in AI_PHRASES:
        if p in low:
            hits.add(p)
    score = len(hits)
    if any(h in low for h in AI_HOSTS):
        score += 2
        hits.add("host:ai_provider")
    return score, sorted(hits)


PRODUCT_PREFIX = re.compile(r"^\s*(?:show|ask|tell)\s+hn\s*[:\-]\s*(.+)$", re.I)
