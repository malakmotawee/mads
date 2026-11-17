"""Gates between steps: go / repeat / pivot / stop.

All thresholds are fixed here, before any run, and are read-only at runtime.
Metrics are computed in code from validated claims (a claim only counts as
sourced if its URL was actually returned by the web search), never by the LLM.

Weak evidence is retried at most MAX_REPEATS times with new search queries;
if it is still weak, the gate recommends STOP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

GO, REPEAT, PIVOT, STOP = "go", "repeat", "pivot", "stop"
OUTCOMES = (GO, REPEAT, PIVOT, STOP)
MAX_REPEATS = 1


def _freeze(d: dict[str, dict[str, float]]) -> Mapping[str, Mapping[str, float]]:
    return MappingProxyType({k: MappingProxyType(v) for k, v in d.items()})


THRESHOLDS = _freeze(
    {
        "phase1_step1_opportunities": {
            "min_sourced_claims": 6,
            "min_distinct_domains": 3,
            "min_pain_signals": 3,
            "max_assumption_ratio": 0.4,
            "stop_below_sourced_claims": 2,
        },
        "phase1_step2_problem": {
            "min_supporting_sourced_claims": 3,
            # Open assumptions are not penalised by count (that would reward hiding them);
            # they go to Phase 2 as hypotheses. The statement fails only if it rests on
            # more assumptions than sourced claims. Changed 2026-11-17, see ARCHITECTURE.md.
            "max_assumptions_per_sourced_claim": 1.0,
        },
        "phase2_step1_competitors": {
            "min_sourced_claims": 5,
            "min_distinct_domains": 3,
            "min_paid_price_points": 1,
            "stop_if_free_alternatives_at_least": 5,
            "stop_below_sourced_claims": 2,
        },
        "phase2_step2_demand": {
            "min_wtp_positive": 3,
            "min_wtp_positive_domains": 3,
            "stop_if_negative_to_positive_ratio_at_least": 2.0,
            "stop_if_negative_at_least": 2,
        },
        "phase2_step3_validation_plan": {
            "max_guardrail_violations": 0,
            "requires_founder_approval": 1,
        },
    }
)

# Drafting steps in phases 3-6 use the LLM but evaluate no market evidence. Their gate
# checks that the artifact exists, that it broke no guardrail, that its code-level
# acceptance checks passed (Phase 3) and, where the step publishes, that the founder approved.
DRAFT_STEPS = (
    "phase3_step1_product_spec",
    "phase4_step1_offer",
    "phase5_step1_listing",
    "phase6_step1_operate",
)
# MOCKED steps: same checks, labelled as MOCKED.
STUB_STEPS = (
    "phase5_step2_checkout",
    "phase5_step3_delivery",
)


@dataclass
class GateDecision:
    step_key: str
    outcome: str
    reasons: list[str]
    metrics: dict[str, Any]
    thresholds: dict[str, Any]
    attempt: int
    stubbed: bool = False
    recommendation: str = field(default="")

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"bad outcome {self.outcome}")
        if not self.recommendation:
            self.recommendation = {
                GO: "Proceed to the next step.",
                REPEAT: "Evidence is not yet sufficient: re-run this step with different search queries.",
                PIVOT: "Evidence points away from the idea as stated: rework the brief toward what the evidence supports, then re-run.",
                STOP: "STOP: the evidence does not support continuing. Do not invest further in this idea as stated.",
            }[self.outcome]


def _weak(reasons: list[str], attempt: int) -> str:
    if attempt < MAX_REPEATS:
        return REPEAT
    reasons.append(f"still below thresholds after {attempt + 1} attempt(s); recommending STOP on weak evidence")
    return STOP


def evaluate(step_key: str, metrics: Mapping[str, Any], attempt: int = 0) -> GateDecision:
    m = dict(metrics)
    if step_key in STUB_STEPS or step_key in DRAFT_STEPS:
        return _stub_gate(step_key, m, attempt)
    if step_key not in THRESHOLDS:
        raise KeyError(f"no gate defined for {step_key}")
    t = THRESHOLDS[step_key]
    reasons: list[str] = []

    def check(name: str, ok: bool, text: str) -> bool:
        reasons.append(("PASS " if ok else "FAIL ") + text)
        return ok

    if m.get("guardrail_block"):
        reasons.append(f"guardrail block: {m['guardrail_block']}")
        return GateDecision(step_key, STOP, reasons, m, dict(t), attempt)

    if step_key == "phase1_step1_opportunities":
        s, d, p, r = m.get("sourced_claims", 0), m.get("distinct_domains", 0), m.get("pain", 0), m.get("assumption_ratio", 1.0)
        volume = all([
            check("sourced", s >= t["min_sourced_claims"], f"sourced claims {s} >= {t['min_sourced_claims']}"),
            check("domains", d >= t["min_distinct_domains"], f"distinct source domains {d} >= {t['min_distinct_domains']}"),
            check("ratio", r <= t["max_assumption_ratio"], f"assumption ratio {r:.2f} <= {t['max_assumption_ratio']}"),
        ])
        pain_ok = check("pain", p >= t["min_pain_signals"], f"sourced pain signals {p} >= {t['min_pain_signals']}")
        if volume and pain_ok:
            outcome = GO
        elif volume and p >= 1:
            reasons.append("the space is discussed, but sources do not confirm the stated problem")
            outcome = PIVOT
        elif volume and p == 0:
            reasons.append("plenty of sources, none showing the stated pain")
            outcome = STOP
        else:
            if s < t["stop_below_sourced_claims"]:
                reasons.append(f"almost no sourced evidence ({s} < {t['stop_below_sourced_claims']})")
            outcome = _weak(reasons, attempt)

    elif step_key == "phase1_step2_problem":
        s, a = m.get("supporting_sourced_claims", 0), m.get("open_assumptions", 99)
        ok = all([
            check("support", s >= t["min_supporting_sourced_claims"], f"problem statement backed by {s} sourced claims >= {t['min_supporting_sourced_claims']}"),
            check("assumptions", a <= s * t["max_assumptions_per_sourced_claim"],
                  f"open assumptions {a} <= {t['max_assumptions_per_sourced_claim']} x sourced support {s}"),
        ])
        outcome = GO if ok else _weak(reasons, attempt)

    elif step_key == "phase2_step1_competitors":
        s, d = m.get("sourced_claims", 0), m.get("distinct_domains", 0)
        free, paid = m.get("free_alternative", 0), m.get("paid_price_points", 0)
        if free >= t["stop_if_free_alternatives_at_least"] and paid == 0:
            reasons.append(f"FAIL market saturated: {free} sourced free alternatives and no sourced paid price point")
            outcome = STOP
        else:
            ok = all([
                check("sourced", s >= t["min_sourced_claims"], f"sourced claims {s} >= {t['min_sourced_claims']}"),
                check("domains", d >= t["min_distinct_domains"], f"distinct source domains {d} >= {t['min_distinct_domains']}"),
                check("paid", paid >= t["min_paid_price_points"], f"sourced paid price points {paid} >= {t['min_paid_price_points']}"),
            ])
            outcome = GO if ok else _weak(reasons, attempt)

    elif step_key == "phase2_step2_demand":
        pos, neg, pd = m.get("wtp_positive", 0), m.get("wtp_negative", 0), m.get("wtp_positive_domains", 0)
        ratio = neg / max(pos, 1)
        if neg >= t["stop_if_negative_at_least"] and ratio >= t["stop_if_negative_to_positive_ratio_at_least"]:
            reasons.append(f"FAIL sourced evidence against paying ({neg}) outweighs evidence for paying ({pos}) by {ratio:.1f}x")
            outcome = STOP
        else:
            ok = all([
                check("pos", pos >= t["min_wtp_positive"], f"sourced willingness-to-pay signals {pos} >= {t['min_wtp_positive']}"),
                check("pd", pd >= t["min_wtp_positive_domains"], f"from {pd} distinct domains >= {t['min_wtp_positive_domains']}"),
                check("net", pos > neg, f"positive signals {pos} > negative signals {neg}"),
            ])
            outcome = GO if ok else _weak(reasons, attempt)

    elif step_key == "phase2_step3_validation_plan":
        v, approved = m.get("guardrail_violations", 0), bool(m.get("founder_approved"))
        clean = check("guardrails", v <= t["max_guardrail_violations"], f"guardrail violations {v} <= {t['max_guardrail_violations']}")
        appr = check("approval", approved, "founder approved publishing the smoke test")
        if clean and appr:
            outcome = GO
        else:
            if not appr:
                reasons.append("halted: nothing is published without founder approval")
            outcome = _weak(reasons, attempt)
    else:  # pragma: no cover
        raise KeyError(step_key)

    return GateDecision(step_key, outcome, reasons, m, dict(t), attempt)


def _stub_gate(step_key: str, m: dict[str, Any], attempt: int) -> GateDecision:
    stubbed = step_key in STUB_STEPS
    reasons = ["MOCKED step: no market evidence is evaluated here" if stubbed
               else "drafting step: checks the artifact, guardrails, tests and approval; no market evidence is evaluated here"]
    if not m.get("artifact_produced"):
        reasons.append("FAIL step produced no artifact")
        return GateDecision(step_key, _weak(reasons, attempt), reasons, m, {}, attempt, stubbed=stubbed)
    if m.get("guardrail_violations", 0):
        reasons.append(f"FAIL draft broke {m['guardrail_violations']} guardrail rule(s)")
        return GateDecision(step_key, _weak(reasons, attempt), reasons, m, {}, attempt, stubbed=stubbed)
    if m.get("failed_checks", 0):
        reasons.append(f"FAIL {m['failed_checks']} acceptance check(s) failed")
        return GateDecision(step_key, _weak(reasons, attempt), reasons, m, {}, attempt, stubbed=stubbed)
    if "failed_checks" in m:
        reasons.append("PASS all acceptance checks")
    if m.get("needs_approval") and not m.get("founder_approved"):
        reasons.append("FAIL founder did not approve; nothing was published")
        return GateDecision(step_key, _weak(reasons, attempt), reasons, m, {}, attempt, stubbed=stubbed)
    reasons.append("PASS artifact produced" + (" and founder approved" if m.get("needs_approval") else ""))
    return GateDecision(step_key, GO, reasons, m, {}, attempt, stubbed=stubbed)
