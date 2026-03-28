"""
generate_mock_data.py — Rich mock data generator for the Graphiti service.

Creates 50 users with diverse behavioral events and assigns them to segments.
Events include: profile info, purchases, sessions, feedback, support tickets.
"""

import asyncio
import httpx
import random
import time
from datetime import datetime, timedelta

API_URL = "http://localhost:8000"

# ── Configuration ─────────────────────────────────────────────────────────────

NUM_USERS = 50
EVENTS_PER_USER = 20  # Rich events per user for good persona synthesis
NUM_WORKERS = 3
MAX_RETRIES = 3

# ── User templates ────────────────────────────────────────────────────────────

OCCUPATIONS = [
    "Student", "Software Engineer", "Product Manager", "Freelance Designer",
    "Teacher", "Marketing Manager", "Security Researcher", "Startup Founder",
    "Data Scientist", "Nurse", "Journalist", "Chef", "Architect",
    "Accountant", "Content Creator", "Retired", "Small Business Owner",
    "Graduate Researcher", "Sales Manager", "Graphic Designer",
]

LOCATIONS = [
    "Austin, TX", "Seattle, WA", "Mumbai, India", "Berlin, Germany",
    "Chicago, IL", "London, UK", "Bangalore, India", "New York, NY",
    "Portland, OR", "Mexico City, Mexico", "Tokyo, Japan", "Lisbon, Portugal",
    "Lagos, Nigeria", "Sydney, Australia", "Toronto, Canada", "Seoul, South Korea",
    "São Paulo, Brazil", "Cape Town, South Africa", "Stockholm, Sweden", "Dubai, UAE",
]

INTERESTS = [
    "gaming", "open-source", "tech news", "productivity", "SaaS tools",
    "AI", "design", "UI/UX", "privacy", "cybersecurity", "education",
    "community", "entrepreneurship", "marketing", "analytics", "travel",
    "sustainability", "photography", "cooking", "fitness", "music",
    "reading", "podcasts", "investing", "social media",
]

SEGMENTS = ["free", "basic", "premium"]
SPECIAL_SEGMENTS = ["high-churn-risk", "enterprise", "power-user", "dormant"]

ITEMS = ["laptop", "headphones", "coffee maker", "keyboard", "monitor",
         "webcam", "desk lamp", "backpack", "shoes", "book", "phone case"]

PAGES = ["/home", "/product/1", "/product/2", "/product/3", "/cart",
         "/checkout", "/profile", "/settings", "/search", "/help", "/pricing"]

FEEDBACK_POSITIVE = [
    "I love this product, it has changed how I work!",
    "Customer support was incredibly helpful, resolved my issue in minutes.",
    "The new dashboard feature is exactly what I needed.",
    "Great value for money, would recommend to friends.",
    "The mobile app is smooth and intuitive.",
    "Integration with Slack was a game-changer for our team.",
    "The dark mode is beautiful, thank you!",
    "Performance has improved dramatically after the last update.",
]

FEEDBACK_NEGATIVE = [
    "The price increase feels unjustified given the features.",
    "I keep getting errors during checkout, very frustrating.",
    "The new UI is confusing, I can't find anything anymore.",
    "Loading times have gotten worse over the past month.",
    "Privacy policy changes concern me, need more transparency.",
    "The free tier is too limited now, considering switching.",
    "Mobile app crashes frequently on Android.",
    "Would appreciate more customization options for notifications.",
]


def _make_user_id(i: int) -> str:
    return f"user_{i:04d}"


def _random_ts(days_back: int = 60) -> str:
    """Generate a random ISO timestamp within the last N days."""
    dt = datetime.now() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return dt.isoformat()


def generate_profile_event(user_id: str) -> dict:
    """Generate a profile/bio event so Graphiti can extract identity entities."""
    age = random.randint(18, 65)
    occupation = random.choice(OCCUPATIONS)
    location = random.choice(LOCATIONS)
    user_interests = random.sample(INTERESTS, k=random.randint(2, 5))

    desc = (
        f"{user_id} is a {age}-year-old {occupation} from {location}. "
        f"Interests include {', '.join(user_interests)}."
    )
    return {
        "user_id": user_id,
        "event_type": "profile_update",
        "description": desc,
        "timestamp": _random_ts(90),
    }


