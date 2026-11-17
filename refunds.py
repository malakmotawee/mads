"""MOCKED refunds. A refund moves money, so it never happens without founder approval.
A completed refund revokes the buyer's access."""
from __future__ import annotations

from typing import Optional

from approval import Approval, ensure_approved
from delivery import DeliveryService
from payments import Ledger

LABEL = "MOCKED"


def refund_order(ledger: Ledger, delivery: DeliveryService, order_id: str, approval: Optional[Approval]) -> dict:
    ensure_approved(approval, f"refund:{order_id}")
    order = ledger.orders[order_id]
    if order.status == "refunded":
        return ledger.refunds[order_id]
    if order.status != "paid":
        raise ValueError(f"order {order_id} is {order.status}, not paid")
    payment = next(p for p in ledger.payments.values() if p.order_id == order_id)
    payment.status = "refunded"
    order.status = "refunded"
    refund = {"refund_id": ledger.new_id("re"), "order_id": order_id, "payment_id": payment.payment_id,
              "amount": payment.amount, "fee_returned": 0.0}  # MOCKED: processor keeps the fee
    ledger.refunds[order_id] = refund
    delivery.revoke_access(order_id)
    return refund
