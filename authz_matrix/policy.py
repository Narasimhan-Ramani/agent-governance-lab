"""Deterministic refund authority rules. No model is involved."""
from __future__ import annotations
from typing import Optional
from .models import Decision, Order, RefundRequest

SELF_SERVICE_LIMIT = 100


def authorize_refund(req: RefundRequest, order: Optional[Order],
                     already_refunded: int) -> Decision:
    if not req.on_behalf_of:
        return Decision(False, "missing on-behalf-of context")
    if order is None:
        return Decision(False, "unknown order")
    if order.owner != req.on_behalf_of:
        return Decision(False, "order does not belong to requester")
    if req.amount <= 0:
        return Decision(False, "invalid amount")
    cumulative = already_refunded + req.amount
    if cumulative > order.total:
        return Decision(False, "refund exceeds order total")
    # Cumulative check: split refunds cannot bypass the self-service limit.
    if cumulative > SELF_SERVICE_LIMIT and req.approved_amount < cumulative:
        return Decision(False, "cumulative amount needs approval covering the full value")
    return Decision(True, "allowed")
