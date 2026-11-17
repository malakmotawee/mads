"""MOCKED reconciliation: match orders, payments, fees, refunds, access grants and payouts."""
from __future__ import annotations

from payments import Ledger, fee_for

LABEL = "MOCKED"


def reconcile(ledger: Ledger) -> dict:
    issues: list[str] = []
    rows = []
    pay_by_order = {p.order_id: p for p in ledger.payments.values()}
    paid_out = {pid: po.payout_id for po in ledger.payouts for pid in po.payment_ids}
    for order in ledger.orders.values():
        pay = pay_by_order.get(order.order_id)
        refund = ledger.refunds.get(order.order_id)
        grant = ledger.grants.get(order.order_id)
        if order.status in ("paid", "refunded") and not pay:
            issues.append(f"{order.order_id}: marked {order.status} but has no payment")
        if pay and abs(pay.amount - order.amount) > 0.001:
            issues.append(f"{order.order_id}: payment {pay.amount} != order {order.amount}")
        if pay and abs(pay.fee - fee_for(pay.amount)) > 0.001:
            issues.append(f"{order.order_id}: fee {pay.fee} does not match the fee schedule")
        if order.status == "paid" and not (grant and grant["active"]):
            issues.append(f"{order.order_id}: paid but not delivered")
        if order.status == "refunded" and grant and grant["active"]:
            issues.append(f"{order.order_id}: refunded but access still active")
        if grant and grant.get("deliveries", 1) != 1:
            issues.append(f"{order.order_id}: delivered {grant['deliveries']} times")
        if order.status == "pending" and grant:
            issues.append(f"{order.order_id}: delivered without payment")
        rows.append({
            "order_id": order.order_id, "status": order.status, "amount": order.amount,
            "payment_id": pay.payment_id if pay else None, "fee": pay.fee if pay else 0.0,
            "refund": refund["amount"] if refund else 0.0,
            "access": ("active" if grant["active"] else "revoked") if grant else "none",
            "payout_id": paid_out.get(pay.payment_id) if pay else None,
        })
    gross = round(sum(p.amount for p in ledger.payments.values()), 2)
    fees = round(sum(p.fee for p in ledger.payments.values()), 2)
    refunds = round(sum(r["amount"] for r in ledger.refunds.values()), 2)
    payouts = round(sum(po.amount for po in ledger.payouts), 2)
    expected = round(gross - fees - refunds, 2)
    unpaid = [p.payment_id for p in ledger.payments.values() if p.payment_id not in paid_out]
    if not unpaid and abs(payouts - expected) > 0.001:
        issues.append(f"payouts {payouts} != gross - fees - refunds {expected}")
    return {"rows": rows, "gross": gross, "fees": fees, "refunds": refunds, "payouts": payouts,
            "expected_payouts": expected, "unpaid_payments": unpaid, "issues": issues, "ok": not issues}
