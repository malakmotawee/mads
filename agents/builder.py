"""Phase 3 (Build): STUBBED. Writes a product-spec outline from validated inputs; builds nothing."""
from __future__ import annotations

from agents.common import RunContext, StepResult

AGENT = "builder"


def product_spec(ctx: RunContext, attempt: int) -> StepResult:
    problem = ctx.results.get("phase1_step2_problem")
    plan = ctx.results.get("phase2_step3_validation_plan")
    body = "\n".join([
        "**STUBBED**: Phase 3 does not build the product yet. This outline only restates validated inputs.",
        "", "### Problem to solve", problem.summary if problem else "_(missing)_",
        "", "### Smoke-test result to build against", plan.summary if plan else "_(missing)_",
        "", "### Build tasks (STUBBED, not executed)",
        "- Draft the minimum digital product that addresses the problem statement",
        "- Founder review of the draft before anything is shared",
    ])
    ctx.log.record(AGENT, "product_spec_outline", model=None, cost=0, detail="STUBBED")
    return StepResult(title="Product spec (STUBBED)", body=body, labels=["STUBBED"], metrics={"artifact_produced": True})
