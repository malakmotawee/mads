"""MOCKED payment provider. No real payment service, sandbox or money is involved.

- Publishing a checkout link needs founder approval (approval.py).
- A `payment_succeeded` webhook is the only thing that triggers delivery.
- Webhooks are idempotent: an event ID is processed once, and an order is
  delivered once, so a duplicate webhook can never cause a double delivery.
- The system never moves or refunds money by itself (see refunds.py).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from approval import Approval, ensure_approved

LABEL = "MOCKED"
FEE_PERCENT = 0.029  # MOCKED fee schedule, for reconciliation only
FEE_FIXED = 0.30


@dataclass
class Order:
    order_id: str
    product_id: str
    amount: float
    currency: str
    customer_ref: str  # opaque reference; no names, emails, passwords or card numbers are stored
    status: str = "pending"  # pending -> paid -> refunded


@dataclass
class Payment:
    payment_id: str
    order_id: str
    amount: float
    fee: float
    net: float
    status: str = "succeeded"  # succeeded | refunded


@dataclass
class Payout:
    payout_id: str
    payment_ids: list[str]
    amount: float


@dataclass
class WebhookEvent:
    event_id: str
    type: str
    order_id: str
    amount: float


@dataclass
class Ledger:
    checkouts: dict[str, dict] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    payments: dict[str, Payment] = field(default_factory=dict)
    refunds: dict[str, dict] = field(default_factory=dict)
    payouts: list[Payout] = field(default_factory=list)
    processed_events: set[str] = field(default_factory=set)
    grants: dict[str, dict] = field(default_factory=dict)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._ids):04d}"


def fee_for(amount: float) -> float:
    return round(amount * FEE_PERCENT + FEE_FIXED, 2)


class MockPaymentProvider:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger

    def create_checkout(self, product_id: str, amount: float, currency: str, approval: Optional[Approval]) -> dict:
        ensure_approved(approval, f"publish_checkout:{product_id}")
        cid = self.ledger.new_id("cs")
        session = {"id": cid, "product_id": product_id, "amount": amount, "currency": currency, "url": f"mock://checkout/{cid}"}
        self.ledger.checkouts[cid] = session
        return session

    def simulate_customer_payment(self, checkout_id: str, customer_ref: str) -> WebhookEvent:
        """TEST HARNESS ONLY (payment_test.py, tests/): stands in for a buyer paying."""
        s = self.ledger.checkouts[checkout_id]
        order = Order(self.ledger.new_id("ord"), s["product_id"], s["amount"], s["currency"], customer_ref)
        self.ledger.orders[order.order_id] = order
        return WebhookEvent(self.ledger.new_id("evt"), "payment_succeeded", order.order_id, s["amount"])

    def simulate_payout(self) -> Optional[Payout]:
        paid_out = {pid for p in self.ledger.payouts for pid in p.payment_ids}
        due = [p for p in self.ledger.payments.values() if p.payment_id not in paid_out]
        if not due:
            return None
        refunded = {r["payment_id"]: r["amount"] for r in self.ledger.refunds.values()}
        amount = round(sum(p.net - refunded.get(p.payment_id, 0) for p in due), 2)
        payout = Payout(self.ledger.new_id("po"), [p.payment_id for p in due], amount)
        self.ledger.payouts.append(payout)
        return payout


class WebhookHandler:
    def __init__(self, ledger: Ledger, delivery):
        self.ledger = ledger
        self.delivery = delivery

    def handle(self, event: WebhookEvent) -> str:
        if event.event_id in self.ledger.processed_events:
            return "duplicate_event_ignored"
        self.ledger.processed_events.add(event.event_id)
        if event.type != "payment_succeeded":
            return "ignored"
        order = self.ledger.orders[event.order_id]
        if order.status != "pending":
            return "order_already_processed"
        fee = fee_for(event.amount)
        pay = Payment(self.ledger.new_id("pay"), order.order_id, event.amount, fee, round(event.amount - fee, 2))
        self.ledger.payments[pay.payment_id] = pay
        order.status = "paid"
        self.delivery.grant_access(order)
        return "delivered"
