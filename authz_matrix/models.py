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
    # Refunded total on the order when the approval was given. Lets the
    # service tell whether the approval is stale at execution time.
    approved_at_refunded: Optional[int] = None
    # Stable key for one logical refund, reused on retries.
    idempotency_key: Optional[str] = None


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    rule_version: str = "refund-policy-v2"
    # "allow", "deny", "reapprove" or "replay". Not every refusal is a denial.
    outcome: str = ""

    def __post_init__(self) -> None:
        if not self.outcome:
            object.__setattr__(self, "outcome", "allow" if self.allowed else "deny")
