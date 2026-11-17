import dataclasses

import pytest

from agents.experiment_designer import publish_landing_page
from approval import Approval, ApprovalRequired, ensure_approved, request_approval


def test_non_interactive_is_rejected(monkeypatch):
    class NoTTY:
        def isatty(self):
            return False
    monkeypatch.setattr("sys.stdin", NoTTY())
    a = request_approval("publish_landing_page", "publish", "copy")
    assert not a.approved
    with pytest.raises(ApprovalRequired):
        ensure_approved(a, "publish_landing_page")


@pytest.mark.parametrize("answer", ["", "yes", "y", "ok", "APPROVE please", "reject"])
def test_only_the_word_approve_approves(answer):
    assert not request_approval("x", "send", "s", input_fn=lambda _: answer).approved


def test_approve_works_and_is_bound_to_its_action():
    a = request_approval("publish_landing_page", "publish", "copy", input_fn=lambda _: "approve")
    assert ensure_approved(a, "publish_landing_page") is a
    with pytest.raises(ApprovalRequired):
        ensure_approved(a, "publish_listing")


def test_forged_approval_is_refused():
    real = request_approval("x", "spend", "s", input_fn=lambda _: "reject")
    forged = dataclasses.replace(real, approved=True, approver="founder")
    with pytest.raises(ApprovalRequired):
        ensure_approved(forged, "x")
    hand_made = Approval("x", "spend", True, "founder", "approved", "now", "deadbeef")
    with pytest.raises(ApprovalRequired):
        ensure_approved(hand_made, "x")


def test_publishing_without_approval_raises():
    with pytest.raises(ApprovalRequired):
        publish_landing_page("copy", None)
