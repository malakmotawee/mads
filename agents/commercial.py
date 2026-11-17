"""Phase 4 (Commercial setup): STUBBED. Offer outline and a store listing that is only
'published' (STUBBED) after founder approval."""
from __future__ import annotations

import guardrails
from agents.common import RunContext, StepResult
from approval import ensure_approved, request_approval

AGENT = "commercial"


def offer(ctx: RunContext, attempt: int) -> StepResult:
    price = ctx.brief.sections.get("Price idea", "ASSUMPTION: no price given")
    comp = ctx.results.get("phase2_step1_competitors")
    prices = [f"- {c.text} ({c.source})" for c in (comp.claims if comp else []) if c.price and c.sourced]
    body = "\n".join(["**STUBBED**: pricing is not optimised; this restates the founder's price and sourced competitor prices.",
                      "", f"### Founder's price idea\n{price}", "", "### Sourced competitor prices", *(prices or ["- _(none)_"]),
                      "", "Terms: refunds handled only with founder approval (refunds.py, MOCKED)."])
    ctx.log.record(AGENT, "offer_outline", model=None, cost=0, detail="STUBBED")
    return StepResult(title="Offer (STUBBED)", body=body, labels=["STUBBED"], metrics={"artifact_produced": True})


def publish_listing(text: str, approval) -> str:
    ensure_approved(approval, "publish_listing")
    return "STUBBED: listing not actually published (no storefront is connected)"


def listing(ctx: RunContext, attempt: int) -> StepResult:
    text = f"{ctx.brief.title}\n\n{ctx.brief.sections.get('Idea', '')}"
    text, hits = guardrails.redact(text, marketing_copy=True)
    appr = request_approval("publish_listing", "publish", f"Store listing (STUBBED):\n\n{text}", input_fn=ctx.approval_input)
    ctx.log.record("approval", "founder_approval:publish_listing", model=None, cost=0,
                   approved_by=appr.approver if appr.approved else None,
                   outcome="approved" if appr.approved else "rejected", detail=appr.reason)
    note = appr.reason
    if appr.approved:
        note = publish_listing(text, appr)
        ctx.log.record(AGENT, "publish_listing", model=None, cost=0, approved_by=appr.approver, detail="STUBBED")
    return StepResult(title="Store listing (STUBBED)", body=f"```\n{text}\n```\n\n{note}", labels=["STUBBED"],
                      metrics={"artifact_produced": True, "needs_approval": True, "founder_approved": appr.approved,
                               "guardrail_violations": len(hits)})
