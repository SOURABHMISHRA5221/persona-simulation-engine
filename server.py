import asyncio
import json
import os
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

GRAPHITI_URL = os.environ.get("GRAPHITI_URL", "http://localhost:8000")

ACTION_SET_MAP = {
    "Vote (Standard approval)": "data/actions/vote.json",
    "Sentiment Scale (1-10)":   "data/actions/vote.json",   # fallback until custom set added
    "Feature Adoption Probability": "data/actions/vote.json",
    "ecommerce": "data/actions/ecommerce.json",
    "social":    "data/actions/social.json",
    "vote":      "data/actions/vote.json",
}

# ── Demo seed data — 5 diverse users, 4 events each = 20 events ───────────────

NOW = datetime.now()

DEMO_USERS = [
    {
        "user_id": "demo_alex",
        "segment": "premium",
        "events": [
            {"event_type": "profile_update", "description": "demo_alex is a 29-year-old Software Engineer from San Francisco interested in AI, open-source, and productivity tools.", "timestamp": (NOW - timedelta(days=20)).isoformat()},
            {"event_type": "purchase",       "description": "Purchased premium subscription for $29.99/month after using the free tier for 3 months.", "timestamp": (NOW - timedelta(days=15)).isoformat()},
            {"event_type": "feature_usage",  "description": "Used the API integration feature for 45 minutes to connect with Slack.", "timestamp": (NOW - timedelta(days=8)).isoformat()},
            {"event_type": "feedback",       "description": "User feedback: The API docs are excellent and the dark mode is beautiful. Would love more keyboard shortcuts.", "timestamp": (NOW - timedelta(days=3)).isoformat()},
        ],
    },
    {
        "user_id": "demo_priya",
        "segment": "free",
        "events": [
            {"event_type": "profile_update", "description": "demo_priya is a 24-year-old Student from Austin, TX interested in design, sustainability, and indie games.", "timestamp": (NOW - timedelta(days=18)).isoformat()},
            {"event_type": "search",         "description": "Searched for: pricing plans and upgrade options", "timestamp": (NOW - timedelta(days=14)).isoformat()},
            {"event_type": "feedback",       "description": "User feedback: The free tier is too limited now. I keep hitting the export cap. Considering switching to a competitor.", "timestamp": (NOW - timedelta(days=6)).isoformat()},
            {"event_type": "support_ticket", "description": "Opened support ticket: billing issue — was charged twice for the same month.", "timestamp": (NOW - timedelta(days=2)).isoformat()},
        ],
    },
    {
        "user_id": "demo_marco",
        "segment": "basic",
        "events": [
            {"event_type": "profile_update", "description": "demo_marco is a 41-year-old Small Business Owner from London interested in marketing, analytics, and travel.", "timestamp": (NOW - timedelta(days=25)).isoformat()},
            {"event_type": "purchase",       "description": "Purchased basic plan for $9.99/month after a 14-day trial.", "timestamp": (NOW - timedelta(days=20)).isoformat()},
            {"event_type": "feature_usage",  "description": "Used the analytics dashboard for 30 minutes, viewed monthly reports.", "timestamp": (NOW - timedelta(days=10)).isoformat()},
            {"event_type": "feedback",       "description": "User feedback: Good value for small teams. The mobile app is smooth but I wish it had offline mode.", "timestamp": (NOW - timedelta(days=4)).isoformat()},
        ],
    },
    {
        "user_id": "demo_yuki",
        "segment": "premium",
        "events": [
            {"event_type": "profile_update", "description": "demo_yuki is a 35-year-old Product Manager from Tokyo interested in UX research, productivity, and cooking.", "timestamp": (NOW - timedelta(days=30)).isoformat()},
            {"event_type": "purchase",       "description": "Upgraded from basic to premium for $29.99/month for advanced collaboration tools.", "timestamp": (NOW - timedelta(days=22)).isoformat()},
            {"event_type": "referral",       "description": "Referred 3 new users via email invite from their company domain.", "timestamp": (NOW - timedelta(days=12)).isoformat()},
            {"event_type": "feedback",       "description": "User feedback: The team collaboration features are exactly what we needed. Performance has improved dramatically.", "timestamp": (NOW - timedelta(days=5)).isoformat()},
        ],
    },
    {
        "user_id": "demo_clara",
        "segment": "free",
        "events": [
            {"event_type": "profile_update", "description": "demo_clara is a 52-year-old Teacher from Chicago interested in education technology, community, and reading.", "timestamp": (NOW - timedelta(days=22)).isoformat()},
            {"event_type": "search",         "description": "Searched for: how to cancel subscription", "timestamp": (NOW - timedelta(days=16)).isoformat()},
            {"event_type": "support_ticket", "description": "Opened support ticket: feature request — need bulk export for classroom data.", "timestamp": (NOW - timedelta(days=9)).isoformat()},
            {"event_type": "feedback",       "description": "User feedback: Love the concept but the pricing is out of reach for most educators. A teacher discount would make a huge difference.", "timestamp": (NOW - timedelta(days=1)).isoformat()},
        ],
    },
]


