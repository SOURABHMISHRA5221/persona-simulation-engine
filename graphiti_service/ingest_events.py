#!/usr/bin/env python3
"""
ingest_events.py — Batch ingestion CLI for the event processing pipeline.

Reads events from a JSON or CSV file and posts them to the graphiti_service
via POST /ingest/batch/rich (structured) or POST /ingest/batch (legacy).

Usage
-----
  python ingest_events.py --input events.json
  python ingest_events.py --input events.csv
  python ingest_events.py --input events.csv --url http://my-server:8000 --batch-size 50
  python ingest_events.py --input events.json --dry-run

JSON format
-----------
Array of RichUserEvent objects:
  [
    {
      "user_id": "user_001",
      "event_type": "purchase",
      "timestamp": "2024-01-15T10:30:00",
      "properties": {
        "item_name": "laptop",
        "price_usd": 499.99,
        "category": "electronics"
      }
    },
    ...
  ]

Also accepts {"events": [...]} wrapper.

CSV format
----------
Required columns: user_id, event_type, timestamp
All other columns become event properties (empty values are omitted).
Numeric values are auto-coerced.

  user_id,event_type,timestamp,item_name,price_usd,category
  user_001,purchase,2024-01-15T10:30:00,laptop,499.99,electronics
  user_002,feedback,2024-01-15T11:00:00,"Great product!",,
"""

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

import httpx

DEFAULT_URL = "http://localhost:8000"
DEFAULT_BATCH_SIZE = 25


# ── File loaders ──────────────────────────────────────────────────────────────

