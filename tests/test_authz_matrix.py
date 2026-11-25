import unittest
from authz_matrix import Order, RefundLedger, RefundRequest, RefundService


class AuthorityMatrix(unittest.TestCase):
    def setUp(self):
        self.orders = {
            "A1": Order("A1", owner="alice", total=1000),
            "B1": Order("B1", owner="bob", total=1000),
            "A2": Order("A2", owner="alice", total=100),
        }
        self.ledger = RefundLedger()
        self.svc = RefundService(self.orders, self.ledger)

    # ---- original matrix -------------------------------------------------
    def test_own_order_small_amount(self):
        self.assertTrue(self.svc.refund(RefundRequest("alice", "A1", 50)).allowed)

    def test_someone_elses_order(self):
        d = self.svc.refund(RefundRequest("alice", "B1", 50))
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "order does not belong to requester")

    def test_over_limit_without_approval(self):
        self.assertFalse(self.svc.refund(RefundRequest("alice", "A1", 800)).allowed)

    def test_over_limit_with_full_approval(self):
        req = RefundRequest("alice", "A1", 800, approved_amount=800, approval_ref="APR-1")
        self.assertTrue(self.svc.refund(req).allowed)

    def test_approval_does_not_cover_amount(self):
        req = RefundRequest("alice", "A1", 800, approved_amount=300, approval_ref="APR-2")
        self.assertFalse(self.svc.refund(req).allowed)

    def test_exceeds_order_total(self):
        self.ledger.record("A2", 50)
        d = self.svc.refund(RefundRequest("alice", "A2", 60))
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "refund exceeds order total")

    def test_missing_on_behalf_of(self):
        self.assertFalse(self.svc.refund(RefundRequest(None, "A1", 50)).allowed)

    def test_unknown_order(self):
        self.assertFalse(self.svc.refund(RefundRequest("alice", "ZZ", 50)).allowed)

    def test_invalid_amount(self):
        self.assertFalse(self.svc.refund(RefundRequest("alice", "A1", 0)).allowed)

    def test_split_refunds_cannot_bypass_limit(self):
        first = self.svc.refund(RefundRequest("alice", "A1", 60))
        second = self.svc.refund(RefundRequest("alice", "A1", 60))
        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)
        self.assertIn("cumulative", second.reason)

    def test_every_decision_is_recorded_with_reason(self):
        self.svc.refund(RefundRequest("alice", "A1", 50))
        self.svc.refund(RefundRequest("alice", "B1", 50))
        self.assertEqual(len(self.svc.evidence), 2)
        self.assertEqual([e["decision"] for e in self.svc.evidence], ["allow", "deny"])
        self.assertTrue(all(e["reason"] and e["rule_version"] for e in self.svc.evidence))


class StaleApproval(unittest.TestCase):
    """Suggested by Rakshitha G: an approval can be valid when given and
    wrong by the time the agent executes."""

    def setUp(self):
        self.orders = {"A1": Order("A1", owner="alice", total=1000)}
        self.ledger = RefundLedger()
        self.svc = RefundService(self.orders, self.ledger)

    def approved_request(self, snapshot):
        return RefundRequest("alice", "A1", 500, approved_amount=500,
                             approval_ref="APR-7", approved_at_refunded=snapshot)

    def test_fresh_approval_is_allowed(self):
        d = self.svc.refund(self.approved_request(snapshot=0))
        self.assertTrue(d.allowed)
        self.assertEqual(d.outcome, "allow")

    def test_approval_goes_stale_when_order_changes(self):
        # Approved when nothing had been refunded; another channel then
        # refunds 300 before the agent executes.
        self.ledger.record("A1", 300)
        d = self.svc.refund(self.approved_request(snapshot=0))
        self.assertFalse(d.allowed)
        self.assertIn("stale", d.reason)

    def test_stale_approval_means_reapprove_not_deny(self):
        self.ledger.record("A1", 300)
        d = self.svc.refund(self.approved_request(snapshot=0))
        self.assertEqual(d.outcome, "reapprove")
        self.assertNotEqual(d.outcome, "deny")

    def test_stale_approval_changes_nothing(self):
        self.ledger.record("A1", 300)
        self.svc.refund(self.approved_request(snapshot=0))
        self.assertEqual(self.ledger.total_for("A1"), 300)

    def test_reapproval_against_current_state_is_allowed(self):
        # The new approval is given against the current state (300 already
        # refunded) and covers the cumulative value: 300 + 500 = 800.
        self.ledger.record("A1", 300)
        req = RefundRequest("alice", "A1", 500, approved_amount=800,
                            approval_ref="APR-8", approved_at_refunded=300)
        d = self.svc.refund(req)
        self.assertTrue(d.allowed)
        self.assertEqual(self.ledger.total_for("A1"), 800)

    def test_stale_decision_is_recorded_as_reapprove(self):
        self.ledger.record("A1", 300)
        self.svc.refund(self.approved_request(snapshot=0))
        self.assertEqual(self.svc.evidence[-1]["decision"], "reapprove")


class IdempotentRetry(unittest.TestCase):
    """Suggested by Dishant Sharma: the agent times out and retries the
    same refund. A cumulative limit alone does not stop this below the limit."""

    def setUp(self):
        self.orders = {"A1": Order("A1", owner="alice", total=1000)}
        self.ledger = RefundLedger()
        self.svc = RefundService(self.orders, self.ledger)

    def test_retry_with_key_returns_original_result(self):
        req = RefundRequest("alice", "A1", 50, idempotency_key="refund-A1-001")
        first = self.svc.refund(req)
        second = self.svc.refund(req)
        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertEqual(second.outcome, "replay")

    def test_retry_with_key_refunds_only_once(self):
        req = RefundRequest("alice", "A1", 50, idempotency_key="refund-A1-001")
        self.svc.refund(req)
        self.svc.refund(req)
        self.assertEqual(self.ledger.total_for("A1"), 50)

    def test_retry_is_recorded_as_replay(self):
        req = RefundRequest("alice", "A1", 50, idempotency_key="refund-A1-001")
        self.svc.refund(req)
        self.svc.refund(req)
        self.assertEqual([e["decision"] for e in self.svc.evidence], ["allow", "replay"])

    def test_same_key_with_different_request_is_denied(self):
        self.svc.refund(RefundRequest("alice", "A1", 50, idempotency_key="k1"))
        d = self.svc.refund(RefundRequest("alice", "A1", 70, idempotency_key="k1"))
        self.assertFalse(d.allowed)
        self.assertIn("different request", d.reason)
        self.assertEqual(self.ledger.total_for("A1"), 50)

    def test_retry_without_key_is_refunded_twice(self):
        # Documents the gap the key closes: 50 + 50 stays within the limit,
        # so the cumulative rule alone lets both through.
        first = self.svc.refund(RefundRequest("alice", "A1", 50))
        second = self.svc.refund(RefundRequest("alice", "A1", 50))
        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertEqual(self.ledger.total_for("A1"), 100)

    def test_denied_request_replays_as_denied(self):
        req = RefundRequest("alice", "A1", 800, idempotency_key="k2")
        first = self.svc.refund(req)
        second = self.svc.refund(req)
        self.assertFalse(first.allowed)
        self.assertFalse(second.allowed)
        self.assertEqual(second.outcome, "replay")


if __name__ == "__main__":
    unittest.main()
