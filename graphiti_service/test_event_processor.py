"""
Unit tests for event_schema.py and event_processor.py.
No external services required.

Run:
  python -m pytest test_event_processor.py -v
  # or
  python test_event_processor.py
"""
import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

# Run from the graphiti_service directory
sys.path.insert(0, os.path.dirname(__file__))

from event_schema import RichUserEvent, BatchRichIngestRequest, UserEvent, SegmentAssignment
from event_processor import EventProcessor, UserSignals


TS = "2024-06-15T10:30:00"


def make_event(user_id, event_type, **props) -> RichUserEvent:
    return RichUserEvent(user_id=user_id, event_type=event_type,
                         timestamp=TS, properties=props)


class TestEventSchema(unittest.TestCase):

    def test_rich_event_defaults(self):
        e = RichUserEvent(user_id="u1", event_type="login", timestamp=TS)
        self.assertEqual(e.properties, {})

    def test_rich_event_with_props(self):
        e = make_event("u1", "purchase", item_name="laptop", price_usd=499.99)
        self.assertEqual(e.properties["item_name"], "laptop")
        self.assertAlmostEqual(e.properties["price_usd"], 499.99)

    def test_batch_request(self):
        req = BatchRichIngestRequest(events=[
            make_event("u1", "login"),
            make_event("u2", "purchase", item_name="book", price_usd=12.99),
        ])
        self.assertEqual(len(req.events), 2)

    def test_legacy_user_event(self):
        e = UserEvent(user_id="u1", event_type="login",
                      description="Logged in on mobile", timestamp=TS)
        self.assertEqual(e.description, "Logged in on mobile")

    def test_segment_assignment(self):
        s = SegmentAssignment(user_id="u1", segment="premium")
        self.assertEqual(s.segment, "premium")


class TestEventProcessorPurchase(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_purchase_increments_count(self):
        e = make_event("u1", "purchase", item_name="laptop", price_usd=500.0, category="electronics")
        self.proc.process(e)
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["purchase"]["count"], 1)
        self.assertAlmostEqual(sigs["purchase"]["total_spend"], 500.0)
        self.assertEqual(sigs["purchase"]["top_category"], "electronics")

    def test_purchase_episode_text(self):
        e = make_event("u1", "purchase", item_name="headphones", price_usd=99.99, category="audio")
        text = self.proc.process(e)
        self.assertIn("purchase #1", text)
        self.assertIn("headphones", text)
        self.assertIn("$99.99", text)
        self.assertIn("audio", text)

    def test_multiple_purchases_accumulate(self):
        for i, price in enumerate([100.0, 200.0, 300.0], 1):
            self.proc.process(make_event("u1", "purchase",
                                         item_name=f"item{i}", price_usd=price, category="tech"))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["purchase"]["count"], 3)
        self.assertAlmostEqual(sigs["purchase"]["total_spend"], 600.0)
        self.assertAlmostEqual(sigs["purchase"]["avg_order_value"], 200.0)

    def test_purchase_episode_shows_running_total(self):
        self.proc.process(make_event("u1", "purchase", item_name="a", price_usd=100.0, category="x"))
        text = self.proc.process(make_event("u1", "purchase", item_name="b", price_usd=200.0, category="x"))
        self.assertIn("purchase #2", text)
        self.assertIn("$300.00", text)  # running total

    def test_quantity_multiplied(self):
        self.proc.process(make_event("u1", "purchase", item_name="item",
                                      price_usd=10.0, category="x", quantity=3))
        sigs = self.proc.get_signals("u1")
        self.assertAlmostEqual(sigs["purchase"]["total_spend"], 30.0)


class TestEventProcessorFeedback(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_positive_feedback_detected(self):
        self.proc.process(make_event("u1", "feedback", text="I love this product, it's amazing!"))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["feedback"]["positive_count"], 1)
        self.assertEqual(sigs["feedback"]["negative_count"], 0)
        self.assertEqual(sigs["feedback"]["sentiment_ratio"], "positive")

    def test_negative_feedback_detected(self):
        self.proc.process(make_event("u1", "feedback", text="This is terrible and broken"))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["feedback"]["negative_count"], 1)
        self.assertEqual(sigs["feedback"]["positive_count"], 0)

    def test_rating_increments_feedback(self):
        self.proc.process(make_event("u1", "feedback", text="ok", rating=5))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["feedback"]["avg_rating"], 5.0)
        self.assertEqual(sigs["feedback"]["positive_count"], 1)

    def test_low_rating_counts_negative(self):
        self.proc.process(make_event("u1", "feedback", text="fine", rating=1))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["feedback"]["negative_count"], 1)

    def test_feedback_text_in_episode(self):
        text = self.proc.process(make_event("u1", "feedback",
                                             text="I love this product!", feature="dashboard"))
        self.assertIn("dashboard", text)
        self.assertIn("positive", text)