@app.get("/api/simulate")
async def simulate(
    campaign: str = "Should we add a dark mode?",
    agents: int = 5,
    hours: int = 24,
    action_set: str = "Vote (Standard approval)"
):
    actions_path = ACTION_SET_MAP.get(action_set, "data/actions/vote.json")

    async def event_generator():
        cmd = [
            "python3", "-u", "main.py",
            "--campaign", campaign,
            "--agents", str(agents),
            "--hours", str(hours),
            "--actions", actions_path,
            "--ollama-cloud"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded_line = line.decode('utf-8').strip()
            if not decoded_line:
                continue
            yield f"data: {json.dumps({'text': decoded_line})}\n\n"

        await process.wait()
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/ingest-demo")
async def ingest_demo():
    """
    Ingest 5 diverse demo users (20 events total) into the Graphiti KG service.
    Streams SSE progress so the frontend can show a live log.
    """
    def sse(payload: dict) -> str:
        return "data: " + json.dumps(payload) + "\n\n"

    async def event_generator():
        total_events = sum(len(u["events"]) for u in DEMO_USERS)
        ingested = 0

        yield sse({"text": f"Starting demo data ingestion — {len(DEMO_USERS)} users, {total_events} events..."})

        # Check graphiti health first
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(GRAPHITI_URL + "/health", timeout=10.0)
                health = resp.json()
                if health.get("status") != "healthy":
                    yield sse({"text": "Graphiti service not healthy — is graphiti_service running on :8000?", "error": True})
                    yield sse({"done": True, "success": False})
                    return
                n = health.get("users_tracked", 0)
                yield sse({"text": f"Graphiti service healthy — {n} users already in graph."})
        except Exception as e:
            yield sse({"text": f"Cannot reach Graphiti at {GRAPHITI_URL}: {e}", "error": True})
            yield sse({"done": True, "success": False})
            return

        # Ingest events user by user
        async with httpx.AsyncClient() as client:
            for user in DEMO_USERS:
                uid = user["user_id"]
                n_events = len(user["events"])
                yield sse({"text": f"[{uid}] Ingesting {n_events} events..."})

                for event in user["events"]:
                    payload = {
                        "user_id": uid,
                        "event_type": event["event_type"],
                        "description": event["description"],
                        "timestamp": event["timestamp"],
                    }
                    etype = event["event_type"]
                    try:
                        resp = await client.post(
                            GRAPHITI_URL + "/ingest",
                            json=payload,
                            timeout=180.0,
                        )
                        if resp.status_code == 200:
                            ingested += 1
                            yield sse({"text": f"  ✓ {etype}", "ingested": ingested, "total": total_events})
                        else:
                            yield sse({"text": f"  ✗ {etype} — {resp.status_code}", "error": True})
                    except Exception as e:
                        yield sse({"text": f"  ✗ {etype} — {e}", "error": True})

                # Assign segment
                seg = user["segment"]
                try:
                    await client.post(
                        GRAPHITI_URL + "/segment",
                        json={"user_id": uid, "segment": seg},
                        timeout=120.0,
                    )
                    yield sse({"text": f"  ✓ segment → {seg}"})
                except Exception as e:
                    yield sse({"text": f"  ✗ segment failed: {e}", "error": True})

        yield sse({"text": f"Done! {ingested}/{total_events} events queued. KG is building in the background — run simulation in ~30s."})
        yield sse({"done": True, "success": True, "ingested": ingested, "total": total_events})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Mount React Frontend for Production Deployment
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    async def fallback():
        return {"status": "Backend is running. In dev mode, run the frontend via Vite on port 5173."}
