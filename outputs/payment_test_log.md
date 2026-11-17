# Payment and delivery test log (MOCKED)

Run at 2026-11-17T21:37:09Z. Provider, fees, payouts and delivery are all MOCKED; no money moves.
Approvals: typed by the founder at the terminal

## 1. Checkout link needs approval
- PASS: checkout without approval refused ('publish_checkout:demo-product' needs founder approval)
- approval `publish_checkout:demo-product`: **approved** (approved)
- checkout created: mock://checkout/cs_0001

## 2. Payment triggers delivery; duplicate webhook is ignored
- webhook evt_0003 -> delivered
- duplicate webhook evt_0003 -> duplicate_event_ignored
- PASS: order ord_0002 delivered 1 time(s)
- webhook evt_0006 -> delivered

## 3. Refund needs approval and revokes access
- PASS: refund without approval refused ('refund:ord_0002' needs founder approval)
- approval `refund:ord_0002`: **rejected** (rejected by founder)

## 4. Payout and reconciliation
- payout po_0008: 36.30

| order | status | amount | fee | refund | access | payout |
|---|---|---|---|---|---|---|
| ord_0002 | paid | 19.00 | 0.85 | 0.00 | active | po_0008 |
| ord_0005 | paid | 19.00 | 0.85 | 0.00 | active | po_0008 |

Gross 38.00, fees 1.70, refunds 0.00, payouts 36.30 (expected 36.30).
Reconciliation: **OK**
