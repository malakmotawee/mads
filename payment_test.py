"""Run the MOCKED sale-to-cash scenario and write outputs/payment_test_log.md.

    python payment_test.py                      # founder approves each step at the terminal
    python payment_test.py --scripted-approvals # test harness answers 'approve' (labelled in the log)

Nothing touches a real payment service: payments.py, delivery.py, refunds.py
and reconcile.py are all MOCKED.
"""
from __future__ import annotations

import argparse
import os

from approval import ApprovalRequired, request_approval
from decision_log import utc_now
from delivery import DeliveryService
from payments import Ledger, MockPaymentProvider, WebhookHandler
from reconcile import reconcile
from refunds import refund_order


def run(out_path: str, scripted: bool) -> bool:
    lines = [f"# Payment and delivery test log (MOCKED)", "",
             f"Run at {utc_now()}. Provider, fees, payouts and delivery are all MOCKED; no money moves.",
             "Approvals: " + ("scripted by the test harness (MOCKED founder input)" if scripted else "typed by the founder at the terminal"), ""]
    label = "test-harness (MOCKED founder input)" if scripted else "founder"
    ask = (lambda _prompt: "approve") if scripted else None

    def approve(action: str, kind: str, summary: str):
        a = request_approval(action, kind, summary, input_fn=ask, approver_label=label)
        lines.append(f"- approval `{action}`: **{'approved' if a.approved else 'rejected'}** ({a.reason})")
        return a

    def step(text: str):
        lines.append(f"- {text}")

    ledger = Ledger()
    provider, delivery = MockPaymentProvider(ledger), DeliveryService(ledger)
    hooks = WebhookHandler(ledger, delivery)

    lines.append("## 1. Checkout link needs approval")
    try:
        provider.create_checkout("demo-product", 19.0, "USD", approval=None)
        step("FAIL: checkout created without approval")
    except ApprovalRequired as exc:
        step(f"PASS: checkout without approval refused ({exc})")
    session = None
    a = approve("publish_checkout:demo-product", "publish", "Publish MOCKED checkout for demo-product at $19.00")
    if a.approved:
        session = provider.create_checkout("demo-product", 19.0, "USD", a)
        step(f"checkout created: {session['url']}")
    if session is None:
        lines.append("\nStopped: checkout not approved.")
        _write(out_path, lines)
        return False

    lines.append("\n## 2. Payment triggers delivery; duplicate webhook is ignored")
    ev1 = provider.simulate_customer_payment(session["id"], "buyer-ref-A")
    step(f"webhook {ev1.event_id} -> {hooks.handle(ev1)}")
    step(f"duplicate webhook {ev1.event_id} -> {hooks.handle(ev1)}")
    g = ledger.grants[ev1.order_id]
    step(f"{'PASS' if g['deliveries'] == 1 else 'FAIL'}: order {ev1.order_id} delivered {g['deliveries']} time(s)")
    ev2 = provider.simulate_customer_payment(session["id"], "buyer-ref-B")
    step(f"webhook {ev2.event_id} -> {hooks.handle(ev2)}")

    lines.append("\n## 3. Refund needs approval and revokes access")
    try:
        refund_order(ledger, delivery, ev1.order_id, approval=None)
        step("FAIL: refund ran without approval")
    except ApprovalRequired as exc:
        step(f"PASS: refund without approval refused ({exc})")
    a = approve(f"refund:{ev1.order_id}", "refund", f"Refund order {ev1.order_id} ($19.00, MOCKED)")
    if a.approved:
        r = refund_order(ledger, delivery, ev1.order_id, a)
        step(f"refund {r['refund_id']} for {r['amount']:.2f}; access active: {delivery.has_access(ev1.order_id)}")

    lines.append("\n## 4. Payout and reconciliation")
    po = provider.simulate_payout()
    step(f"payout {po.payout_id if po else '-'}: {po.amount if po else 0:.2f}")
    rec = reconcile(ledger)
    lines += ["", "| order | status | amount | fee | refund | access | payout |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['order_id']} | {r['status']} | {r['amount']:.2f} | {r['fee']:.2f} | {r['refund']:.2f} | {r['access']} | {r['payout_id']} |" for r in rec["rows"]]
    lines += ["", f"Gross {rec['gross']:.2f}, fees {rec['fees']:.2f}, refunds {rec['refunds']:.2f}, "
              f"payouts {rec['payouts']:.2f} (expected {rec['expected_payouts']:.2f}).",
              f"Reconciliation: **{'OK' if rec['ok'] else 'MISMATCH'}**"]
    lines += [f"- issue: {i}" for i in rec["issues"]]
    _write(out_path, lines)
    return rec["ok"]


def _write(path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=os.path.join(os.environ.get("OUTPUTS_DIR", "outputs"), "payment_test_log.md"))
    p.add_argument("--scripted-approvals", action="store_true")
    args = p.parse_args()
    raise SystemExit(0 if run(args.out, args.scripted_approvals) else 1)
