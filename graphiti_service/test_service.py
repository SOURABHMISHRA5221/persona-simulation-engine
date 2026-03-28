"""
test_service.py — Integration test suite for the Graphiti service.

Tests:
  1. Health check
  2. Event ingestion (2 users, 2 events each — fast)
  3. Segment assignment
  4. User listing (all + filtered)
  5. User detail retrieval
  6. Segment listing
  7. Persona synthesis schema validation (1 persona)

Usage:
  python3 test_service.py
  python3 test_service.py --url http://localhost:8001
"""

import asyncio
import sys
import json
import httpx
import os
from datetime import datetime, timedelta

API_URL = "http://localhost:8000"
for i, arg in enumerate(sys.argv):
    if arg == "--url" and i + 1 < len(sys.argv):
        API_URL = sys.argv[i + 1]

print(f"\n[INFO] Target API: {API_URL}")
print(f"[INFO] OLLAMA_API_KEY set: {bool(os.environ.get('OLLAMA_API_KEY'))}")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = failed = total = 0


def log_test(name: str, ok: bool, detail: str = ""):
    global passed, failed, total
    total += 1
    if ok:
        passed += 1
        print(f"  {GREEN}✅ PASS{RESET}  {name}" + (f"  {CYAN}({detail}){RESET}" if detail else ""))
    else:
        failed += 1
        print(f"  {RED}❌ FAIL{RESET}  {name}" + (f"  {RED}({detail}){RESET}" if detail else ""))


# ── Minimal test data (2 users, 2 events each = 4 LLM calls max) ─────────────

NOW = datetime.now()

TEST_USERS = [
    {
        "user_id": "tst_alpha",
        "events": [
            {
                "event_type": "profile_update",
                "description": "tst_alpha is a 28-year-old Software Engineer from San Francisco interested in AI and open-source.",
                "timestamp": (NOW - timedelta(days=10)).isoformat(),
            },
            {
                "event_type": "purchase",
                "description": "Purchased premium subscription for $29.99/month.",
                "timestamp": (NOW - timedelta(days=5)).isoformat(),
            },
        ],
        "segment": "premium",
    },
    {
        "user_id": "tst_beta",
        "events": [
            {
                "event_type": "profile_update",
                "description": "tst_beta is a 35-year-old Teacher from Chicago interested in education and community.",
                "timestamp": (NOW - timedelta(days=8)).isoformat(),
            },
            {
                "event_type": "feedback",
                "description": "User feedback: The free tier is too limited, considering switching to a competitor.",
                "timestamp": (NOW - timedelta(days=2)).isoformat(),
            },
        ],
        "segment": "free",
    },
]


# ── Test 1: Health ────────────────────────────────────────────────────────────

async def test_health(client: httpx.AsyncClient):
    print(f"\n{BOLD}── Test 1: Health Check ──{RESET}")
    try:
        resp = await client.get(f"{API_URL}/health", timeout=60.0)
        data = resp.json()
        log_test("GET /health returns 200", resp.status_code == 200)
        neo4j_ok = data.get("checks", {}).get("neo4j") is True
        ollama_ok = data.get("checks", {}).get("ollama") is True
        log_test("Neo4j connected", neo4j_ok,
                 data.get("checks", {}).get("neo4j_error", "ok"))
        log_test("Ollama connected", ollama_ok,
                 data.get("checks", {}).get("ollama_model", data.get("checks", {}).get("ollama_error", "")))
        if not neo4j_ok or not ollama_ok:
            print(f"  {RED}⚠ Health checks failed — remaining tests may fail.{RESET}")
    except Exception as e:
        log_test("GET /health reachable", False, str(e))


# ── Test 2: Ingestion ─────────────────────────────────────────────────────────

async def _wait_for_queue(client: httpx.AsyncClient, timeout: int = 300):
    """Poll /health until ingest_queue_size == 0 (background workers done)."""
    print(f"  {CYAN}→ Waiting for ingest queue to drain...{RESET}", flush=True)
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            resp = await client.get(f"{API_URL}/health", timeout=10.0)
            data = resp.json()
            if data.get("ingest_queue_size", 1) == 0 and data.get("ingest_inflight", 1) == 0:
                print(f"    {GREEN}✓{RESET} Queue drained.")
                return
        except Exception:
            pass
        await asyncio.sleep(3)
    print(f"    {RED}✗{RESET} Queue did not drain within {timeout}s.")


