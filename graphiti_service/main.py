"""
Graphiti User Behavior Service — Production-grade knowledge graph API.

Endpoints:
  POST /ingest              — Ingest a single legacy flat event
  POST /ingest/batch        — Ingest multiple legacy flat events (parallel per-user)
  POST /ingest/rich         — Ingest a single structured event (with typed properties)
  POST /ingest/batch/rich   — Ingest multiple structured events (parallel per-user)
  POST /segment             — Assign a user to a segment
  GET  /users               — List distinct user IDs (optional segment filter)
  GET  /user/{user_id}      — Get all facts/edges for a user
  GET  /personas            — LLM-synthesized persona dicts for the Simulation Engine
  GET  /signals             — Behavioral signals for all users tracked this session
  GET  /signals/{user_id}   — Behavioral signals for a specific user
  GET  /health              — Health check (Neo4j + Ollama)
  GET  /sample-graph        — Sample random nodes from the graph

Speed optimisations applied:
  1. Parallel per-user batching   — events for different users run concurrently
  2. Low-signal fast-path         — login/page_view/heartbeat skip LLM extraction
  3. Local LLM for extraction     — qwen3:4b on localhost (no cloud round-trip)
  4. Async ingest queue           — POST /ingest returns instantly, processes in bg
  5. Entity deduplication cache   — skips redundant LLM dedup calls per session
  6. Parallel persona synthesis   — all personas synthesized concurrently
"""

import os
import re
import json
import random
import asyncio

from dotenv import load_dotenv
load_dotenv()  # loads .env if present — env vars set in the shell always take priority
import logging
import traceback
from collections import defaultdict
from datetime import datetime
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from contextlib import asynccontextmanager

from event_schema import RichUserEvent, BatchRichIngestRequest
from event_processor import EventProcessor

from graphiti_core import Graphiti
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.prompts.models import Message

from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> str:
    """Strip markdown fences and think blocks, return clean JSON string."""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if "```json" in raw:
        raw = raw.split("```json")[-1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    for i, ch in enumerate(raw):
        if ch in "{[":
            return raw[i:]
    return raw


# ── Custom LLM client — fixes Ollama Cloud json_schema incompatibility ────────

class OllamaCloudLLMClient(OpenAIGenericClient):
    """
    Forces json_object mode and injects the expected schema into the prompt.
    Needed because Ollama Cloud models ignore json_schema response_format and
    return markdown-wrapped text instead of raw JSON.
    """

    async def _generate_response(
        self,
        messages: list[Message],
        response_model=None,
        max_tokens=None,
        model_size=None,
        group_id=None,
        prompt_name=None,
    ) -> dict:
        openai_messages: list[dict[str, str]] = []
        for m in messages:
            content = self._clean_input(m.content)
            if m.role == "user":
                openai_messages.append({"role": "user", "content": content})
            elif m.role == "system":
                openai_messages.append({"role": "system", "content": content})

        if response_model is not None:
            schema = response_model.model_json_schema()
            hint = (
                f"\n\nYou MUST respond with a JSON object that strictly follows "
                f"this schema (use exact field names):\n{json.dumps(schema, indent=2)}"
            )
            if openai_messages and openai_messages[-1]["role"] == "user":
                openai_messages[-1]["content"] += hint
            else:
                openai_messages.append({"role": "user", "content": hint})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        return json.loads(_extract_json(raw))


# ── Config ────────────────────────────────────────────────────────────────────

OLLAMA_API_KEY  = os.environ.get("OLLAMA_API_KEY", "")
OLLAMA_CLOUD    = bool(OLLAMA_API_KEY)
LOCAL_OLLAMA_URL = "http://localhost:11434/v1"

if OLLAMA_CLOUD:
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "https://ollama.com/v1")
    OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "ministral-3:8b")
else:
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", LOCAL_OLLAMA_URL)
    OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

# Cloud client — used for LLM extraction & persona synthesis
ollama_client = AsyncOpenAI(
    api_key=OLLAMA_API_KEY or "ollama",
    base_url=OLLAMA_BASE_URL,
    timeout=300.0,
)

