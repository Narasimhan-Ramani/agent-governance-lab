"""The enforcement point: the business service, not the gateway or the prompt."""
from __future__ import annotations
from typing import Dict, List
from .ledger import RefundLedger
from .models import Decision, Order, RefundRequest
from .policy import authorize_refund


class RefundService:
    def __init__(self, orders: Dict[str, Order], ledger: RefundLedger) -> None:
        self.orders = orders
        self.ledger = ledger
        self.evidence: List[dict] = []

    def refund(self, req: RefundRequest) -> Decision:
        order = self.orders.get(req.order_id)
        decision = authorize_refund(req, order, self.ledger.total_for(req.order_id))
        if decision.allowed:
            self.ledger.record(req.order_id, req.amount)
        self.evidence.append({
            "order_id": req.order_id,
            "on_behalf_of": req.on_behalf_of,
            "amount": req.amount,
            "approval_ref": req.approval_ref,
            "decision": "allow" if decision.allowed else "deny",
            "reason": decision.reason,
            "rule_version": decision.rule_version,
        })
        return decision