async def test_ingest(client: httpx.AsyncClient):
    print(f"\n{BOLD}── Test 2: Event Ingestion ──{RESET}")
    total_events = sum(len(u["events"]) for u in TEST_USERS)
    print(f"  {CYAN}→ Ingesting {total_events} events for {len(TEST_USERS)} users...{RESET}")
    success = 0
    for user in TEST_USERS:
        for event in user["events"]:
            payload = {
                "user_id": user["user_id"],
                "event_type": event["event_type"],
                "description": event["description"],
                "timestamp": event["timestamp"],
            }
            try:
                print(f"  {CYAN}→ {user['user_id']} / {event['event_type']} (LLM extraction, ~30s)...{RESET}", flush=True)
                resp = await client.post(f"{API_URL}/ingest", json=payload, timeout=180.0)
                if resp.status_code == 200:
                    success += 1
                    print(f"    {GREEN}✓{RESET} done")
                else:
                    print(f"    {RED}✗{RESET} {resp.status_code}: {resp.text[:120]}")
            except Exception as e:
                print(f"    {RED}✗{RESET} {e}")

    log_test(f"Ingested {success}/{total_events} events", success == total_events)
    await _wait_for_queue(client)


# ── Test 3: Segments ──────────────────────────────────────────────────────────

async def test_segments(client: httpx.AsyncClient):
    print(f"\n{BOLD}── Test 3: Segment Assignment ──{RESET}")
    success = 0
    for user in TEST_USERS:
        try:
            resp = await client.post(
                f"{API_URL}/segment",
                json={"user_id": user["user_id"], "segment": user["segment"]},
                timeout=120.0,
            )
            if resp.status_code == 200:
                success += 1
                print(f"    {GREEN}✓{RESET} {user['user_id']} → {user['segment']}")
            else:
                print(f"    {RED}✗{RESET} {resp.text[:120]}")
        except Exception as e:
            print(f"    {RED}✗{RESET} {e}")
    log_test("All segments assigned", success == len(TEST_USERS))


# ── Test 4: User listing ──────────────────────────────────────────────────────

async def test_user_listing(client: httpx.AsyncClient):
    print(f"\n{BOLD}── Test 4: User Listing ──{RESET}")

    try:
        resp = await client.get(f"{API_URL}/users", timeout=30.0)
        data = resp.json()
        all_ids = data.get("user_ids", [])
        present = all(u["user_id"] in all_ids for u in TEST_USERS)
        log_test("GET /users — test users present", present, f"{data.get('count',0)} total")
    except Exception as e:
        log_test("GET /users", False, str(e))

    try:
        resp = await client.get(f"{API_URL}/users?segment=premium", timeout=30.0)
        data = resp.json()
        premium_ids = data.get("user_ids", [])
        expected = [u["user_id"] for u in TEST_USERS if u["segment"] == "premium"]
        log_test("GET /users?segment=premium correct",
                 all(uid in premium_ids for uid in expected),
                 f"{len(premium_ids)} users")
    except Exception as e:
        log_test("GET /users?segment=premium", False, str(e))

    try:
        resp = await client.get(f"{API_URL}/users?segment=free", timeout=30.0)
        data = resp.json()
        free_ids = data.get("user_ids", [])
        expected = [u["user_id"] for u in TEST_USERS if u["segment"] == "free"]
        log_test("GET /users?segment=free correct",
                 all(uid in free_ids for uid in expected),
                 f"{len(free_ids)} users")
    except Exception as e:
        log_test("GET /users?segment=free", False, str(e))


# ── Test 5: User detail ───────────────────────────────────────────────────────

async def test_user_detail(client: httpx.AsyncClient):
    print(f"\n{BOLD}── Test 5: User Detail ──{RESET}")
    uid = "tst_alpha"
    try:
        resp = await client.get(f"{API_URL}/user/{uid}", timeout=30.0)
        data = resp.json()
        log_test(f"GET /user/{uid} returns 200", resp.status_code == 200)
        log_test("user_id matches", data.get("user_id") == uid)
        log_test("Has events", data.get("event_count", 0) > 0, f"{data.get('event_count',0)} events")
        log_test("Has segment", "premium" in data.get("segments", []), str(data.get("segments")))
    except Exception as e:
        log_test(f"GET /user/{uid}", False, str(e))