def generate_behavior_event(user_id: str) -> dict:
    """Generate a random behavioral event."""
    event_type = random.choice([
        "page_view", "purchase", "add_to_cart", "search",
        "support_ticket", "feedback", "login", "session_end",
        "feature_usage", "referral",
    ])

    if event_type == "page_view":
        page = random.choice(PAGES)
        duration = random.randint(5, 300)
        desc = f"Viewed {page} for {duration} seconds"
    elif event_type == "purchase":
        item = random.choice(ITEMS)
        price = round(random.uniform(9.99, 499.99), 2)
        desc = f"Purchased {item} for ${price}"
    elif event_type == "add_to_cart":
        item = random.choice(ITEMS)
        desc = f"Added {item} to cart"
    elif event_type == "search":
        queries = ["best headphones", "cheap laptop", "productivity tools",
                    "how to cancel", "upgrade plan", "dark mode", "API docs",
                    "pricing", "alternatives", "refund policy"]
        desc = f"Searched for: {random.choice(queries)}"
    elif event_type == "support_ticket":
        issues = ["billing issue", "feature request", "bug report",
                   "account access problem", "integration help", "performance complaint"]
        desc = f"Opened support ticket: {random.choice(issues)}"
    elif event_type == "feedback":
        feedback = random.choice(FEEDBACK_POSITIVE + FEEDBACK_NEGATIVE)
        desc = f"User feedback: \"{feedback}\""
    elif event_type == "login":
        devices = ["mobile_ios", "mobile_android", "desktop_chrome",
                    "desktop_firefox", "tablet", "desktop_safari"]
        desc = f"Logged in from {random.choice(devices)}"
    elif event_type == "session_end":
        minutes = random.randint(1, 120)
        pages = random.randint(1, 25)
        desc = f"Session ended after {minutes} minutes, viewed {pages} pages"
    elif event_type == "feature_usage":
        features = ["dashboard", "reports", "export_csv", "team_invite",
                     "dark_mode", "notifications", "api_access", "integrations"]
        desc = f"Used feature: {random.choice(features)}"
    elif event_type == "referral":
        desc = "Referred a new user via email invite"
    else:
        desc = f"General {event_type} action"

    return {
        "user_id": user_id,
        "event_type": event_type,
        "description": desc,
        "timestamp": _random_ts(60),
    }


async def send_event(client: httpx.AsyncClient, payload: dict, endpoint: str = "/ingest") -> bool:
    """Send an event with retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.post(f"{API_URL}{endpoint}", json=payload, timeout=120.0)
            if resp.status_code == 200:
                return True
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
        except Exception:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
    return False


async def worker(queue: asyncio.Queue, client: httpx.AsyncClient, counters: dict):
    """Worker that drains the queue."""
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break

        payload, endpoint = item
        ok = await send_event(client, payload, endpoint)
        counters["success" if ok else "fail"] += 1
        counters["total"] += 1

        if counters["total"] % 50 == 0:
            print(f"  Progress: {counters['total']}/{counters['expected']} "
                  f"| ✅ {counters['success']} | ❌ {counters['fail']}")

        queue.task_done()


async def main():
    print("=" * 60)
    print("  Graphiti Mock Data Generator")
    print("=" * 60)

    # Check health first
    async with httpx.AsyncClient() as c:
        try:
            resp = await c.get(f"{API_URL}/health", timeout=10.0)
            health = resp.json()
            print(f"\n  Service health: {health.get('status', 'unknown')}")
            if health.get("status") != "healthy":
                print("  ⚠️  Service is not fully healthy. Proceeding anyway...\n")
        except Exception as e:
            print(f"\n  ❌ Cannot reach service at {API_URL}: {e}")
            print("  Make sure to run: uvicorn main:app --port 8000")
            return

    # Build all events
    all_events: list[tuple[dict, str]] = []

    # 1. Profile events (one per user)
    print(f"\n  Generating data for {NUM_USERS} users...")
    user_segments: dict[str, str] = {}

    for i in range(1, NUM_USERS + 1):
        uid = _make_user_id(i)

        # Profile event
        all_events.append((generate_profile_event(uid), "/ingest"))

        # Behavioral events
        for _ in range(EVENTS_PER_USER):
            all_events.append((generate_behavior_event(uid), "/ingest"))

        # Assign a segment
        segment = random.choice(SEGMENTS)
        user_segments[uid] = segment

    # 2. Some users get special segments too
    special_users = random.sample(list(user_segments.keys()), k=min(15, NUM_USERS))
    for uid in special_users:
        special = random.choice(SPECIAL_SEGMENTS)
        all_events.append(({
            "user_id": uid,
            "segment": special,
        }, "/segment"))

    # 3. Primary segment assignments
    for uid, seg in user_segments.items():
        all_events.append(({
            "user_id": uid,
            "segment": seg,
        }, "/segment"))

    random.shuffle(all_events)  # Randomize order for realism

    total = len(all_events)
    print(f"  Total events to send: {total}")
    print(f"  Workers: {NUM_WORKERS}\n")

    start_time = time.time()

    queue: asyncio.Queue = asyncio.Queue(maxsize=NUM_WORKERS * 10)
    counters = {"success": 0, "fail": 0, "total": 0, "expected": total}

    limits = httpx.Limits(max_connections=NUM_WORKERS, max_keepalive_connections=NUM_WORKERS)
    async with httpx.AsyncClient(limits=limits) as client:
        workers = [
            asyncio.create_task(worker(queue, client, counters))
            for _ in range(NUM_WORKERS)
        ]

        for item in all_events:
            await queue.put(item)

        for _ in range(NUM_WORKERS):
            await queue.put(None)

        await asyncio.gather(*workers)

    elapsed = time.time() - start_time
    print(f"\n  {'=' * 50}")
    print(f"  Done! ✅ {counters['success']}/{total} succeeded, "
          f"❌ {counters['fail']} failed")
    print(f"  Took {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Segments assigned: {len(user_segments)}")
    print(f"  {'=' * 50}\n")


if __name__ == "__main__":
    asyncio.run(main())
