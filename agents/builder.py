"""Phase 3 (Build): drafts the MVP and its user guide (real, LLM), then tests the draft in code.

The gate after this step is a "passing tests" gate: structural checks run here in
code, never by the LLM. Shipping the product to a host or store is STUBBED.
"""
from __future__ import annotations

from agents.common import RunContext, StepResult, as_list, ask_json, guard_fields, load_prompt

AGENT = "builder"


def _components(data: dict) -> list[dict[str, str]]:
    out = []
    for c in as_list(data.get("components")):
        if isinstance(c, dict) and str(c.get("name") or "").strip():
            out.append({k: " ".join(str(c.get(k) or "").split()) for k in ("name", "purpose", "contents")})
    return out


def _tests(data: dict) -> list[dict[str, str]]:
    out = []
    for t in as_list(data.get("acceptance_tests")):
        if isinstance(t, dict) and str(t.get("test") or "").strip():
            out.append({"test": " ".join(str(t["test"]).split()), "component": str(t.get("component") or "").strip()})
    return out


def run_checks(components: list[dict[str, str]], guide: str, tests: list[dict[str, str]]) -> list[tuple[str, bool]]:
    """Code-level acceptance checks on the drafted MVP. Each is (description, passed)."""
    names = [c["name"] for c in components]
    lower_guide = guide.lower()
    checks = [
        (f"at least 3 components ({len(components)})", len(components) >= 3),
        ("every component has contents", bool(components) and all(len(c["contents"]) >= 20 for c in components)),
        ("every component states the problem it solves", bool(components) and all(c["purpose"] for c in components)),
        ("user guide mentions every component", bool(names) and all(n.lower() in lower_guide for n in names)),
        (f"at least 3 acceptance tests ({len(tests)})", len(tests) >= 3),
        ("every acceptance test targets an existing component",
         bool(tests) and all(t["component"].lower() in {n.lower() for n in names} for t in tests)),
    ]
    return checks


def product_spec(ctx: RunContext, attempt: int) -> StepResult:
    problem = ctx.results.get("phase1_step2_problem")
    plan = ctx.results.get("phase2_step3_validation_plan")
    prev = ctx.results.get("phase3_step1_product_spec") if attempt else None
    failed_before = prev.data.get("failed", []) if prev else []
    extra = ("\n\nThe previous draft failed these acceptance checks; fix every one:\n"
             + "\n".join(f"- {f}" for f in failed_before)) if failed_before else ""
    data = ask_json(
        ctx, AGENT, "draft_mvp", load_prompt("builder"),
        f"FOUNDER BRIEF:\n{ctx.brief.as_text()}\n\nPROBLEM:\n{problem.summary if problem else ''}\n\n"
        f"SMOKE TEST AND SUCCESS CRITERIA:\n{plan.summary if plan else ''}\n"
        + "\n".join(f"- {c}" for c in (plan.data.get("success_criteria", []) if plan else [])) + extra,
    )
    components, tests = _components(data), _tests(data)
    texts = {"product_name": str(data.get("product_name") or ""), "format": str(data.get("format") or ""),
             "user_guide": str(data.get("user_guide") or "")}
    texts.update({f"component_{i}": c["contents"] for i, c in enumerate(components)})
    clean, violations = guard_fields(ctx, AGENT, texts)
    for i, c in enumerate(components):
        c["contents"] = clean[f"component_{i}"]
    checks = run_checks(components, clean["user_guide"], tests)
    failed = [d for d, ok in checks if not ok]
    ctx.log.record(AGENT, "test_mvp", model=None, cost=0, outcome="pass" if not failed else "fail",
                   detail=f"{len(checks) - len(failed)}/{len(checks)} acceptance checks passed")

    body = [f"### Product: {clean['product_name'] or '_(unnamed)_'}", f"Format: {clean['format'] or '_(none)_'}", "",
            "### Components (the MVP content)"]
    for c in components:
        body += [f"#### {c['name']}", f"*Solves:* {c['purpose']}", "", c["contents"], ""]
    body += ["### User guide", clean["user_guide"] or "_(none)_", "", "### Acceptance tests (for the buyer)"]
    body += [f"- [{t['component']}] {t['test']}" for t in tests] or ["- _(none)_"]
    body += ["", "### Automated checks on this draft (run in code)"]
    body += [f"- {'PASS' if ok else 'FAIL'} {d}" for d, ok in checks]
    body += ["", "### Shipping (STUBBED)", "STUBBED: the draft is not uploaded to any host or store; the founder builds it from this spec."]
    return StepResult(
        title="MVP draft and user guide",
        summary=f"{clean['product_name']}: {clean['format']}",
        body="\n".join(body),
        data={"product_name": clean["product_name"], "components": [c["name"] for c in components], "failed": failed},
        metrics={"artifact_produced": bool(components), "failed_checks": len(failed), "guardrail_violations": violations},
        labels=["shipping STUBBED"],
    )