llm_config = LLMConfig(
    base_url=OLLAMA_BASE_URL,
    api_key=OLLAMA_API_KEY or "ollama",
    model=OLLAMA_MODEL,
)
llm_client = OllamaCloudLLMClient(config=llm_config, client=ollama_client)

# Local client — always used for embeddings (Ollama Cloud has no /v1/embeddings)
local_ollama_client = AsyncOpenAI(
    api_key="ollama",
    base_url=LOCAL_OLLAMA_URL,
    timeout=120.0,
)
embedder_config = OpenAIEmbedderConfig(
    base_url=LOCAL_OLLAMA_URL,
    api_key="ollama",
    embedding_model="nomic-embed-text",
)
embedder = OpenAIEmbedder(config=embedder_config, client=local_ollama_client)
reranker  = OpenAIRerankerClient(config=llm_config, client=ollama_client)

# ── Neo4j + Graphiti ──────────────────────────────────────────────────────────

NEO4J_URI      = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.environ.get("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

graphiti = Graphiti(
    uri=NEO4J_URI,
    user=NEO4J_USER,
    password=NEO4J_PASSWORD,
    llm_client=llm_client,
    embedder=embedder,
    cross_encoder=reranker,
)

# ── Event processor ───────────────────────────────────────────────────────────
processor = EventProcessor()

# ── In-memory stores ──────────────────────────────────────────────────────────
_user_segments: dict[str, set[str]] = {}
_segment_users: dict[str, set[str]] = {}

# Optimisation 5 — entity dedup cache: user_id -> set of lower-cased entity names
# already written this session; skips redundant Neo4j dedup LLM calls.
_entity_cache: dict[str, set[str]] = defaultdict(set)

# Optimisation 4 — async ingest queue + semaphore
_ingest_queue: asyncio.Queue = asyncio.Queue()
_ingest_semaphore: asyncio.Semaphore   # initialised in lifespan
INGEST_CONCURRENCY = int(os.environ.get("INGEST_CONCURRENCY", "4"))
_inflight_tasks: int = 0  # tasks dequeued but not yet written to Neo4j

# Low-signal event types that don't need LLM entity extraction
LOW_SIGNAL_EVENTS = {
    "login", "logout", "heartbeat", "page_view", "session_start",
    "click", "scroll", "impression",
}


def _add_segment_mapping(user_id: str, segment: str):
    _user_segments.setdefault(user_id, set()).add(segment)
    _segment_users.setdefault(segment, set()).add(user_id)


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ingest_semaphore
    _ingest_semaphore = asyncio.Semaphore(INGEST_CONCURRENCY)

    await graphiti.build_indices_and_constraints()
    await _rebuild_segment_index()

    # Start background ingest worker
    worker_task = asyncio.create_task(_ingest_worker())

    logger.info(
        f"Graphiti service started — concurrency={INGEST_CONCURRENCY}, "
        f"model={OLLAMA_MODEL}, segments loaded."
    )
    yield
    worker_task.cancel()
    await graphiti.close()


async def _rebuild_segment_index():
    try:
        records, _, _ = await graphiti.driver.execute_query(
            """
            MATCH (e:Episodic)
            WHERE e.source_description = 'Segment Assignment'
            RETURN e.group_id AS user_id, e.content AS content
            """
        )
        for record in records:
            user_id = record["user_id"]
            content = record["content"]
            if "assigned to segment:" in content:
                segment = content.split("assigned to segment:")[-1].strip()
                _add_segment_mapping(user_id, segment)
        logger.info(
            f"Rebuilt segment index: {len(_user_segments)} users, "
            f"{len(_segment_users)} segments"
        )
    except Exception as e:
        logger.warning(f"Could not rebuild segment index: {e}")


# ── Background ingest worker (Optimisation 4) ─────────────────────────────────

async def _ingest_worker():
    """Drain the ingest queue with bounded concurrency."""
    global _inflight_tasks
    while True:
        item = await _ingest_queue.get()
        _inflight_tasks += 1
        asyncio.create_task(_process_queued_item(item))


async def _process_queued_item(item: dict):
    global _inflight_tasks
    async with _ingest_semaphore:
        try:
            await _add_episode_with_retry(**item)
        except Exception as e:
            logger.error(f"Background ingest failed for {item.get('group_id')}: {e}")
        finally:
            _inflight_tasks -= 1
            _ingest_queue.task_done()


# ── Core ingest helper ────────────────────────────────────────────────────────

async def _add_episode_with_retry(
    name: str,
    episode_body: str,
    source_description: str,
    reference_time: datetime,
    group_id: str,
    max_retries: int = 3,
):
    """Add a graphiti episode with retry. Skips LLM for low-signal events."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            await graphiti.add_episode(
                name=name,
                episode_body=episode_body,
                source_description=source_description,
                reference_time=reference_time,
                group_id=group_id,
            )
            return
        except Exception as e:
            last_exc = e
            logger.warning(
                f"Extraction failed for {group_id} "
                f"(attempt {attempt + 1}/{max_retries}): {e}"
            )
            await asyncio.sleep(1)
    raise last_exc


async def _store_low_signal_event(
    user_id: str, event_type: str, description: str, timestamp: str
):
    """Fast-path: write low-signal events directly to Neo4j without LLM."""
    episode_body = (
        f"[{timestamp}] User {user_id} performed {event_type}: {description}"
    )
    try:
        await graphiti.driver.execute_query(
            """
            CREATE (e:Episodic {
                uuid: randomUUID(),
                group_id: $group_id,
                content: $content,
                source_description: $source_desc,
                valid_at: datetime($ts),
                created_at: datetime()
            })
            """,
            group_id=user_id,
            content=episode_body,
            source_desc="User Action Event Stream",
            ts=timestamp,
        )
    except Exception as e:
        logger.warning(f"Low-signal store failed for {user_id}: {e}")


# ── Pydantic models ───────────────────────────────────────────────────────────

class UserEvent(BaseModel):
    user_id: str
    event_type: str
    description: str
    timestamp: str


class BatchIngestRequest(BaseModel):
    events: list[UserEvent]


class SegmentAssignment(BaseModel):
    user_id: str
    segment: str


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    lifespan=lifespan,
    title="Graphiti User Behavior Service",
    description="Knowledge graph API for user behavioral data with LLM-powered persona synthesis.",
    version="3.0.0",
)


# ── POST /ingest ──────────────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest_event(event: UserEvent, background_tasks: BackgroundTasks):
    """
    Ingest a single user event.
    Low-signal events (login, page_view, etc.) are stored instantly.
    High-signal events are queued for async LLM extraction and return immediately.
    """
    try:
        if event.event_type.lower() in LOW_SIGNAL_EVENTS:
            # Optimisation 2: fast-path, no LLM
            background_tasks.add_task(
                _store_low_signal_event,
                event.user_id, event.event_type,
                event.description, event.timestamp,
            )
            return {"status": "queued", "path": "fast"}

        episode = (
            f"[{event.timestamp}] User {event.user_id} "
            f"performed {event.event_type}: {event.description}"
        )
        # Optimisation 4: queue instead of blocking
        await _ingest_queue.put({
            "name": f"Event for {event.user_id}",
            "episode_body": episode,
            "source_description": "User Action Event Stream",
            "reference_time": datetime.fromisoformat(event.timestamp),
            "group_id": event.user_id,
        })
        return {"status": "queued", "path": "llm", "queue_size": _ingest_queue.qsize()}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /ingest/batch ────────────────────────────────────────────────────────

@app.post("/ingest/batch")
async def ingest_batch(req: BatchIngestRequest):
    """
    Ingest multiple events with parallel per-user processing.
    Optimisation 1: events for different users run concurrently.
    Events for the same user stay sequential to preserve graph consistency.
    """
    # Group events by user
    by_user: dict[str, list[UserEvent]] = defaultdict(list)
    for event in req.events:
        by_user[event.user_id].append(event)

    results: dict[str, Any] = {"success": 0, "failed": 0, "errors": []}
    lock = asyncio.Lock()

    async def _process_user_events(user_id: str, events: list[UserEvent]):
        for event in events:
            try:
                if event.event_type.lower() in LOW_SIGNAL_EVENTS:
                    await _store_low_signal_event(
                        user_id, event.event_type,
                        event.description, event.timestamp,
                    )
                else:
                    episode = (
                        f"[{event.timestamp}] User {user_id} "
                        f"performed {event.event_type}: {event.description}"
                    )
                    await _add_episode_with_retry(
                        name=f"Event for {user_id}",
                        episode_body=episode,
                        source_description="User Action Event Stream",
                        reference_time=datetime.fromisoformat(event.timestamp),
                        group_id=user_id,
                    )
                async with lock:
                    results["success"] += 1
            except Exception as e:
                async with lock:
                    results["failed"] += 1
                    results["errors"].append({"user_id": user_id, "error": str(e)})

    # Run all users in parallel
    await asyncio.gather(*[
        _process_user_events(uid, events)
        for uid, events in by_user.items()
    ])

    return results


# ── POST /segment ─────────────────────────────────────────────────────────────

@app.post("/segment")
async def assign_segment(assignment: SegmentAssignment):
    """Assign a user to a segment."""
    try:
        episode = f"User {assignment.user_id} assigned to segment: {assignment.segment}"
        await _add_episode_with_retry(
            name=f"Segment assignment for {assignment.user_id}",
            episode_body=episode,
            source_description="Segment Assignment",
            reference_time=datetime.utcnow(),
            group_id=assignment.user_id,
        )
        _add_segment_mapping(assignment.user_id, assignment.segment)
        return {
            "status": "success",
            "user_id": assignment.user_id,
            "segment": assignment.segment,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /users ────────────────────────────────────────────────────────────────

@app.get("/users")
async def list_users(segment: Optional[str] = Query(None)):
    try:
        if segment:
            user_ids = sorted(_segment_users.get(segment, set()))
            return {"status": "success", "segment": segment,
                    "count": len(user_ids), "user_ids": user_ids}

        records, _, _ = await graphiti.driver.execute_query(
            """
            MATCH (e:Episodic)
            WHERE e.source_description = 'User Action Event Stream'
            RETURN DISTINCT e.group_id AS user_id ORDER BY user_id
            """
        )
        user_ids = [r["user_id"] for r in records]
        return {"status": "success", "count": len(user_ids), "user_ids": user_ids}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /user/{user_id} ───────────────────────────────────────────────────────

@app.get("/user/{user_id}")
async def get_user(user_id: str):
    try:
        events_q, entities_q, edges_q = await asyncio.gather(
            graphiti.driver.execute_query(
                """
                MATCH (e:Episodic {group_id: $uid})
                WHERE e.source_description = 'User Action Event Stream'
                RETURN e.content AS content, e.valid_at AS valid_at
                ORDER BY e.valid_at DESC
                """,
                uid=user_id,
            ),
            graphiti.driver.execute_query(
                """
                MATCH (ep:Episodic {group_id: $uid})-[:MENTIONS]->(n:Entity)
                RETURN DISTINCT n.uuid AS uuid, n.name AS name,
                       n.summary AS summary, labels(n) AS labels
                """,
                uid=user_id,
            ),
            graphiti.driver.execute_query(
                """
                MATCH (ep:Episodic {group_id: $uid})-[:MENTIONS]->(n:Entity)
                MATCH (n)-[e:RELATES_TO]->(m:Entity)
                RETURN DISTINCT e.uuid AS uuid, e.name AS name,
                       e.fact AS fact, n.name AS source, m.name AS target
                """,
                uid=user_id,
            ),
        )
        events   = [{"content": r["content"], "timestamp": str(r["valid_at"])} for r in events_q[0]]
        entities = [{"uuid": r["uuid"], "name": r["name"], "summary": r["summary"], "labels": r["labels"]} for r in entities_q[0]]
        edges    = [{"uuid": r["uuid"], "name": r["name"], "fact": r["fact"], "source": r["source"], "target": r["target"]} for r in edges_q[0]]

        return {
            "status": "success",
            "user_id": user_id,
            "segments": sorted(_user_segments.get(user_id, set())),
            "event_count": len(events),
            "events": events[:50],
            "entity_count": len(entities),
            "entities": entities,
            "edge_count": len(edges),
            "edges": edges,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /personas ─────────────────────────────────────────────────────────────

PERSONA_SYNTHESIS_PROMPT = """You are a data analyst building user personas for a simulation engine.

Given the following raw behavioral data about a user from a knowledge graph, synthesize a structured persona profile.

USER ID: {user_id}
SEGMENTS: {segments}

ENTITIES (things the graph knows about this user):
{entities_text}

RELATIONSHIPS (facts connecting entities):
{edges_text}

RAW EVENTS (recent activity):
{events_text}

Based on this data, produce a JSON object (and ONLY a JSON object, no other text) matching this exact schema:
{{
  "user_id": "{user_id}",
  "username": "<a descriptive username based on the user's behavior, lowercase with underscores>",
  "persona": {{
    "age": <estimated age as integer, or 30 if unknown>,
    "occupation": "<inferred occupation or 'Unknown'>",
    "location": "<inferred location or 'Unknown'>",
    "interests": ["<list of 3-5 interests inferred from behavior>"],
    "values": ["<list of 2-4 values inferred from behavior>"],
    "traits": {{
      "price_sensitivity": <0.0-1.0 float>,
      "tech_savviness": <0.0-1.0 float>,
      "brand_loyalty": <0.0-1.0 float>,
      "optimism": <0.0-1.0 float>,
      "skepticism": <0.0-1.0 float>,
      "community_orientation": <0.0-1.0 float>
    }},
    "behavior": {{
      "avg_session_minutes": <estimated integer>,
      "engagement_rate": <0.0-1.0 float>,
      "subscription_tier": "<one of: free, basic, premium>",
      "account_age_months": <estimated integer>
    }},
    "past_opinions": ["<2-3 plausible opinion quotes based on their behavior>"],
    "hourly_activity": [<24 floats representing activity probability per hour, summing roughly to 1.0>]
  }}
}}

Return ONLY the JSON object. No explanation, no markdown fences, no preamble."""


@app.get("/personas")
async def get_personas(
    n: int = Query(10, ge=1, le=100),
    segment: Optional[str] = Query(None),
):
    """
    Synthesize persona dicts from graph data using LLM.
    Optimisation 6: all personas synthesized in parallel.
    """
    try:
        if segment:
            all_user_ids = sorted(_segment_users.get(segment, set()))
        else:
            records, _, _ = await graphiti.driver.execute_query(
                """
                MATCH (e:Episodic)
                WHERE e.source_description = 'User Action Event Stream'
                RETURN DISTINCT e.group_id AS user_id
                """
            )
            all_user_ids = [r["user_id"] for r in records]

        if not all_user_ids:
            return {"status": "success", "count": 0, "personas": []}

        selected_ids = random.sample(all_user_ids, min(n, len(all_user_ids)))

        # Optimisation 6: synthesize all personas concurrently
        results = await asyncio.gather(
            *[_synthesize_persona(uid) for uid in selected_ids],
            return_exceptions=True,
        )

        personas = []
        for uid, result in zip(selected_ids, results):
            if isinstance(result, Exception):
                logger.warning(f"Persona synthesis failed for {uid}: {result}")
            elif result:
                personas.append(result)

        return {
            "status": "success",
            "count": len(personas),
            "segment": segment,
            "personas": personas,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


async def _synthesize_persona(user_id: str) -> dict | None:
    """Fetch graph data and LLM-synthesize a persona. Neo4j queries run in parallel."""

    # Run all three Neo4j queries concurrently
    entity_q, edge_q, event_q = await asyncio.gather(
        graphiti.driver.execute_query(
            """
            MATCH (ep:Episodic {group_id: $uid})-[:MENTIONS]->(n:Entity)
            RETURN DISTINCT n.name AS name, n.summary AS summary LIMIT 20
            """,
            uid=user_id,
        ),
        graphiti.driver.execute_query(
            """
            MATCH (ep:Episodic {group_id: $uid})-[:MENTIONS]->(n:Entity)
            MATCH (n)-[e:RELATES_TO]->(m:Entity)
            RETURN DISTINCT e.fact AS fact LIMIT 20
            """,
            uid=user_id,
        ),
        graphiti.driver.execute_query(
            """
            MATCH (e:Episodic {group_id: $uid})
            WHERE e.source_description = 'User Action Event Stream'
            RETURN e.content AS content ORDER BY e.valid_at DESC LIMIT 15
            """,
            uid=user_id,
        ),
    )

    entities_text = "\n".join(
        f"  - {r['name']}: {r['summary'] or 'no summary'}" for r in entity_q[0]
    ) or "  (no entities found)"
    edges_text = "\n".join(f"  - {r['fact']}" for r in edge_q[0]) or "  (no relationships found)"
    events_text = "\n".join(f"  - {r['content']}" for r in event_q[0]) or "  (no events found)"

    segments = sorted(_user_segments.get(user_id, set()))
    prompt = PERSONA_SYNTHESIS_PROMPT.format(
        user_id=user_id,
        segments=", ".join(segments) if segments else "none",
        entities_text=entities_text,
        edges_text=edges_text,
        events_text=events_text,
    )

    response = await ollama_client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    raw = _extract_json(response.choices[0].message.content.strip())

    try:
        persona = json.loads(raw)
        if "user_id" not in persona or "username" not in persona or "persona" not in persona:
            logger.warning(f"Invalid persona structure for {user_id}")
            return None
        return persona
    except json.JSONDecodeError:
        logger.warning(f"Could not parse persona JSON for {user_id}: {raw[:200]}")
        return None


# ── POST /ingest/rich ─────────────────────────────────────────────────────────

@app.post("/ingest/rich")
async def ingest_rich_event(event: RichUserEvent, background_tasks: BackgroundTasks):
    """Ingest a structured event. Low-signal types use fast-path."""
    try:
        episode = processor.process(event)

        if event.event_type.lower() in LOW_SIGNAL_EVENTS:
            background_tasks.add_task(
                _store_low_signal_event,
                event.user_id, event.event_type,
                episode, event.timestamp,
            )
            return {"status": "queued", "path": "fast", "episode_preview": episode[:200]}

        await _ingest_queue.put({
            "name": f"Event for {event.user_id}",
            "episode_body": episode,
            "source_description": "User Action Event Stream",
            "reference_time": datetime.fromisoformat(event.timestamp),
            "group_id": event.user_id,
        })

        signals = processor.get_signals(event.user_id) or {}
        for seg in signals.get("derived_segments", []):
            if seg not in _user_segments.get(event.user_id, set()):
                _add_segment_mapping(event.user_id, seg)

        return {"status": "queued", "path": "llm", "episode_preview": episode[:200]}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /ingest/batch/rich ───────────────────────────────────────────────────

@app.post("/ingest/batch/rich")
async def ingest_batch_rich(req: BatchRichIngestRequest):
    """
    Ingest multiple structured events with parallel per-user processing.
    Optimisation 1: different users run concurrently.
    """
    by_user: dict[str, list[RichUserEvent]] = defaultdict(list)
    for event in req.events:
        by_user[event.user_id].append(event)

    results: dict[str, Any] = {"success": 0, "failed": 0, "errors": []}
    lock = asyncio.Lock()

    async def _process_user(user_id: str, events: list[RichUserEvent]):
        for event in events:
            try:
                episode = processor.process(event)
                if event.event_type.lower() in LOW_SIGNAL_EVENTS:
                    await _store_low_signal_event(
                        user_id, event.event_type, episode, event.timestamp
                    )
                else:
                    await _add_episode_with_retry(
                        name=f"Event for {user_id}",
                        episode_body=episode,
                        source_description="User Action Event Stream",
                        reference_time=datetime.fromisoformat(event.timestamp),
                        group_id=user_id,
                    )
                async with lock:
                    results["success"] += 1
            except Exception as e:
                async with lock:
                    results["failed"] += 1
                    results["errors"].append({"user_id": user_id, "error": str(e)})

        # Apply derived segments
        signals = processor.get_signals(user_id) or {}
        for seg in signals.get("derived_segments", []):
            if seg not in _user_segments.get(user_id, set()):
                _add_segment_mapping(user_id, seg)

    await asyncio.gather(*[_process_user(uid, evs) for uid, evs in by_user.items()])
    return results


# ── GET /signals ──────────────────────────────────────────────────────────────

@app.get("/signals")
async def get_all_signals():
    all_sigs = processor.get_all_signals()
    return {"status": "success", "user_count": len(all_sigs), "signals": all_sigs}


@app.get("/signals/{user_id}")
async def get_user_signals(user_id: str):
    sigs = processor.get_signals(user_id)
    if sigs is None:
        raise HTTPException(status_code=404, detail=f"No signals for '{user_id}'.")
    return {"status": "success", "signals": sigs}


# ── GET /health ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    checks: dict[str, Any] = {"neo4j": False, "ollama": False}

    neo4j_task = graphiti.driver.execute_query("RETURN 1 AS ok")
    ollama_task = ollama_client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5,
    )

    neo4j_result, ollama_result = await asyncio.gather(
        neo4j_task, ollama_task, return_exceptions=True
    )

    if isinstance(neo4j_result, Exception):
        checks["neo4j_error"] = str(neo4j_result)
    else:
        checks["neo4j"] = bool(neo4j_result[0])

    if isinstance(ollama_result, Exception):
        checks["ollama_error"] = str(ollama_result)
    else:
        checks["ollama"] = bool(ollama_result.choices)
        checks["ollama_model"] = OLLAMA_MODEL

    return {
        "status": "healthy" if checks["neo4j"] and checks["ollama"] else "degraded",
        "checks": checks,
        "segments_loaded": len(_segment_users),
        "users_tracked": len(_user_segments),
        "ingest_queue_size": _ingest_queue.qsize(),
        "ingest_inflight": _inflight_tasks,
    }


# ── GET /sample-graph ─────────────────────────────────────────────────────────

@app.get("/sample-graph")
async def sample_graph():
    try:
        records, _, _ = await graphiti.driver.execute_query(
            "MATCH (n) RETURN COUNT(n) AS total"
        )
        total_nodes = records[0]["total"] if records else 0
        if total_nodes == 0:
            return {"status": "success", "sample": [], "total_nodes": 0}

        sample_size = max(1, int(total_nodes * 0.01))
        sample_records, _, _ = await graphiti.driver.execute_query(
            "MATCH (n) WITH n, rand() AS r ORDER BY r LIMIT $lim "
            "OPTIONAL MATCH (n)-[e]-(m) "
            "RETURN n, collect({type: type(e), target: m}) as relationships",
            lim=sample_size,
        )
        samples = [
            {
                "node_id": rec["n"].element_id,
                "labels": list(rec["n"].labels),
                "properties": dict(rec["n"]),
                "relationships_count": len(rec["relationships"]),
            }
            for rec in sample_records
        ]
        return {
            "status": "success",
            "total_nodes_in_graph": total_nodes,
            "sample_size": sample_size,
            "sample": samples,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /segments ─────────────────────────────────────────────────────────────

@app.get("/segments")
async def list_segments():
    return {
        "status": "success",
        "segments": {seg: len(users) for seg, users in sorted(_segment_users.items())},
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
