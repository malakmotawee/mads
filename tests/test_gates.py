import pytest

import gates


def test_thresholds_are_read_only():
    with pytest.raises(TypeError):
        gates.THRESHOLDS["phase2_step2_demand"]["min_wtp_positive"] = 0


def test_opportunities_go():
    m = {"sourced_claims": 8, "distinct_domains": 4, "pain": 4, "assumption_ratio": 0.1}
    assert gates.evaluate("phase1_step1_opportunities", m).outcome == gates.GO


def test_opportunities_pivot_when_pain_not_confirmed():
    m = {"sourced_claims": 8, "distinct_domains": 4, "pain": 1, "assumption_ratio": 0.1}
    assert gates.evaluate("phase1_step1_opportunities", m).outcome == gates.PIVOT


def test_weak_evidence_repeats_then_stops():
    m = {"sourced_claims": 1, "distinct_domains": 1, "pain": 0, "assumption_ratio": 0.8}
    assert gates.evaluate("phase1_step1_opportunities", m, attempt=0).outcome == gates.REPEAT
    assert gates.evaluate("phase1_step1_opportunities", m, attempt=gates.MAX_REPEATS).outcome == gates.STOP


def test_saturated_free_market_stops():
    m = {"sourced_claims": 9, "distinct_domains": 5, "free_alternative": 6, "paid_price_points": 0}
    assert gates.evaluate("phase2_step1_competitors", m).outcome == gates.STOP


def test_demand_stop_when_negative_outweighs_positive():
    m = {"wtp_positive": 1, "wtp_negative": 4, "wtp_positive_domains": 1}
    assert gates.evaluate("phase2_step2_demand", m).outcome == gates.STOP


def test_demand_go():
    m = {"wtp_positive": 4, "wtp_negative": 1, "wtp_positive_domains": 3}
    assert gates.evaluate("phase2_step2_demand", m).outcome == gates.GO


def test_validation_plan_needs_founder_approval():
    m = {"guardrail_violations": 0, "founder_approved": False}
    assert gates.evaluate("phase2_step3_validation_plan", m, attempt=gates.MAX_REPEATS).outcome == gates.STOP
    assert gates.evaluate("phase2_step3_validation_plan", {**m, "founder_approved": True}).outcome == gates.GO


def test_stub_gate_requires_approval_when_publishing():
    m = {"artifact_produced": True, "needs_approval": True, "founder_approved": False}
    d = gates.evaluate("phase5_step2_checkout", m, attempt=gates.MAX_REPEATS)
    assert d.outcome == gates.STOP and d.stubbed
    d = gates.evaluate("phase5_step1_listing", m, attempt=gates.MAX_REPEATS)
    assert d.outcome == gates.STOP and not d.stubbed


def test_build_gate_needs_passing_acceptance_checks():
    m = {"artifact_produced": True, "failed_checks": 2, "guardrail_violations": 0}
    assert gates.evaluate("phase3_step1_product_spec", m).outcome == gates.REPEAT
    assert gates.evaluate("phase3_step1_product_spec", m, attempt=gates.MAX_REPEATS).outcome == gates.STOP
    assert gates.evaluate("phase3_step1_product_spec", {**m, "failed_checks": 0}).outcome == gates.GO


def test_drafting_gate_stops_on_guardrail_violations():
    m = {"artifact_produced": True, "guardrail_violations": 1}
    assert gates.evaluate("phase4_step1_offer", m, attempt=gates.MAX_REPEATS).outcome == gates.STOP


def test_problem_gate_does_not_punish_listing_assumptions():
    m = {"supporting_sourced_claims": 7, "open_assumptions": 6}
    assert gates.evaluate("phase1_step2_problem", m).outcome == gates.GO


def test_problem_gate_fails_when_assumptions_outnumber_evidence():
    m = {"supporting_sourced_claims": 3, "open_assumptions": 5}
    assert gates.evaluate("phase1_step2_problem", m).outcome == gates.REPEAT
    assert gates.evaluate("phase1_step2_problem", m, attempt=gates.MAX_REPEATS).outcome == gates.STOP
    assert gates.evaluate("phase1_step2_problem", {"supporting_sourced_claims": 2, "open_assumptions": 0},
                          attempt=gates.MAX_REPEATS).outcome == gates.STOP
