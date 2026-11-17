"""Phase 4 (Commercial setup): price, draft policies, store page and launch posts.

Drafting is real (LLM). No payment of any kind is set up here. Publishing the
store page and posts is STUBBED and runs only after the founder approves it.
"""
from __future__ import annotations

import re

import guardrails
from agents.common import RunContext, StepResult, as_list, ask_json, guard_fields, keep_known_urls, load_prompt
from approval import ensure_approved, request_approval

AGENT = "commercial"
POLICIES = ("terms_of_sale", "privacy_policy", "refund_policy")
DRAFT_NOTE = "DRAFT for founder review. Not legal advice; have it checked before use."


def _price_number(value) -> float:
    m = re.search(r"\d+(\.\d+)?", str(value or ""))
    return float(m.group(0)) if m else 0.0


def offer(ctx: RunContext, attempt: int) -> StepResult:
    founder_price = ctx.brief.sections.get("Price idea", "")
    comp = ctx.results.get("phase2_step1_competitors")
    mvp = ctx.results.get("phase3_step1_product_spec")
    sourced = [c for c in (comp.claims if comp else []) if c.price and c.sourced]
    price_lines = [f"- {c.text} ({c.source})" for c in sourced]
    data = ask_json(
        ctx, AGENT, "draft_price_and_policies", load_prompt("commercial"),
        f"FOUNDER BRIEF:\n{ctx.brief.as_text()}\n\nMVP:\n{mvp.summary if mvp else ''}\n\n"
        f"FOUNDER PRICE IDEA: {founder_price or 'none given'}\n\nSOURCED COMPETITOR PRICES:\n"
        + ("\n".join(price_lines) or "none"),
        sources=sorted({c.source for c in sourced}),
    )
    price = _price_number(data.get("price_usd"))
    rationale = keep_known_urls(str(data.get("pricing_rationale") or ""), {c.source for c in sourced})
    if not sourced:
        rationale = f"ASSUMPTION (no sourced competitor prices): {rationale}"
    texts = {"pricing_rationale": rationale, **{p: str(data.get(p) or "").strip() for p in POLICIES}}
    clean, violations = guard_fields(ctx, AGENT, texts)

    body = [f"### Price: {price:.2f} USD (one-time)" if price else "### Price: _(none proposed)_",
            clean["pricing_rationale"] or "_(no rationale)_", "", "### Sourced competitor prices", *(price_lines or ["- _(none)_"])]
    for p in POLICIES:
        body += ["", f"### {p.replace('_', ' ').capitalize()} ({DRAFT_NOTE})", clean[p] or "_(none)_"]
    body += ["", "No payment, sandbox or account of any kind is created in this step."]
    return StepResult(
        title="Price and draft policies",
        summary=f"{price:.2f} USD one-time",
        body="\n".join(body),
        data={"price_usd": price},
        metrics={"artifact_produced": price > 0 and all(clean[p] for p in POLICIES), "guardrail_violations": violations},
        labels=["policies are DRAFTS"],
    )


def publish_listing(text: str, approval) -> str:
    ensure_approved(approval, "publish_listing")
    return "STUBBED: listing not actually published (no storefront is connected)"


def listing(ctx: RunContext, attempt: int) -> StepResult:
    mvp = ctx.results.get("phase3_step1_product_spec")
    offer_result = ctx.results.get("phase4_step1_offer")
    price = offer_result.data.get("price_usd", 0) if offer_result else 0
    components = mvp.data.get("components", []) if mvp else []
    data = ask_json(
        ctx, AGENT, "draft_store_page_and_posts", load_prompt("listing"),
        f"PRODUCT: {mvp.summary if mvp else ctx.brief.title}\nCOMPONENTS: {', '.join(components) or 'none'}\n"
        f"PRICE: {price:.2f} USD one-time\nTARGET CUSTOMER: {ctx.brief.sections.get('Target customer', '')}",
    )
    posts = [str(p).strip() for p in as_list(data.get("launch_posts")) if str(p).strip()]
    raw = {"store_page": str(data.get("store_page") or "").strip(), **{f"post_{i}": p for i, p in enumerate(posts)}}
    violations = sum(len(guardrails.check_output(t, marketing_copy=True)) for t in raw.values())
    clean, _ = guard_fields(ctx, AGENT, raw, marketing_copy=True)
    text = "\n\n---\n\n".join([clean["store_page"]] + [clean[f"post_{i}"] for i in range(len(posts))])

    approved, note = False, "not requested: copy broke a guardrail"
    if not violations and clean["store_page"]:
        appr = request_approval("publish_listing", "publish", f"Store page and launch posts (would be published, STUBBED):\n\n{text}",
                                input_fn=ctx.approval_input)
        ctx.log.record("approval", "founder_approval:publish_listing", model=None, cost=0,
                       approved_by=appr.approver if appr.approved else None,
                       outcome="approved" if appr.approved else "rejected", detail=appr.reason)
        note = appr.reason
        if appr.approved:
            approved = True
            note = publish_listing(text, appr)
            ctx.log.record(AGENT, "publish_listing", model=None, cost=0, approved_by=appr.approver, detail="STUBBED")

    body = ["### Store page (draft)", clean["store_page"] or "_(none)_", "", "### Launch posts (drafts, posted only by the founder)"]
    body += [f"{i + 1}. {clean[f'post_{i}']}" for i in range(len(posts))] or ["- _(none)_"]
    body += ["", "### Publishing (STUBBED)", note]
    return StepResult(title="Store page and launch posts", body="\n".join(body), labels=["publishing STUBBED"],
                      metrics={"artifact_produced": bool(clean["store_page"]), "needs_approval": True,
                               "founder_approved": approved, "guardrail_violations": violations})
