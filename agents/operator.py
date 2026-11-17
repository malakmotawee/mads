"""Phase 6 (Operate and learn): support plan, metrics and a persevere-or-pivot memo (real, LLM).

No live sales or usage data is connected (STUBBED), so the memo sets decision
rules from the Phase 2 success criteria; it never reports results.
"""
from __future__ import annotations

from agents.common import RunContext, StepResult, as_list, ask_json, guard_fields, load_prompt

AGENT = "operator"


def operate(ctx: RunContext, attempt: int) -> StepResult:
    plan = ctx.results.get("phase2_step3_validation_plan")
    criteria = plan.data.get("success_criteria", []) if plan else []
    history = ctx.results.get("_gate_history")
    gate_lines = history.data.get("lines", []) if history else []
    data = ask_json(
        ctx, AGENT, "draft_operating_plan", load_prompt("operator"),
        f"FOUNDER BRIEF:\n{ctx.brief.as_text()}\n\nPHASE 2 SUCCESS CRITERIA:\n"
        + ("\n".join(f"- {c}" for c in criteria) or "none") + "\n\nGATE OUTCOMES SO FAR:\n" + ("\n".join(gate_lines) or "none")
        + "\n\nLIVE DATA: none connected.",
    )
    metrics = [str(m).strip() for m in as_list(data.get("metrics_to_track")) if str(m).strip()]
    texts = {k: str(data.get(k) or "").strip() for k in ("support_plan", "review_cadence", "memo")}
    texts.update({f"metric_{i}": m for i, m in enumerate(metrics)})
    clean, violations = guard_fields(ctx, AGENT, texts)

    body = ["**STUBBED data**: no live sales or usage data is connected, so nothing below is a measured result.", "",
            "### Metrics to track"] + ([f"- {clean[f'metric_{i}']}" for i in range(len(metrics))] or ["- _(none)_"])
    body += ["", "### Support plan", clean["support_plan"] or "_(none)_", "", "### Review cadence", clean["review_cadence"] or "_(none)_",
             "", "### Persevere-or-pivot memo", clean["memo"] or "_(none)_"]
    return StepResult(title="Operate and learn", body="\n".join(body), labels=["live data STUBBED"],
                      metrics={"artifact_produced": bool(clean["memo"]), "guardrail_violations": violations})
