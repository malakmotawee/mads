"""End-to-end smoke test of the orchestrator with a fake LLM and fake search (offline)."""
import json
import os

import gates
from decision_log import REQUIRED_KEYS
from orchestrator import run_pipeline
from tests.fakes import FakeLLM, FakeSearch

STRONG = {
    "Researcher": [("pain", None)] * 6 + [("workaround", None)],
    "Competitor": [("competitor", None)] * 3 + [("free_alternative", None)] * 2,
    "Demand": [("wtp_positive", None)] * 4 + [("wtp_negative", None)],
}
WEAK = {
    "Researcher": [("pain", None)] * 6,
    "Competitor": [("free_alternative", None)] * 6,
    "Demand": [],
}


def run(tmp_path, claims, answer=None, brief="briefs/weak_idea.yaml", llm=None):
    out, log = tmp_path / "outputs", tmp_path / "decision_log.json"
    res = run_pipeline(brief, llm=llm or FakeLLM(claims), search=FakeSearch(), out_dir=str(out), log_path=str(log),
                       approval_input=(lambda _: answer) if answer else (lambda _: "reject"), echo=lambda *_: None)
    return res, out, json.loads(log.read_text())


def test_weak_evidence_stops(tmp_path):
    res, out, log = run(tmp_path, WEAK)
    assert res["final_outcome"] == gates.STOP and res["halted_at"] == "phase2_step1_competitors"
    assert (out / "phase2_gate_competitors.md").exists()
    assert "Outcome: STOP" in (out / "phase2_gate_competitors.md").read_text()


def test_decision_log_entries_have_required_keys(tmp_path):
    _, _, log = run(tmp_path, WEAK)
    assert log
    for e in log:
        assert all(k in e for k in REQUIRED_KEYS)
        assert isinstance(e["sources"], list) and isinstance(e["cost"], (int, float))
    assert any(e["agent"] == "gate" and e.get("outcome") == "stop" for e in log)


def test_output_file_names(tmp_path):
    _, out, _ = run(tmp_path, WEAK)
    for name in os.listdir(out):
        assert name.startswith("phase") and ("_step" in name or "_gate_" in name), name


def test_invented_source_is_relabelled_assumption(tmp_path):
    claims = dict(WEAK, Researcher=[("pain", "https://invented.example/not-in-results")])
    _, out, _ = run(tmp_path, claims)
    text = (out / "phase1_step1_opportunities.md").read_text()
    row = next(line for line in text.splitlines() if line.startswith("| O1 |"))
    assert "ASSUMPTION" in row and "invented.example" not in row


def test_fake_testimonials_in_copy_are_never_offered_for_publishing(tmp_path):
    asked = []
    llm = FakeLLM(STRONG, landing_copy="Loved by 5,000 happy customers. Read our testimonials.")
    out, logp = tmp_path / "o", tmp_path / "l.json"
    res = run_pipeline("briefs/weak_idea.yaml", llm=llm, search=FakeSearch(), out_dir=str(out), log_path=str(logp),
                       approval_input=lambda p: asked.append(p) or "approve", echo=lambda *_: None)
    assert res["halted_at"] == "phase2_step3_validation_plan" and res["final_outcome"] == gates.STOP
    assert asked == []


def test_nothing_published_without_approval(tmp_path):
    res, _, log = run(tmp_path, STRONG, answer="reject")
    assert res["halted_at"] == "phase2_step3_validation_plan"
    assert not any(e["action"] == "publish_landing_page" for e in log)
    assert not any(e["approved_by"] for e in log)


def test_full_run_with_founder_approvals(tmp_path):
    res, out, log = run(tmp_path, STRONG, answer="approve")
    assert res["final_outcome"] == gates.GO and res["halted_at"] is None
    published = [e for e in log if e["action"] in ("publish_landing_page", "publish_listing", "create_checkout")]
    assert len(published) == 3 and all(e["approved_by"] == "founder" for e in published)
    assert "STUBBED" in (out / "phase3_step1_product_spec.md").read_text()
    assert "MOCKED" in (out / "phase5_step2_checkout.md").read_text()
    assert "Lean Canvas" in (out / "phase2_step3_validation_plan.md").read_text()
    spec = (out / "phase3_step1_product_spec.md").read_text()
    assert "PASS every acceptance test targets an existing component" in spec and "FAIL" not in spec
    offer = (out / "phase4_step1_offer.md").read_text()
    assert "invented.example" not in offer and "ASSUMPTION" in offer and "Not legal advice" in offer
    assert "Persevere-or-pivot memo" in (out / "phase6_step1_operate.md").read_text()


def test_mvp_failing_acceptance_checks_stops_at_build(tmp_path):
    class BrokenGuide(FakeLLM):
        def complete(self, system, user):
            res = super().complete(system, user)
            if "Builder" in system.splitlines()[0]:
                res.text = res.text.replace("Duplicate the kit, then open", "Read the docs")
                res.text = res.text.replace("Event planner, Budget tracker, Sponsor outreach", "")
            return res
    res, out, _ = run(tmp_path, STRONG, answer="approve", llm=BrokenGuide(STRONG))
    assert res["halted_at"] == "phase3_step1_product_spec" and res["final_outcome"] == gates.STOP
    assert "FAIL user guide mentions every component" in (out / "phase3_step1_product_spec.md").read_text()


def test_store_page_with_fake_reviews_is_never_offered_for_publishing(tmp_path):
    asked = []
    llm = FakeLLM(STRONG, store_page="Rated 5 stars by 2,000 clubs! Only 3 left, buy today.")
    out, logp = tmp_path / "o", tmp_path / "l.json"
    res = run_pipeline("briefs/good_idea.yaml", llm=llm, search=FakeSearch(), out_dir=str(out), log_path=str(logp),
                       approval_input=lambda p: asked.append(p) or "approve", echo=lambda *_: None)
    assert res["halted_at"] == "phase5_step1_listing" and res["final_outcome"] == gates.STOP
    log = json.loads(logp.read_text())
    assert not any("publish_listing" in e["action"] for e in log)


def test_guardrail_brief_stops_before_any_agent(tmp_path):
    brief = tmp_path / "bad.md"
    brief.write_text("# Bad\n\n## Idea\nA crypto trading signals PDF.\n")
    llm = FakeLLM(STRONG)
    res, out, log = run(tmp_path, STRONG, brief=str(brief), llm=llm)
    assert res["halted_at"] == "brief_screen" and llm.calls == 0
    assert (out / "phase1_gate_brief_screen.md").exists()


def test_good_brief_runs_end_to_end_with_approvals(tmp_path):
    res, out, _ = run(tmp_path, STRONG, answer="approve", brief="briefs/good_idea.yaml")
    assert res["final_outcome"] == gates.GO
    assert "Outcome: GO" in (out / "phase6_gate_operate.md").read_text()
