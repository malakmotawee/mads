"""Phase 6 (Operate and learn): STUBBED. No live sales data is connected."""
from __future__ import annotations

from agents.common import RunContext, StepResult

AGENT = "operator"


def operate(ctx: RunContext, attempt: int) -> StepResult:
    body = "\n".join([
        "**STUBBED**: no live metrics are connected, so nothing is measured.",
        "", "Planned loop (not executed):",
        "- Weekly: reconcile orders, payments, fees and payouts (reconcile.py, MOCKED today)",
        "- Compare results with the success criteria set in Phase 2 step 3",
        "- Feed the result back into the gates: go / repeat / pivot / stop",
    ])
    ctx.log.record(AGENT, "operate_review", model=None, cost=0, detail="STUBBED")
    return StepResult(title="Operate and learn (STUBBED)", body=body, labels=["STUBBED"], metrics={"artifact_produced": True})
