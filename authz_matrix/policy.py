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

    # A stale approval is not a flat denial: the approver said yes to an
    # order state that no longer exists, so the right result is re-approval.
    if (req.approved_amount > 0 and req.approved_at_refunded is not None
            and req.approved_at_refunded != already_refunded):
        return Decision(False, "approval is stale: order changed since approval",
                        outcome="reapprove")

    cumulative = already_refunded + req.amount
    if cumulative > order.total:
        return Decision(False, "refund exceeds order total")
    # Cumulative check: split refunds cannot bypass the self-service limit.
    if cumulative > SELF_SERVICE_LIMIT and req.approved_amount < cumulative:
        return Decision(False, "cumulative amount needs approval covering the full value")
    return Decision(True, "allowed")
