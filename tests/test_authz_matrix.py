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


if __name__ == "__main__":
    unittest.main()
