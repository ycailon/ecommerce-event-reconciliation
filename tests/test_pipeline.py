import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from ecommerce_reconciliation.pipeline import EventStore, ValidationError, sign_webhook, verify_webhook

SECRET = "only-for-tests"
BASE = {"event_id": "evt_1", "event_type": "order_paid", "order_id": "TEST001",
        "amount_cents": 900, "currency": "USD", "occurred_at": "2026-10-10T12:00:00Z", "analytics_consent": False}


def send(store, data):
    raw = json.dumps(data).encode()
    return store.ingest_signed(raw, sign_webhook(raw, SECRET), SECRET)


class TestIngestion(unittest.TestCase):
    def setUp(self):
        self.store = EventStore()

    def tearDown(self):
        self.store.close()

    def test_signature_rejects_tampered_payload(self):
        raw = json.dumps(BASE).encode()
        self.assertTrue(verify_webhook(raw, sign_webhook(raw, SECRET), SECRET))
        with self.assertRaisesRegex(ValidationError, "signature"):
            self.store.ingest_signed(raw + b" ", sign_webhook(raw, SECRET), SECRET)
        self.assertEqual([], self.store.reconciliation())

    def test_replay_is_idempotent(self):
        self.assertEqual("inserted", send(self.store, BASE))
        self.assertEqual("duplicate", send(self.store, BASE))
        self.assertEqual(1, len(self.store.reconciliation()))

    def test_same_event_id_different_amount_is_rejected(self):
        send(self.store, BASE)
        with self.assertRaisesRegex(ValidationError, "reused"):
            send(self.store, {**BASE, "amount_cents": 1})

    def test_missing_consent_suppresses_browser_event(self):
        event = {**BASE, "event_type": "checkout_completed"}
        self.assertEqual("suppressed_no_consent", send(self.store, event))
        self.assertEqual([], self.store.reconciliation())

    def test_matching_and_mismatching_orders(self):
        send(self.store, BASE)
        send(self.store, {**BASE, "event_id": "evt_2", "event_type": "checkout_completed", "analytics_consent": True})
        send(self.store, {**BASE, "event_id": "evt_3", "order_id": "TEST002"})
        send(self.store, {**BASE, "event_id": "evt_4", "order_id": "TEST002", "event_type": "checkout_completed", "analytics_consent": True, "amount_cents": 10})
        self.assertEqual(["matched", "amount_or_currency_mismatch"], [x["status"] for x in self.store.reconciliation()])

    def test_bad_timestamp_and_unexpected_fields(self):
        with self.assertRaises(ValidationError):
            send(self.store, {**BASE, "occurred_at": "2026-10-10 12:00:00"})
        with self.assertRaises(ValidationError):
            send(self.store, {**BASE, "email": "private@example.org"})

    def test_invalid_amount_type(self):
        for val in (-1, 2.5, True):
            with self.subTest(val=val), self.assertRaises(ValidationError):
                send(self.store, {**BASE, "amount_cents": val})

    def test_reopen_persistent_db(self):
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/events.sqlite"
            first = EventStore(path)
            send(first, BASE)
            first.close()
            second = EventStore(path)
            self.assertEqual("duplicate", send(second, BASE))
            second.close()

    def test_rejects_far_future_timestamp(self):
        ts = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        with self.assertRaisesRegex(ValidationError, "future"):
            send(self.store, {**BASE, "occurred_at": ts})


if __name__ == "__main__":
    unittest.main()
