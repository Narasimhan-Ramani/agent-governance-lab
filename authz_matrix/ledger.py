from __future__ import annotations
from typing import Dict


class RefundLedger:
    """In-memory record of amounts already refunded per order."""

    def __init__(self) -> None:
        self._refunded: Dict[str, int] = {}

    def total_for(self, order_id: str) -> int:
        return self._refunded.get(order_id, 0)

    def record(self, order_id: str, amount: int) -> None:
        self._refunded[order_id] = self.total_for(order_id) + amount
