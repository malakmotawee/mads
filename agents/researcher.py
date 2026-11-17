"""Phase 1, step 1 (Discover): find evidence of the problem and the opportunity."""
from __future__ import annotations

from agents.common import Brief, RunContext, StepResult, research_step

AGENT = "researcher"
TYPES = ("pain", "workaround", "trend", "other")


def _fallback(brief: Brief) -> list[str]:
    customer = brief.sections.get("Target customer", "")[:80]
    problem = brief.sections.get("Problem", brief.title)[:80]
    return [f"{customer} {problem} reddit", f"{problem} frustrating", f"{customer} how do you deal with {problem}", f"{problem} forum"]


def find_opportunities(ctx: RunContext, attempt: int) -> StepResult:
    return research_step(
        ctx,
        agent=AGENT,
        prompt_name="researcher",
        title="Opportunities and pain-point evidence",
        purpose="Find public evidence (forums, Q&A, articles) that the target customer actually has the stated problem, "
        "how they handle it today, and any trend that makes it bigger.",
        allowed_types=TYPES,
        claim_prefix="O",
        attempt=attempt,
        fallback_queries=_fallback,
    )
