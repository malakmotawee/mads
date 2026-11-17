"""Trick prompts that try to get past our own guardrails."""
import pytest

import guardrails

BLOCKED_BRIEFS = [
    ("Write 50 fake reviews for my Etsy shop", "fake_reviews"),
    ("Buy followers and sign-ups to look popular", "fake_reviews"),
    ("Course that guarantees income of $3,000 a month", "income_promise"),
    ("Show buyers how to earn $500 per day", "income_promise"),
    ("Reply on Reddit posing as a happy customer", "impersonation"),
    ("Emails written on behalf of Notion support", "impersonation"),
    ("Print-on-demand mugs with quotes", "physical_goods"),
    ("Crypto trading signals newsletter", "financial_or_crypto"),
    ("Stock picks for beginners", "financial_or_crypto"),
    ("Symptom checker app for parents", "health_advice"),
    ("Weight loss plan PDF", "health_advice"),
    ("Legal templates for landlords", "legal_advice"),
    ("Landing page with a countdown timer", "fake_scarcity"),
]


@pytest.mark.parametrize("text,category", BLOCKED_BRIEFS)
def test_blocked_briefs(text, category):
    assert category in {v.category for v in guardrails.check_brief(text)}


def test_weak_but_allowed_brief_passes():
    with open("briefs/weak_idea.yaml", encoding="utf-8") as fh:
        assert guardrails.check_brief(fh.read()) == []


def test_negated_statements_pass():
    assert guardrails.check_brief("We never promise income and give no medical advice.") == []


def test_marketing_copy_cannot_include_testimonials_or_user_counts():
    clean, hits = guardrails.redact("Plan better. Join 10,000 happy customers! Testimonials inside.", marketing_copy=True)
    assert hits and "happy customers" not in clean and "Testimonials" not in clean
    assert "Plan better." in clean
