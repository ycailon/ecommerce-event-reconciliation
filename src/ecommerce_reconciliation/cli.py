"""Local demo CLI using intentionally fictional transactions."""

import argparse
import json
from pathlib import Path

from .pipeline import EventStore, sign_webhook


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay signed synthetic commerce events locally")
    parser.add_argument("command", choices=["demo"])
    parser.add_argument("--db", default=":memory:", help="SQLite output path, default in-memory")
    parser.add_argument("--out", default="output/reconciliation.json", help="JSON report path")
    args = parser.parse_args()
    sample = Path(__file__).resolve().parents[2] / "examples" / "synthetic_events.jsonl"
    if not sample.exists():
        sample = Path("examples/synthetic_events.jsonl")
    store = EventStore(args.db)
    secret = "local-demo-secret-not-for-production"
    statuses = {}
    for line in sample.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        body = json.dumps(event, separators=(",", ":")).encode()
        status = store.ingest_signed(body, sign_webhook(body, secret), secret)
        statuses[status] = statuses.get(status, 0) + 1
    report = {"ingestion": statuses, "reconciliation": store.reconciliation()}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    store.close()


if __name__ == "__main__":
    main()