class TestEventProcessorSession(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_session_increments(self):
        self.proc.process(make_event("u1", "session_end",
                                      duration_minutes=20, pages_viewed=5, device="desktop"))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["engagement"]["session_count"], 1)
        self.assertEqual(sigs["engagement"]["total_session_minutes"], 20)

    def test_multiple_sessions_accumulate(self):
        self.proc.process(make_event("u1", "session_end", duration_minutes=10, pages_viewed=3))
        self.proc.process(make_event("u1", "session_end", duration_minutes=30, pages_viewed=10))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["engagement"]["session_count"], 2)
        self.assertEqual(sigs["engagement"]["total_session_minutes"], 40)
        self.assertAlmostEqual(sigs["engagement"]["avg_session_minutes"], 20.0)

    def test_high_engagement_label(self):
        text = self.proc.process(make_event("u1", "session_end",
                                             duration_minutes=45, pages_viewed=12))
        self.assertIn("high engagement", text)

    def test_low_engagement_label(self):
        text = self.proc.process(make_event("u1", "session_end",
                                             duration_minutes=3, pages_viewed=1))
        self.assertIn("low engagement", text)


class TestEventProcessorSupport(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_support_ticket_increments(self):
        self.proc.process(make_event("u1", "support_ticket",
                                      issue="login broken", priority="high", category="auth"))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["support"]["ticket_count"], 1)
        self.assertEqual(sigs["support"]["categories"]["auth"], 1)

    def test_churn_risk_flag_at_3_tickets(self):
        for _ in range(3):
            self.proc.process(make_event("u1", "support_ticket",
                                          issue="problem", category="billing"))
        text = self.proc.process(make_event("u1", "support_ticket",
                                             issue="another", category="billing"))
        # churn flag should appear at ticket 3+
        self.assertIn("CHURN RISK", text)


class TestEventProcessorSearch(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_search_recorded(self):
        self.proc.process(make_event("u1", "search", query="productivity tools"))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["browse"]["search_count"], 1)
        self.assertIn("productivity tools", sigs["browse"]["recent_searches"])

    def test_churn_signal_search(self):
        text = self.proc.process(make_event("u1", "search", query="cancel subscription"))
        self.assertIn("churn-signal", text)

    def test_exploratory_search(self):
        text = self.proc.process(make_event("u1", "search", query="best features"))
        self.assertIn("exploratory search", text)


class TestEventProcessorProfile(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_profile_update_stored(self):
        self.proc.process(make_event("u1", "profile_update",
                                      age=28, occupation="Engineer",
                                      location="Austin, TX",
                                      interests=["AI", "gaming"]))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["profile"]["age"], 28)
        self.assertEqual(sigs["profile"]["occupation"], "Engineer")
        self.assertEqual(sigs["profile"]["location"], "Austin, TX")
        self.assertIn("AI", sigs["profile"]["interests"])


class TestEventProcessorSubscription(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_upgrade_detected(self):
        text = self.proc.process(make_event("u1", "subscription_change",
                                             from_tier="free", to_tier="premium"))
        self.assertIn("upgrade", text)
        self.assertIn("Positive revenue event", text)

    def test_downgrade_churn_flag(self):
        text = self.proc.process(make_event("u1", "subscription_change",
                                             from_tier="premium", to_tier="free"))
        self.assertIn("downgrade", text)
        self.assertIn("CHURN RISK", text)

    def test_tier_stored(self):
        self.proc.process(make_event("u1", "subscription_change",
                                      from_tier="basic", to_tier="premium"))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["profile"]["subscription_tier"], "premium")


