"""
Event schema definitions — typed models for structured event ingestion.

Supported event_type values and their expected properties keys:
  purchase            item_name, price_usd, category, quantity (opt), item_id (opt)
  add_to_cart         item_name, price_usd, category (opt)
  page_view           url, duration_seconds (opt), referrer (opt)
  search              query, results_count (opt)
  feedback            text, rating (1-5, opt), feature (opt)
  support_ticket      issue, priority (opt), category (opt)
  session_end         duration_minutes, pages_viewed (opt), device (opt)
  login               device (opt), country (opt)
  feature_usage       feature_name, duration_seconds (opt)
  referral            channel (opt), referred_user_id (opt)
  profile_update      age (opt), occupation (opt), location (opt), interests (opt list)
  subscription_change from_tier, to_tier, reason (opt)
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RichUserEvent(BaseModel):
    """
    Structured event with typed properties dict.
    Primary ingestion format — use POST /ingest/rich or POST /ingest/batch/rich.
    """
    user_id: str
    event_type: str
    timestamp: str          # ISO-8601
    properties: dict[str, Any] = {}


class BatchRichIngestRequest(BaseModel):
    events: list[RichUserEvent]


# ── Legacy flat model (kept for backwards-compat) ─────────────────────────────

class UserEvent(BaseModel):
    """Legacy flat event — still accepted at POST /ingest and POST /ingest/batch."""
    user_id: str
    event_type: str
    description: str
    timestamp: str


class BatchIngestRequest(BaseModel):
    events: list[UserEvent]


class SegmentAssignment(BaseModel):
    user_id: str
    segment: str
