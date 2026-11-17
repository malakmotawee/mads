"""MOCKED digital delivery: access grants keyed by order (idempotent), revoked on refund."""
from __future__ import annotations

import hashlib

from payments import Ledger, Order

LABEL = "MOCKED"


class DeliveryService:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger

    def grant_access(self, order: Order) -> dict:
        existing = self.ledger.grants.get(order.order_id)
        if existing:  # idempotent: one grant per order, never a second delivery
            return existing
        token = "mock-access-" + hashlib.sha256(order.order_id.encode()).hexdigest()[:12]
        grant = {"order_id": order.order_id, "product_id": order.product_id, "token": token,
                 "active": True, "deliveries": 1}
        self.ledger.grants[order.order_id] = grant
        return grant

    def revoke_access(self, order_id: str) -> dict:
        grant = self.ledger.grants[order_id]
        grant["active"] = False
        return grant

    def has_access(self, order_id: str) -> bool:
        g = self.ledger.grants.get(order_id)
        return bool(g and g["active"])
