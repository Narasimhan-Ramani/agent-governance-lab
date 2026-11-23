from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Order:
    order_id: str
    owner: str
    total: int  # whole pounds, for simplicity


@dataclass(frozen=True)
class RefundRequest:
    on_behalf_of: Optional[str]
    order_id: str
    amount: int
    approved_amount: int = 0
    approval_ref: Optional[str] = None


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    rule_version: str = "refund-policy-v1"