# ── Test 6: Segments list ─────────────────────────────────────────────────────

async def test_segments_list(client: httpx.AsyncClient):
    print(f"\n{BOLD}── Test 6: Segment Listing ──{RESET}")
    try:
        resp = await client.get(f"{API_URL}/segments", timeout=30.0)
        data = resp.json()
        segs = data.get("segments", {})
        log_test("GET /segments returns 200", resp.status_code == 200)
        log_test("'premium' segment exists", "premium" in segs, str(list(segs.keys())))
        log_test("'free' segment exists", "free" in segs)
        print(f"  {GREEN}✓{RESET} Segments: { {k: v for k, v in segs.items()} }")
    except Exception as e:
        log_test("GET /segments", False, str(e))


# ── Test 7: Persona synthesis ─────────────────────────────────────────────────

async def test_personas(client: httpx.AsyncClient):
    print(f"\n{BOLD}── Test 7: Persona Synthesis (LLM) ──{RESET}")
    print(f"  {CYAN}→ Requesting 1 persona (LLM synthesis, ~30s)...{RESET}", flush=True)
    try:
        resp = await client.get(f"{API_URL}/personas?n=1", timeout=300.0)
        data = resp.json()
        log_test("GET /personas?n=1 returns 200", resp.status_code == 200)
        personas = data.get("personas", [])
        log_test("Returns at least 1 persona", len(personas) >= 1, f"got {len(personas)}")

        if personas:
            p = personas[0]
            log_test("Has user_id",   "user_id"   in p)
            log_test("Has username",  "username"  in p, p.get("username", "MISSING"))
            log_test("Has persona",   "persona"   in p)

            if "persona" in p:
                persona = p["persona"]
                log_test("Has traits",       "traits"   in persona)
                log_test("Has behavior",     "behavior" in persona)
                log_test("Has interests",    "interests" in persona and isinstance(persona["interests"], list))
                log_test("Has past_opinions","past_opinions" in persona)
                log_test("Has hourly_activity", "hourly_activity" in persona)

                if "traits" in persona:
                    for t in ["price_sensitivity","tech_savviness","brand_loyalty",
                               "optimism","skepticism","community_orientation"]:
                        log_test(f"Trait '{t}'", t in persona["traits"] and
                                 isinstance(persona["traits"][t], (int, float)))

                if "behavior" in persona:
                    log_test("Has subscription_tier",
                             "subscription_tier" in persona["behavior"],
                             persona["behavior"].get("subscription_tier","?"))

            print(f"\n  {CYAN}Sample persona:{RESET}")
            print(f"  {json.dumps(p, indent=2)[:800]}")

    except Exception as e:
        log_test("GET /personas?n=1", False, str(e))

    # Segment-filtered
    print(f"  {CYAN}→ Requesting 1 premium persona...{RESET}", flush=True)
    try:
        resp = await client.get(f"{API_URL}/personas?n=1&segment=premium", timeout=300.0)
        data = resp.json()
        log_test("GET /personas?segment=premium works", resp.status_code == 200)
        if data.get("personas"):
            log_test("Segment-filtered persona returned", True, "1 persona")
    except Exception as e:
        log_test("GET /personas?segment=premium", False, str(e))


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print(f"\n{BOLD}{'=' * 60}")
    print(f"  Graphiti Service Test Suite")
    print(f"  Target: {API_URL}")
    print(f"{'=' * 60}{RESET}")

    async with httpx.AsyncClient() as client:
        await test_health(client)
        await test_ingest(client)
        await test_segments(client)
        await test_user_listing(client)
        await test_user_detail(client)
        await test_segments_list(client)
        await test_personas(client)

    print(f"\n{BOLD}{'=' * 60}")
    color = GREEN if failed == 0 else RED
    status = "ALL TESTS PASSED" if failed == 0 else f"{failed} TEST(S) FAILED"
    print(f"  {color}{passed}/{total} passed — {status}{RESET}")
    print(f"{'=' * 60}\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
