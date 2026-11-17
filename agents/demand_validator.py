"""Phase 2, step 2 (Validate): evidence for and against willingness to pay."""
from __future__ import annotations

from agents.common import Brief, RunContext, StepResult, domain, research_step

AGENT = "demand_validator"
TYPES = ("wtp_positive", "wtp_negative", "demand_signal", "other")


def _fallback(brief: Brief) -> list[str]:
    idea = brief.sections.get("Idea", brief.title)[:90]
    return [f"would you pay for {idea}", f"{idea} worth paying for", f"{idea} reviews sales", f"{idea} free vs paid"]


def assess_demand(ctx: RunContext, attempt: int) -> StepResult:
    comp = ctx.results.get("phase2_step1_competitors")
    extra = ""
    if comp:
        extra = "COMPETITOR FINDINGS (phase 2 step 1):\n" + "\n".join(f"- {c.text} ({c.source})" for c in comp.claims[:15])
    result = research_step(
        ctx,
        agent=AGENT,
        prompt_name="demand_validator",
        title="Demand and willingness to pay",
        purpose="Find evidence that the target customer pays (or refuses to pay) for this kind of digital product: "
        "sales counts, paid listings with reviews, forum threads about paying vs. using free options.",
        allowed_types=TYPES,
        claim_prefix="D",
        attempt=attempt,
        extra_context=extra,
        fallback_queries=_fallback,
    )
    result.metrics.setdefault("wtp_positive", 0)
    result.metrics.setdefault("wtp_negative", 0)
    result.metrics["wtp_positive_domains"] = len({domain(c.source) for c in result.claims if c.sourced and c.type == "wtp_positive"})
    return result
