"""The enforcement point: the business service, not the gateway or the prompt."""
from __future__ import annotations
from dataclasses import replace
from typing import Dict, List, Tuple
from .ledger import RefundLedger
from .models import Decision, Order, RefundRequest
from .policy import authorize_refund


class RefundService:
    def __init__(self, orders: Dict[str, Order], ledger: RefundLedger) -> None:
        self.orders = orders
        self.ledger = ledger
        self.evidence: List[dict] = []
        # idempotency key -> (original request, original decision)
        self._seen: Dict[str, Tuple[RefundRequest, Decision]] = {}

    def refund(self, req: RefundRequest) -> Decision:
        if req.idempotency_key and req.idempotency_key in self._seen:
            first_req, first_decision = self._seen[req.idempotency_key]
            if first_req != req:
                decision = Decision(False, "idempotency key reused with a different request")
            else:
                # Same logical refund retried: return the original result,
                # change nothing.
                decision = replace(first_decision, outcome="replay")
            self._record(req, decision)
            return decision

        order = self.orders.get(req.order_id)
        decision = authorize_refund(req, order, self.ledger.total_for(req.order_id))
        if decision.allowed:
            self.ledger.record(req.order_id, req.amount)
        if req.idempotency_key:
            self._seen[req.idempotency_key] = (req, decision)
        self._record(req, decision)
        return decision

    def _record(self, req: RefundRequest, decision: Decision) -> None:
        self.evidence.append({
            "order_id": req.order_id,
            "on_behalf_of": req.on_behalf_of,
            "amount": req.amount,
            "approval_ref": req.approval_ref,
            "idempotency_key": req.idempotency_key,
            "decision": decision.outcome,
            "reason": decision.reason,
            "rule_version": decision.rule_version,
        })
