"""Deterministic guardrails.

The pipeline refuses:
- fake reviews, testimonials, ratings or sign-ups, and fake scarcity (countdown timers)
- promises of income or success
- posing as the founder, a customer or another brand
- excluded products: physical goods; financial, investment or crypto products;
  health or legal advice products

`check_brief` screens the founder's idea before any agent runs.
`check_output` screens every piece of generated text before it is written or shown;
`redact` removes offending sentences from generated text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NEGATION = re.compile(r"\b(no|not|never|without|don't|doesn't|won't|refuse[sd]?|avoid|nor)\b[^.!?\n]{0,25}$", re.I)

CONDUCT_RULES: dict[str, list[str]] = {
    "fake_reviews": [
        r"\b(fake|fabricat\w*|made[- ]up|invent(ed)?|bogus|astroturf\w*|sock ?puppet\w*)\b[^.\n]{0,40}\b(reviews?|testimonials?|ratings?|sign-?ups?|customers?|users?|followers?)\b",
        r"\b(buy|purchase)\w*\s+(reviews|ratings|followers|sign-?ups)\b",
        r"\b(write|generate|post)\w*\s+(\w+\s+){0,3}(5|five)[- ]star reviews?\b",
    ],
    "fake_scarcity": [
        r"\bcountdown timers?\b",
        r"\bonly \d+ (spots?|copies|seats|left)\b",
        r"\boffer (ends|expires) in\b",
    ],
    "income_promise": [
        r"\bguarantee[sd]?\b[^.\n]{0,30}\b(income|earnings|profits?|revenue|results|success|returns?|sales)\b",
        r"\b(make|earn)\s+\$\s?\d[\d,]*(k)?\s*(\+\s*)?(a|per|/)\s*(day|week|month|year)\b",
        r"\bget rich\b",
        r"\b(passive income|financial freedom)\b[^.\n]{0,20}\b(guaranteed|fast|easy)\b",
        r"\b(guaranteed|risk-free) (income|profit|returns|success)\b",
    ],
    "impersonation": [
        r"\b(pose|posing|pretend\w*|masquerad\w*)\s+(as|to be)\b",
        r"\bimpersonat\w*\b",
        r"\b(write|post|reply|comment|sign)\w*\s+as (if (i|we) (were|are) )?(a|the) (customer|founder|user|buyer)\b",
        r"\b(official|on behalf of)\s+(apple|google|amazon|microsoft|meta|notion|canva|etsy|shopify|stripe|paypal)\b",
    ],
}

PRODUCT_RULES: dict[str, list[str]] = {
    "physical_goods": [
        r"\bphysical (product|goods|item|book|copy|copies|kit|box)\w*\b",
        r"\b(t-?shirts?|mugs?|merch(andise)?|stickers?|posters?|hardware devices?|print[- ]on[- ]demand|dropship\w*|warehouse|subscription box)\b",
        r"\bshipping (costs?|address|labels?)\b",
    ],
    "financial_or_crypto": [
        r"\b(crypto\w*|bitcoin|ethereum|nfts?|blockchain tokens?|defi|forex|day[- ]trading)\b",
        r"\b(investment|investing|trading|stock|financial)\s+(advice|signals?|picks?|tips|bot|product|fund|course)\b",
        r"\b(loans?|lending|insurance product|credit repair)\b",
    ],
    "health_advice": [
        r"\b(medical|health|clinical|nutrition(al)?)\s+advice\b",
        r"\b(diagnos\w*|symptom checker|treatment plans?|prescri\w*|supplements?|therapy|therapist)\b",
        r"\b(weight[- ]loss|diet|meal) (plans?|programs?|coaching)\b",
    ],
    "legal_advice": [
        r"\blegal (advice|documents?|contracts?|counsel|templates?)\b",
        r"\b(lawyer|attorney|immigration advice|wills? and testaments?|lawsuit)\b",
    ],
}

COPY_RULES: dict[str, list[str]] = {
    # Generated marketing copy may not contain testimonials or review quotes at all:
    # before launch there are no real customers to quote.
    "fake_reviews": [r"\btestimonials?\b", r"\b(rated|rating of) \d(\.\d)? ?(/ ?5|stars?)\b", r"\b\d[\d,]* (happy|satisfied) (customers|users)\b"],
}


@dataclass(frozen=True)
class Violation:
    category: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.category}: '{self.excerpt}'"


def _scan(text: str, rules: dict[str, list[str]]) -> list[Violation]:
    found: list[Violation] = []
    for category, patterns in rules.items():
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.I):
                before = text[max(0, m.start() - 40) : m.start()]
                if _NEGATION.search(before):
                    continue
                found.append(Violation(category, m.group(0)))
    return found


def check_brief(text: str) -> list[Violation]:
    return _scan(text, {**PRODUCT_RULES, **CONDUCT_RULES})


def check_output(text: str, *, marketing_copy: bool = False) -> list[Violation]:
    rules = dict(CONDUCT_RULES)
    if marketing_copy:
        rules = {k: rules.get(k, []) + COPY_RULES.get(k, []) for k in set(rules) | set(COPY_RULES)}
    return _scan(text, rules)


def redact(text: str, *, marketing_copy: bool = False) -> tuple[str, list[Violation]]:
    """Remove each sentence that breaks a conduct rule. Returns (clean_text, violations)."""
    violations = check_output(text, marketing_copy=marketing_copy)
    if not violations:
        return text, []
    parts = re.split(r"(?<=[.!?])\s+|\n", text)
    kept = []
    for part in parts:
        hits = check_output(part, marketing_copy=marketing_copy)
        kept.append(f"[removed by guardrails: {hits[0].category}]" if hits else part)
    return "\n".join(p for p in kept if p is not None), violations