def load_json_events(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "events" in data:
        return data["events"]
    print("[ERROR] JSON must be an array of events or {\"events\": [...]}")
    sys.exit(1)


def load_csv_events(path: Path) -> list[dict]:
    """
    Map CSV rows to RichUserEvent dicts.
    Required columns: user_id, event_type, timestamp
    All other columns become properties (empty values dropped).
    """
    required = {"user_id", "event_type", "timestamp"}
    events = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("[ERROR] CSV has no header row")
            sys.exit(1)

        missing = required - set(reader.fieldnames)
        if missing:
            print(f"[ERROR] CSV missing required columns: {missing}")
            print(f"        Found: {list(reader.fieldnames)}")
            sys.exit(1)

        for row_num, row in enumerate(reader, start=2):
            uid = (row.get("user_id") or "").strip()
            etype = (row.get("event_type") or "").strip()
            ts = (row.get("timestamp") or "").strip()

            if not uid or not etype or not ts:
                print(f"[WARN] Row {row_num}: missing required field — skipping")
                continue

            props: dict = {}
            for col, val in row.items():
                if col in required or not val or not val.strip():
                    continue
                v = val.strip()
                # Coerce numeric values
                try:
                    props[col] = float(v) if "." in v else int(v)
                except ValueError:
                    props[col] = v

            events.append({
                "user_id": uid,
                "event_type": etype,
                "timestamp": ts,
                "properties": props,
            })

    return events


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def check_health(client: httpx.AsyncClient, url: str) -> bool:
    try:
        resp = await client.get(f"{url}/health", timeout=10.0)
        data = resp.json()
        status = data.get("status", "unknown")
        print(f"  Service status  : {status}")
        checks = data.get("checks", {})
        print(f"  Neo4j           : {'✅' if checks.get('neo4j') else '❌'}")
        print(f"  LLM backend     : {'✅' if checks.get('ollama') else '❌'}")
        return status in ("healthy", "degraded")
    except Exception as e:
        print(f"  [ERROR] Cannot reach {url}: {e}")
        return False


async def send_batch(
    client: httpx.AsyncClient,
    url: str,
    batch: list[dict],
    batch_num: int,
    total_batches: int,
) -> tuple[int, int]:
    """POST a batch to /ingest/batch/rich. Returns (success, fail)."""
    try:
        resp = await client.post(
            f"{url}/ingest/batch/rich",
            json={"events": batch},
            timeout=300.0,
        )
        if resp.status_code == 200:
            result = resp.json()
            s = result.get("success", 0)
            f = result.get("failed", 0)
            for err in result.get("errors", [])[:3]:
                print(f"\n    [WARN] {err.get('user_id','?')}: {str(err.get('error',''))[:80]}")
            return s, f
        print(f"\n  [ERROR] Batch {batch_num}/{total_batches} → HTTP {resp.status_code}: {resp.text[:150]}")
        return 0, len(batch)
    except Exception as ex:
        print(f"\n  [ERROR] Batch {batch_num}/{total_batches} failed: {ex}")
        return 0, len(batch)


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-ingest events from CSV or JSON into the Graphiti service.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Path to .json or .csv events file")
    parser.add_argument("--url", "-u", default=DEFAULT_URL,
                        help=f"Service base URL (default: {DEFAULT_URL})")
    parser.add_argument("--batch-size", "-b", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Events per batch request (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and validate the file without sending to the service")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)

    # ── Load events ───────────────────────────────────────────────────────
    ext = path.suffix.lower()
    print(f"\nLoading events from {path} ...")
    if ext == ".json":
        events = load_json_events(path)
    elif ext == ".csv":
        events = load_csv_events(path)
    else:
        print(f"[ERROR] Unsupported file type '{ext}'. Use .json or .csv")
        sys.exit(1)

    if not events:
        print("[WARN] No events found in file. Exiting.")
        return

    # ── Summary ───────────────────────────────────────────────────────────
    users = {e.get("user_id") for e in events}
    etypes: dict[str, int] = {}
    for e in events:
        k = e.get("event_type", "unknown")
        etypes[k] = etypes.get(k, 0) + 1

    print(f"\nEvents loaded   : {len(events)}")
    print(f"Unique users    : {len(users)}")
    print(f"Event types     : {dict(sorted(etypes.items(), key=lambda x: -x[1]))}")
    print(f"\nSample event    :")
    s = events[0]
    print(f"  user_id       : {s.get('user_id')}")
    print(f"  event_type    : {s.get('event_type')}")
    print(f"  timestamp     : {s.get('timestamp')}")
    print(f"  properties    : {s.get('properties', {})}")

    if args.dry_run:
        print("\n[DRY RUN] Validation passed. No events sent.")
        return

    # ── Send ──────────────────────────────────────────────────────────────
    batches = [events[i:i + args.batch_size] for i in range(0, len(events), args.batch_size)]
    total_batches = len(batches)

    print(f"\nSending {len(events)} events in {total_batches} batch(es) "
          f"of up to {args.batch_size} ...")
    print(f"Target          : {args.url}/ingest/batch/rich\n")

    start = time.time()
    total_success = 0
    total_fail = 0

    async with httpx.AsyncClient() as client:
        if not await check_health(client, args.url):
            print("\n[ERROR] Service unreachable. Start it with: uvicorn main:app --port 8000")
            sys.exit(1)
        print()

        for i, batch in enumerate(batches, start=1):
            s_cnt, f_cnt = await send_batch(client, args.url, batch, i, total_batches)
            total_success += s_cnt
            total_fail += f_cnt
            pct = int((i / total_batches) * 100)
            print(f"  [{pct:3d}%] Batch {i}/{total_batches} — "
                  f"✅ {total_success} sent  ❌ {total_fail} failed", end="\r")

    elapsed = time.time() - start
    print(f"\n\n{'='*56}")
    print(f"  Done!  ✅ {total_success}/{len(events)} succeeded   ❌ {total_fail} failed")
    print(f"  Time   : {elapsed:.1f}s  ({elapsed / 60:.1f} min)")
    print(f"  Users  : {len(users)}")
    print(f"  Rate   : {len(events) / max(elapsed, 0.01):.1f} events/sec")
    print(f"\n  Signals  → GET {args.url}/signals")
    print(f"  Personas → GET {args.url}/personas")
    print(f"{'='*56}\n")


if __name__ == "__main__":
    asyncio.run(main())
