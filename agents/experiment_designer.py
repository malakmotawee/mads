"""Phase 2, step 3 (Validate): a smoke-test plan with success criteria set in advance.

Drafting is real (LLM). Publishing the landing page is STUBBED and runs only
after the founder approves it in approval.py.
"""
from __future__ import annotations

import guardrails
from agents.common import RunContext, StepResult, ask_json, load_prompt
from approval import ensure_approved, request_approval

AGENT = "experiment_designer"


def publish_landing_page(copy: str, approval) -> str:
    """STUBBED: nothing goes online. Refuses to run without a founder approval."""
    ensure_approved(approval, "publish_landing_page")
    return "STUBBED: landing page not actually published (no hosting is connected)"


def design_validation_plan(ctx: RunContext, attempt: int) -> StepResult:
    problem = ctx.results.get("phase1_step2_problem")
    demand = ctx.results.get("phase2_step2_demand")
    data = ask_json(
        ctx, AGENT, "draft_validation_plan", load_prompt("experiment_designer"),
        f"FOUNDER BRIEF:\n{ctx.brief.as_text()}\n\nPROBLEM:\n{problem.summary if problem else ''}\n\n"
        f"DEMAND SUMMARY:\n{demand.summary if demand else ''}",
        sources=(demand.sources if demand else []),
    )
    copy = str(data.get("landing_page_copy") or "").strip()
    violations = guardrails.check_output(copy, marketing_copy=True)
    copy, _ = guardrails.redact(copy, marketing_copy=True)
    experiment = str(data.get("experiment") or "").strip()
    criteria = [str(c) for c in data.get("success_criteria", []) if str(c).strip()]
    for v in violations:
        ctx.log.record("guardrails", "redact_marketing_copy", model=None, cost=0, detail=str(v))

    approved = False
    publish_note = "not requested: copy broke a guardrail"
    if not violations and copy:
        appr = request_approval("publish_landing_page", "publish",
                                f"Landing page copy (would be published, STUBBED):\n\n{copy}",
                                input_fn=ctx.approval_input)
        ctx.log.record("approval", "founder_approval:publish_landing_page", model=None, cost=0,
                       approved_by=appr.approver if appr.approved else None,
                       outcome="approved" if appr.approved else "rejected", detail=appr.reason)
        if appr.approved:
            publish_note = publish_landing_page(copy, appr)
            ctx.log.record(AGENT, "publish_landing_page", model=None, cost=0, approved_by=appr.approver,
                           detail="STUBBED: not actually published")
            approved = True
        else:
            publish_note = appr.reason

    body = ["### Landing page copy (draft)", copy or "_(none)_", "", "### Experiment", experiment or "_(none)_", "",
            "### Success criteria (set before the test runs)"]
    body += [f"- {c}" for c in criteria] or ["- _(none)_"]
    body += ["", "### Publishing (STUBBED)", publish_note]
    return StepResult(
        title="Validation plan (smoke test)",
        summary=experiment,
        body="\n".join(body),
        metrics={"guardrail_violations": len(violations), "founder_approved": approved, "success_criteria": len(criteria)},
        labels=["publishing STUBBED"],
    )
