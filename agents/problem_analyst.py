"""Phase 1, step 2 (Discover): turn the evidence into a problem statement.

No new searching: the analyst may only cite claims from step 1. Supporting
claim IDs are checked in code, and only sourced claims count as support.
"""
from __future__ import annotations

import json

import guardrails
from agents.common import RunContext, StepResult, ask_json, load_prompt

AGENT = "problem_analyst"


def define_problem(ctx: RunContext, attempt: int) -> StepResult:
    evidence = ctx.results.get("phase1_step1_opportunities")
    claims = evidence.claims if evidence else []
    by_id = {c.id: c for c in claims}
    listing = json.dumps([{"id": c.id, "text": c.text, "type": c.type, "source": c.source} for c in claims], indent=1)
    data = ask_json(
        ctx, AGENT, "define_problem", load_prompt("problem_analyst"),
        f"FOUNDER BRIEF:\n{ctx.brief.as_text()}\n\nEVIDENCE CLAIMS FROM STEP 1:\n{listing}\n\nATTEMPT: {attempt + 1}",
        sources=evidence.sources if evidence else [],
    )
    ids = [str(i).strip() for i in data.get("supporting_claim_ids", []) if str(i).strip() in by_id]
    supporting = [by_id[i] for i in dict.fromkeys(ids)]
    sourced_support = [c for c in supporting if c.sourced]
    assumptions = [str(a).strip() for a in data.get("assumptions", []) if str(a).strip()]
    statement, hits1 = guardrails.redact(str(data.get("problem_statement") or "").strip())
    customer, hits2 = guardrails.redact(str(data.get("target_customer") or "").strip())

    body = [
        "### Target customer", customer or "_(none produced)_", "",
        "### Problem statement", statement or "_(none produced)_", "",
        "### Supporting evidence (from step 1)",
    ]
    body += [f"- [{c.id}] {c.text} ({c.source})" for c in supporting] or ["- _(none)_"]
    body += ["", "### Open assumptions (each labelled ASSUMPTION)"]
    body += [f"- ASSUMPTION: {a}" for a in assumptions] or ["- _(none listed)_"]
    notes = []
    if len(ids) < len(data.get("supporting_claim_ids", []) or []):
        notes.append("some cited claim IDs did not exist in step 1 and were ignored")
    if hits1 or hits2:
        notes.append("guardrails removed text from the problem statement")
    return StepResult(
        title="Problem definition",
        summary=statement,
        body="\n".join(body),
        metrics={"supporting_claims": len(supporting), "supporting_sourced_claims": len(sourced_support),
                 "open_assumptions": len(assumptions)},
        data={"target_customer": customer, "problem_statement": statement, "assumptions": assumptions},
        notes=notes,
    )