class TestEventProcessorFeature(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_feature_usage_counted(self):
        self.proc.process(make_event("u1", "feature_usage", feature_name="dark_mode"))
        self.proc.process(make_event("u1", "feature_usage", feature_name="dark_mode"))
        self.proc.process(make_event("u1", "feature_usage", feature_name="export_csv"))
        sigs = self.proc.get_signals("u1")
        self.assertEqual(sigs["features"]["distinct_count"], 2)
        self.assertEqual(sigs["features"]["usage_counts"]["dark_mode"], 2)
        self.assertEqual(sigs["features"]["usage_counts"]["export_csv"], 1)


class TestDerivedSegments(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_high_value_buyer_by_spend(self):
        for i in range(3):
            self.proc.process(make_event("u1", "purchase",
                                          item_name=f"item{i}", price_usd=200.0, category="x"))
        sigs = self.proc.get_signals("u1")
        self.assertIn("high-value-buyer", sigs["derived_segments"])

    def test_high_value_buyer_by_count(self):
        for i in range(5):
            self.proc.process(make_event("u1", "purchase",
                                          item_name=f"item{i}", price_usd=1.0, category="x"))
        sigs = self.proc.get_signals("u1")
        self.assertIn("high-value-buyer", sigs["derived_segments"])

    def test_churn_risk_by_negative_feedback(self):
        for _ in range(3):
            self.proc.process(make_event("u1", "feedback", text="terrible broken bad"))
        sigs = self.proc.get_signals("u1")
        self.assertIn("churn-risk", sigs["derived_segments"])

    def test_churn_risk_by_support_tickets(self):
        for _ in range(3):
            self.proc.process(make_event("u1", "support_ticket",
                                          issue="problem", category="billing"))
        sigs = self.proc.get_signals("u1")
        self.assertIn("churn-risk", sigs["derived_segments"])

    def test_deal_seeker(self):
        self.proc.process(make_event("u1", "search", query="cancel plan refund"))
        sigs = self.proc.get_signals("u1")
        self.assertIn("deal-seeker", sigs["derived_segments"])

    def test_power_user_by_features(self):
        for feat in ["dashboard", "reports", "export", "api", "integrations"]:
            self.proc.process(make_event("u1", "feature_usage", feature_name=feat))
        sigs = self.proc.get_signals("u1")
        self.assertIn("power-user", sigs["derived_segments"])

    def test_engaged_user(self):
        for _ in range(10):
            self.proc.process(make_event("u1", "session_end",
                                          duration_minutes=20, pages_viewed=5))
        self.proc.process(make_event("u1", "feedback", text="I love this product, amazing!"))
        sigs = self.proc.get_signals("u1")
        self.assertIn("engaged", sigs["derived_segments"])

    def test_repeat_buyer(self):
        for i in range(2):
            self.proc.process(make_event("u1", "purchase",
                                          item_name=f"item{i}", price_usd=10.0, category="x"))
        for _ in range(5):
            self.proc.process(make_event("u1", "add_to_cart",
                                          item_name="thing", price_usd=5.0))
        sigs = self.proc.get_signals("u1")
        self.assertIn("repeat-buyer", sigs["derived_segments"])

    def test_no_false_segments_for_new_user(self):
        self.proc.process(make_event("u1", "login", device="mobile"))
        sigs = self.proc.get_signals("u1")
        # Brand new user with just a login should have no heavy segments
        segs = sigs["derived_segments"]
        self.assertNotIn("high-value-buyer", segs)
        self.assertNotIn("churn-risk", segs)
        self.assertNotIn("power-user", segs)


class TestMultipleUsers(unittest.TestCase):

    def setUp(self):
        self.proc = EventProcessor()

    def test_signals_isolated_per_user(self):
        self.proc.process(make_event("alice", "purchase",
                                      item_name="laptop", price_usd=1000.0, category="tech"))
        self.proc.process(make_event("bob", "feedback", text="terrible experience"))

        alice = self.proc.get_signals("alice")
        bob = self.proc.get_signals("bob")

        self.assertEqual(alice["purchase"]["count"], 1)
        self.assertEqual(bob["purchase"]["count"], 0)
        self.assertEqual(bob["feedback"]["negative_count"], 1)
        self.assertEqual(alice["feedback"]["negative_count"], 0)

    def test_get_all_signals(self):
        self.proc.process(make_event("u1", "login"))
        self.proc.process(make_event("u2", "login"))
        self.proc.process(make_event("u3", "login"))
        all_sigs = self.proc.get_all_signals()
        self.assertEqual(len(all_sigs), 3)
        self.assertIn("u1", all_sigs)
        self.assertIn("u3", all_sigs)

    def test_unknown_user_returns_none(self):
        self.assertIsNone(self.proc.get_signals("nonexistent"))


class TestLegacyProcessing(unittest.TestCase):

    def test_process_legacy_returns_string(self):
        proc = EventProcessor()
        text = proc.process_legacy("u1", "purchase", "Bought a laptop for $499", TS)
        self.assertIn("u1", text)
        self.assertIn("purchase", text)
        self.assertIn("laptop", text)

    def test_process_legacy_bad_timestamp(self):
        proc = EventProcessor()
        # Should not raise even with malformed timestamp
        text = proc.process_legacy("u1", "login", "Logged in", "not-a-date")
        self.assertIn("u1", text)


class TestRecency(unittest.TestCase):

    def test_first_and_last_seen_tracked(self):
        proc = EventProcessor()
        early = "2024-01-01T08:00:00"
        late = "2024-06-15T20:00:00"
        proc.process(RichUserEvent(user_id="u1", event_type="login",
                                    timestamp=late, properties={}))
        proc.process(RichUserEvent(user_id="u1", event_type="login",
                                    timestamp=early, properties={}))
        sigs = proc.get_signals("u1")
        self.assertIn("2024-01-01", sigs["recency"]["first_seen"])
        self.assertIn("2024-06-15", sigs["recency"]["last_seen"])


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__import__("__main__"))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
