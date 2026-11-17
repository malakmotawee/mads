import pytest

from approval import ApprovalRequired, request_approval
from delivery import DeliveryService
from payments import Ledger, MockPaymentProvider, WebhookHandler
from reconcile import reconcile
from refunds import refund_order

YES = lambda _: "approve"  # noqa: E731  (test harness input)


def setup():
    ledger = Ledger()
    provider, delivery = MockPaymentProvider(ledger), DeliveryService(ledger)
    a = request_approval("publish_checkout:p", "publish", "s", input_fn=YES)
    return ledger, provider, delivery, WebhookHandler(ledger, delivery), provider.create_checkout("p", 19.0, "USD", a)


def test_checkout_needs_approval():
    with pytest.raises(ApprovalRequired):
        MockPaymentProvider(Ledger()).create_checkout("p", 19.0, "USD", None)


def test_payment_triggers_delivery_once():
    ledger, provider, delivery, hooks, s = setup()
    ev = provider.simulate_customer_payment(s["id"], "ref")
    assert hooks.handle(ev) == "delivered"
    assert hooks.handle(ev) == "duplicate_event_ignored"
    assert ledger.grants[ev.order_id]["deliveries"] == 1 and delivery.has_access(ev.order_id)


def test_refund_needs_approval_and_revokes_access():
    ledger, provider, delivery, hooks, s = setup()
    ev = provider.simulate_customer_payment(s["id"], "ref")
    hooks.handle(ev)
    with pytest.raises(ApprovalRequired):
        refund_order(ledger, delivery, ev.order_id, None)
    refund_order(ledger, delivery, ev.order_id, request_approval(f"refund:{ev.order_id}", "refund", "s", input_fn=YES))
    assert not delivery.has_access(ev.order_id)


def test_reconcile_matches():
    ledger, provider, delivery, hooks, s = setup()
    for ref in ("a", "b"):
        hooks.handle(provider.simulate_customer_payment(s["id"], ref))
    first = next(iter(ledger.orders))
    refund_order(ledger, delivery, first, request_approval(f"refund:{first}", "refund", "s", input_fn=YES))
    provider.simulate_payout()
    rec = reconcile(ledger)
    assert rec["ok"], rec["issues"]
    assert rec["payouts"] == rec["expected_payouts"]
