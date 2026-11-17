"""Phase 5 (Sell, deliver, get paid): MOCKED payments and delivery.

The pipeline only sets up a MOCKED checkout (after founder approval) and checks
that delivery is wired to payment. It never simulates sales in a pipeline run;
the end-to-end payment scenario lives in payment_test.py.
"""
from __future__ import annotations

import re

from agents.common import RunContext, StepResult
from approval import request_approval
from delivery import DeliveryService
from payments import Ledger, MockPaymentProvider

AGENT = "seller"


def _price(ctx: RunContext) -> float:
    offer = ctx.results.get("phase4_step1_offer")
    if offer and offer.data.get("price_usd"):
        return float(offer.data["price_usd"])
    m = re.search(r"\d+(\.\d+)?", ctx.brief.sections.get("Price idea", ""))
    return float(m.group(0)) if m else 0.0


def checkout(ctx: RunContext, attempt: int) -> StepResult:
    ledger = Ledger()
    ctx.results["_ledger"] = StepResult(title="", data={"ledger": ledger})
    product_id = re.sub(r"[^a-z0-9]+", "-", ctx.brief.title.lower()).strip("-") or "product"
    action = f"publish_checkout:{product_id}"
    appr = request_approval(action, "publish", f"MOCKED checkout for {product_id} at {_price(ctx):.2f} USD",
                            input_fn=ctx.approval_input)
    ctx.log.record("approval", f"founder_approval:{action}", model=None, cost=0,
                   approved_by=appr.approver if appr.approved else None,
                   outcome="approved" if appr.approved else "rejected", detail=appr.reason)
    body = appr.reason
    if appr.approved:
        session = MockPaymentProvider(ledger).create_checkout(product_id, _price(ctx), "USD", appr)
        ctx.log.record(AGENT, "create_checkout", model=None, cost=0, approved_by=appr.approver, detail="MOCKED")
        body = f"MOCKED checkout created: `{session['url']}` (no real payment provider)."
    return StepResult(title="Checkout (MOCKED)", body=body, labels=["MOCKED"],
                      metrics={"artifact_produced": True, "needs_approval": True, "founder_approved": appr.approved})


def delivery(ctx: RunContext, attempt: int) -> StepResult:
    ledger = ctx.results["_ledger"].data["ledger"]
    DeliveryService(ledger)  # wiring check only: delivery runs from WebhookHandler on payment_succeeded
    ctx.log.record(AGENT, "configure_delivery", model=None, cost=0, detail="MOCKED")
    body = ("MOCKED: delivery is triggered only by a `payment_succeeded` webhook (payments.WebhookHandler), "
            "is idempotent per order, and is revoked by an approved refund. Run `python payment_test.py` "
            "for the end-to-end MOCKED scenario.")
    return StepResult(title="Delivery (MOCKED)", body=body, labels=["MOCKED"], metrics={"artifact_produced": True})
