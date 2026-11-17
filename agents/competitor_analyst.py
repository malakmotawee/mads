"""Phase 2, step 1 (Validate): competitors, free alternatives and price points."""
from __future__ import annotations

import re

from agents.common import Brief, RunContext, StepResult, research_step

AGENT = "competitor_analyst"
TYPES = ("competitor", "free_alternative", "price_point", "other")
_PRICE = re.compile(r"(\$|€|£|usd|eur|gbp)\s?\d|\d\s?(\$|€|£|usd|eur|gbp)", re.I)


def _fallback(brief: Brief) -> list[str]:
    idea = brief.sections.get("Idea", brief.title)[:90]
    return [f"{idea} price", f"best {idea}", f"free {idea}", f"{idea} alternatives"]


def scan_competitors(ctx: RunContext, attempt: int) -> StepResult:
    problem = ctx.results.get("phase1_step2_problem")
    extra = f"PROBLEM STATEMENT FROM PHASE 1:\n{problem.summary}" if problem else ""
    result = research_step(
        ctx,
        agent=AGENT,
        prompt_name="competitor_analyst",
        title="Competitors, free alternatives and prices",
        purpose="Find existing paid products, free alternatives, and real prices for products that solve this problem.",
        allowed_types=TYPES,
        claim_prefix="C",
        attempt=attempt,
        extra_context=extra,
        fallback_queries=_fallback,
    )
    # A paid price point counts only if it is sourced and a price is visible in the claim.
    paid = [
        c for c in result.claims
        if c.sourced and c.type in ("competitor", "price_point") and (_PRICE.search(c.price or "") or _PRICE.search(c.text))
    ]
    result.metrics["paid_price_points"] = len(paid)
    result.metrics.setdefault("free_alternative", 0)
    return result
