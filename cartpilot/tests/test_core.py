import os, tempfile, unittest
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["MOCK_PAYPAL"] = "1"
os.environ.pop("ANTHROPIC_API_KEY", None)

from app import db, catalog, agent, paypal
from app.policy import Rules, check_policy


class PolicyTests(unittest.TestCase):
    R = Rules(monthly_budget=100, max_per_purchase=50, approval_threshold=20, allowed_categories=["food", "tech"])

    def test_allow(self):
        self.assertEqual(check_policy(10, "food", self.R, 0)["decision"], "allow")

    def test_needs_approval(self):
        self.assertEqual(check_policy(30, "food", self.R, 0)["decision"], "needs_approval")

    def test_block_per_purchase(self):
        self.assertEqual(check_policy(60, "tech", self.R, 0)["decision"], "block")

    def test_block_budget(self):
        self.assertEqual(check_policy(30, "food", self.R, 80)["decision"], "block")

    def test_block_category(self):
        self.assertEqual(check_policy(10, "toys", self.R, 0)["decision"], "block")

    def test_boundaries(self):
        self.assertEqual(check_policy(20, "food", self.R, 0)["decision"], "allow")
        self.assertEqual(check_policy(50, "food", self.R, 50)["decision"], "needs_approval")
        self.assertEqual(check_policy(50.01, "food", self.R, 0)["decision"], "block")


class FlowTests(unittest.TestCase):
    def setUp(self):
        db.init()

    def test_agent_fallback_respects_budget(self):
        out = agent.run_agent("A gift for my dad under $50, he loves coffee", db.get_rules())
        self.assertTrue(out["products"])
        self.assertTrue(all(p["price"] <= 50 for p in out["products"]))

    def test_full_paid_flow_and_budget_tracking(self):
        p = catalog.get("p01")  # $24 food -> needs approval (default threshold 25? 24 <= 25 -> allow)
        v = check_policy(p["price"], p["category"], db.get_rules(), db.spent_this_month())
        req = db.add_request(p, v["decision"], v["reason"])
        self.assertEqual(req["status"], "approved")
        order = paypal.create_order(req["amount"], req["title"], req["id"])
        self.assertEqual(paypal.capture_order(order["id"])["status"], "COMPLETED")
        before = db.spent_this_month()
        db.set_status(req["id"], "paid", paid_at=db.now())
        self.assertEqual(db.spent_this_month(), round(before + 24.0, 2))

    def test_overspend_is_blocked_and_logged(self):
        p = catalog.get("p08")  # $299 headphones
        v = check_policy(p["price"], p["category"], db.get_rules(), db.spent_this_month())
        self.assertEqual(v["decision"], "block")
        req = db.add_request(p, v["decision"], v["reason"])
        self.assertEqual(req["status"], "blocked")
        self.assertTrue(any("purchase_requested" in a["event"] for a in db.audit_log()))


if __name__ == "__main__":
    unittest.main()
