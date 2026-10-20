"""Provider-neutral commerce events with Shopify-compatible webhook HMAC verification.

This is a local reference implementation, not a deployed Cloud Run endpoint.
Payloads contain intentionally non-personal synthetic event fields only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EVENT_TYPES = {"order_paid", "checkout_completed"}
FIELDS = {"event_id", "event_type", "order_id", "amount_cents", "currency", "occurred_at", "analytics_consent"}


class ValidationError(ValueError):
    """Invalid signature, payload, or contradictory event identifier."""


def sign_webhook(body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode("ascii")


def verify_webhook(body: bytes, header: str, secret: str) -> bool:
    if not body or not header or not secret:
        return False
    return hmac.compare_digest(sign_webhook(body, secret), header.strip())


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("occurred_at must be an ISO 8601 timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("invalid occurred_at") from exc
    if dt.tzinfo is None:
        raise ValidationError("occurred_at must have an explicit timezone")
    dt = dt.astimezone(timezone.utc)
    if dt > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValidationError("future event timestamp is not allowed")
    return dt.isoformat(timespec="seconds")


def validate(body: bytes) -> dict[str, Any]:
    if len(body) > 32_768:
        raise ValidationError("payload exceeds 32 KiB limit")
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError("invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValidationError("expected JSON object")
    if set(data) != FIELDS:
        raise ValidationError("missing or unexpected fields")
    for field in ("event_id", "order_id"):
        val = data[field]
        if not isinstance(val, str) or not 1 <= len(val) <= 100 or not all(c.isalnum() or c in "-_" for c in val):
            raise ValidationError(f"invalid {field}")
    if data["event_type"] not in EVENT_TYPES:
        raise ValidationError("unrecognized event type")
    if type(data["amount_cents"]) is not int or not 0 <= data["amount_cents"] <= 10**10:
        raise ValidationError("amount_cents must be a nonnegative integer")
    if not isinstance(data["currency"], str) or len(data["currency"]) != 3 or not data["currency"].isalpha():
        raise ValidationError("invalid ISO currency code")
    if type(data["analytics_consent"]) is not bool:
        raise ValidationError("analytics_consent must be boolean")
    data["currency"] = data["currency"].upper()
    data["occurred_at"] = _timestamp(data["occurred_at"])
    return data


class EventStore:
    def __init__(self, path: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS commerce_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                order_id TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                currency TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                canonical_sha256 TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_event_order ON commerce_events(order_id, event_type);
            CREATE TABLE IF NOT EXISTS ingestion_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT,
                outcome TEXT NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.db.commit()

    def ingest_signed(self, body: bytes, signature: str, secret: str) -> str:
        # Verify before parsing, logging, or persisting untrusted data.
        if not verify_webhook(body, signature, secret):
            self._audit(None, "rejected_signature")
            raise ValidationError("webhook signature verification failed")
        data = validate(body)
        event_id = data["event_id"]
        # Browser-side analytics events require explicit consent. Operational orders
        # are a separate source with a distinct operational purpose.
        if data["event_type"] == "checkout_completed" and not data["analytics_consent"]:
            self._audit(event_id, "suppressed_no_consent")
            return "suppressed_no_consent"

        # The consent flag is intentionally not stored: no raw payload or personal data.
        payload = {key: value for key, value in data.items() if key != "analytics_consent"}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.db:
            existing = self.db.execute("SELECT canonical_sha256 FROM commerce_events WHERE event_id=?", (event_id,)).fetchone()
            if existing is not None:
                if existing["canonical_sha256"] != fingerprint:
                    self._audit(event_id, "event_id_conflict")
                    raise ValidationError("event ID reused with different content")
                self._audit(event_id, "duplicate")
                return "duplicate"
            self.db.execute("""
                INSERT INTO commerce_events(event_id, event_type, order_id, amount_cents,
                    currency, occurred_at, canonical_sha256)
                VALUES (:event_id, :event_type, :order_id, :amount_cents, :currency,
                    :occurred_at, :canonical_sha256)
            """, {**payload, "canonical_sha256": fingerprint})
            self._audit(event_id, "inserted")
        return "inserted"

    def _audit(self, event_id: str | None, outcome: str) -> None:
        self.db.execute("INSERT INTO ingestion_audit(event_id, outcome) VALUES (?, ?)", (event_id, outcome))
        self.db.commit()

    def reconciliation(self) -> list[dict[str, Any]]:
        """Compare latest synthetic operational order and consented checkout events."""
        rows = self.db.execute("""
            SELECT order_id, event_type, amount_cents, currency, occurred_at, event_id
            FROM commerce_events ORDER BY occurred_at DESC, event_id DESC
        """).fetchall()
        order_map: dict[str, dict[str, sqlite3.Row]] = {}
        for row in rows:
            order_map.setdefault(row["order_id"], {}).setdefault(row["event_type"], row)
        output = []
        for order_id, events in sorted(order_map.items()):
            paid, checkout = events.get("order_paid"), events.get("checkout_completed")
            if not paid:
                status = "checkout_without_order"
            elif not checkout:
                status = "order_without_checkout"
            elif (paid["currency"], paid["amount_cents"]) != (checkout["currency"], checkout["amount_cents"]):
                status = "amount_or_currency_mismatch"
            else:
                status = "matched"
            output.append({"order_id": order_id, "status": status,
                           "paid_cents": paid["amount_cents"] if paid else None,
                           "checkout_cents": checkout["amount_cents"] if checkout else None})
        return output

    def close(self) -> None:
        self.db.close()
