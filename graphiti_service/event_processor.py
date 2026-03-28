"""
EventProcessor — converts RichUserEvents into signal-rich episode text for
Graphiti KG ingestion, while accumulating per-user behavioral signals.

Design
------
- Each call to .process() updates UserSignals for that user and returns a
  verbose episode string.  Verbosity is intentional: Graphiti's LLM extractor
  creates richer entities and relationships when context is dense.
- .get_signals(user_id)        → structured numeric signals dict
- .get_all_signals()           → signals for every tracked user
- UserSignals.derived_segments() → auto-computed segment tags
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from event_schema import RichUserEvent

logger = logging.getLogger(__name__)


# ── Per-user signal accumulator ───────────────────────────────────────────────

class UserSignals:
    """Mutable behavioral signal state for one user."""

    def __init__(self, user_id: str):
        self.user_id = user_id

        # Purchase
        self.purchase_count: int = 0
        self.total_spend: float = 0.0
        self.purchase_categories: Counter = Counter()

        # Engagement
        self.session_count: int = 0
        self.total_session_minutes: int = 0
        self.login_count: int = 0
        self.pages_viewed: int = 0

        # Feedback
        self.positive_feedback: int = 0
        self.negative_feedback: int = 0
        self.ratings: list[int] = []

        # Support
        self.support_tickets: int = 0
        self.support_categories: Counter = Counter()

        # Feature / search / cart
        self.features_used: Counter = Counter()
        self.search_queries: list[str] = []
        self.cart_additions: int = 0

        # Profile
        self.age: int | None = None
        self.occupation: str | None = None
        self.location: str | None = None
        self.interests: list[str] = []
        self.subscription_tier: str = "unknown"

        # Recency
        self.first_seen: datetime | None = None
        self.last_seen: datetime | None = None

    # ── Derived properties ────────────────────────────────────────────────

    @property
    def avg_order_value(self) -> float:
        return round(self.total_spend / self.purchase_count, 2) if self.purchase_count else 0.0

    @property
    def avg_session_minutes(self) -> float:
        return round(self.total_session_minutes / self.session_count, 1) if self.session_count else 0.0

    @property
    def avg_rating(self) -> float | None:
        return round(sum(self.ratings) / len(self.ratings), 1) if self.ratings else None

    @property
    def top_category(self) -> str | None:
        return self.purchase_categories.most_common(1)[0][0] if self.purchase_categories else None

    @property
    def sentiment_ratio(self) -> str:
        total = self.positive_feedback + self.negative_feedback
        if total == 0:
            return "neutral"
        ratio = self.positive_feedback / total
        if ratio >= 0.7:
            return "positive"
        if ratio <= 0.3:
            return "negative"
        return "mixed"

    @property
    def account_age_days(self) -> int | None:
        if self.first_seen:
            now = datetime.now(timezone.utc)
            fs = self.first_seen if self.first_seen.tzinfo else self.first_seen.replace(tzinfo=timezone.utc)
            return (now - fs).days
        return None

    def derived_segments(self) -> list[str]:
        """Compute behaviorally-derived segment tags from accumulated signals."""
        segs: list[str] = []

        if self.total_spend >= 500 or self.purchase_count >= 5:
            segs.append("high-value-buyer")

        if self.session_count >= 20 or len(self.features_used) >= 5:
            segs.append("power-user")

        if self.support_tickets >= 3 or self.negative_feedback > self.positive_feedback:
            segs.append("churn-risk")

        if self.last_seen:
            ls = self.last_seen if self.last_seen.tzinfo else self.last_seen.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - ls).days >= 30:
                segs.append("dormant")

        if self.session_count >= 10 and self.sentiment_ratio == "positive":
            segs.append("engaged")

        deal_terms = {"cheap", "discount", "alternative", "cancel", "refund", "free"}
        if any(term in q.lower() for q in self.search_queries for term in deal_terms):
            segs.append("deal-seeker")

        if self.purchase_count >= 2 and self.cart_additions >= 5:
            segs.append("repeat-buyer")

        return segs

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "purchase": {
                "count": self.purchase_count,
                "total_spend": round(self.total_spend, 2),
                "avg_order_value": self.avg_order_value,
                "top_category": self.top_category,
                "categories": dict(self.purchase_categories),
            },
            "engagement": {
                "session_count": self.session_count,
                "total_session_minutes": self.total_session_minutes,
                "avg_session_minutes": self.avg_session_minutes,
                "login_count": self.login_count,
                "pages_viewed": self.pages_viewed,
            },
            "feedback": {
                "positive_count": self.positive_feedback,
                "negative_count": self.negative_feedback,
                "avg_rating": self.avg_rating,
                "sentiment_ratio": self.sentiment_ratio,
            },
            "support": {
                "ticket_count": self.support_tickets,
                "categories": dict(self.support_categories),
            },
            "features": {
                "distinct_count": len(self.features_used),
                "usage_counts": dict(self.features_used),
            },
            "browse": {
                "cart_additions": self.cart_additions,
                "search_count": len(self.search_queries),
                "recent_searches": self.search_queries[-10:],
            },
            "profile": {
                "age": self.age,
                "occupation": self.occupation,
                "location": self.location,
                "interests": self.interests,
                "subscription_tier": self.subscription_tier,
            },
            "recency": {
                "first_seen": self.first_seen.isoformat() if self.first_seen else None,
                "last_seen": self.last_seen.isoformat() if self.last_seen else None,
                "account_age_days": self.account_age_days,
            },
            "derived_segments": self.derived_segments(),
        }


# ── Event Processor ───────────────────────────────────────────────────────────

class EventProcessor:
    """
    Stateful processor: accumulates UserSignals and produces rich episode text.

    Instantiate once per service lifetime.
    Call .process(event) → returns the episode string to send to Graphiti.
    Call .process_legacy(...) → for old-style flat description events.
    """

    def __init__(self):
        self._signals: dict[str, UserSignals] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def process(self, event: RichUserEvent) -> str:
        """Update UserSignals and return a rich episode string for Graphiti."""
        s = self._get_or_create(event.user_id)
        self._update_recency(s, event.timestamp)
        return self._dispatch(s, event)

    def process_legacy(self, user_id: str, event_type: str, description: str, timestamp: str) -> str:
        """Wrap a legacy flat-description event into an episode string."""
        s = self._get_or_create(user_id)
        self._update_recency(s, timestamp)
        try:
            ts = datetime.fromisoformat(timestamp)
        except Exception:
            ts = datetime.now(timezone.utc)
        return f"[{ts:%Y-%m-%d %H:%M}] {user_id} performed {event_type}: {description}"

    def get_signals(self, user_id: str) -> dict | None:
        s = self._signals.get(user_id)
        return s.to_dict() if s else None

    def get_all_signals(self) -> dict[str, dict]:
        return {uid: s.to_dict() for uid, s in self._signals.items()}

    def get_user_ids(self) -> list[str]:
        return list(self._signals.keys())

    # ── Internals ─────────────────────────────────────────────────────────

    def _get_or_create(self, user_id: str) -> UserSignals:
        if user_id not in self._signals:
            self._signals[user_id] = UserSignals(user_id)
        return self._signals[user_id]

    def _update_recency(self, s: UserSignals, timestamp: str) -> None:
        try:
            ts = datetime.fromisoformat(timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if s.first_seen is None or ts < s.first_seen:
                s.first_seen = ts
            if s.last_seen is None or ts > s.last_seen:
                s.last_seen = ts
        except Exception:
            pass

    def _dispatch(self, s: UserSignals, event: RichUserEvent) -> str:
        p = event.properties
        try:
            ts = datetime.fromisoformat(event.timestamp)
        except Exception:
            ts = datetime.now(timezone.utc)

        handlers = {
            "purchase":             self._purchase,
            "add_to_cart":          self._cart,
            "page_view":            self._page_view,
            "search":               self._search,
            "feedback":             self._feedback,
            "support_ticket":       self._support,
            "session_end":          self._session,
            "login":                self._login,
            "feature_usage":        self._feature,
            "referral":             self._referral,
            "profile_update":       self._profile,
            "subscription_change":  self._subscription,
        }
        handler = handlers.get(event.event_type.lower(), self._generic)
        return handler(s, event, p, ts)

    # ── Event handlers ────────────────────────────────────────────────────

    def _purchase(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        item = p.get("item_name", p.get("item", "unknown item"))
        price = float(p.get("price_usd", p.get("price", 0)))
        category = p.get("category", "general")
        qty = int(p.get("quantity", 1))

        s.purchase_count += 1
        s.total_spend += price * qty
        s.purchase_categories[category] += 1

        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} completed purchase #{s.purchase_count}: "
            f"bought {qty}x '{item}' ({category}) for ${price:.2f}. "
            f"Lifetime spend: ${s.total_spend:.2f} across {s.purchase_count} orders. "
            f"Top category: {s.top_category} ({s.purchase_categories[s.top_category]} orders). "
            f"Avg order value: ${s.avg_order_value:.2f}."
        )

    def _cart(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        item = p.get("item_name", p.get("item", "unknown"))
        price = float(p.get("price_usd", p.get("price", 0)))
        category = p.get("category", "general")

        s.cart_additions += 1
        intent = (
            " High browse-to-purchase intent (many cart additions vs purchases)."
            if s.cart_additions > s.purchase_count * 2 and s.purchase_count > 0
            else ""
        )
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} added '{item}' ({category}, ${price:.2f}) to cart "
            f"(cart addition #{s.cart_additions}).{intent}"
        )

    def _page_view(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        url = p.get("url", p.get("page", "/unknown"))
        duration = int(p.get("duration_seconds", 0))
        referrer = p.get("referrer", "")

        s.pages_viewed += 1
        parts = [
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} viewed '{url}' for {duration}s.",
            f"Total pages viewed: {s.pages_viewed}.",
        ]
        if referrer:
            parts.append(f"Referred from: {referrer}.")
        if any(x in url for x in ("/pricing", "/checkout", "/upgrade")):
            parts.append("High-intent page visit (pricing/checkout/upgrade).")
        if any(x in url for x in ("/help", "/cancel", "/unsubscribe")):
            parts.append("Support or cancellation page — possible churn signal.")
        return " ".join(parts)

    def _search(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        query = p.get("query", p.get("q", ""))
        results = p.get("results_count")

        s.search_queries.append(query)
        churn_terms = {"cancel", "refund", "alternative", "competitor", "vs "}
        intent = "churn-signal query" if any(t in query.lower() for t in churn_terms) else "exploratory search"
        results_str = f" Results: {results}." if results is not None else ""
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} searched '{query}' ({intent}).{results_str} "
            f"Total searches: {len(s.search_queries)}."
        )

    def _feedback(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        text = p.get("text", p.get("feedback", ""))
        rating = p.get("rating")
        feature = p.get("feature", "general product")

        neg = {"bad","terrible","hate","awful","broken","slow","expensive","frustrat",
               "disappoint","worst","confus","cancel","useless","buggy","crash"}
        pos = {"great","love","amazing","excellent","perfect","fast","helpful",
               "smooth","intuitive","recommend","awesome","brilliant","fantastic"}
        tl = text.lower()
        is_neg = any(w in tl for w in neg)
        is_pos = any(w in tl for w in pos)

        if is_neg and not is_pos:
            s.negative_feedback += 1
            sentiment = "negative"
        elif is_pos and not is_neg:
            s.positive_feedback += 1
            sentiment = "positive"
        else:
            sentiment = "neutral"

        if rating:
            r = int(rating)
            s.ratings.append(r)
            if r <= 2:
                s.negative_feedback += 1
            elif r >= 4:
                s.positive_feedback += 1

        rating_str = f" Rating: {rating}/5." if rating else ""
        avg_str = f" Running avg: {s.avg_rating}/5." if s.avg_rating else ""
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} submitted {sentiment} feedback about '{feature}':{rating_str} "
            f"\"{text[:250]}\".{avg_str} "
            f"Feedback totals: {s.positive_feedback} positive, {s.negative_feedback} negative "
            f"(overall sentiment: {s.sentiment_ratio})."
        )

    def _support(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        issue = p.get("issue", p.get("description", "unspecified"))
        priority = p.get("priority", "normal")
        category = p.get("category", "general")

        s.support_tickets += 1
        s.support_categories[category] += 1
        churn_flag = " CHURN RISK: 3+ support tickets." if s.support_tickets >= 3 else ""
        top_cat = s.support_categories.most_common(1)[0][0]
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} opened support ticket #{s.support_tickets} "
            f"({priority} priority, category: {category}): '{issue}'.{churn_flag} "
            f"Top support category: '{top_cat}'."
        )

    def _session(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        minutes = int(p.get("duration_minutes", p.get("minutes", 0)))
        pages = int(p.get("pages_viewed", p.get("pages", 0)))
        device = p.get("device", "unknown")

        s.session_count += 1
        s.total_session_minutes += minutes
        s.pages_viewed += pages

        engagement = "high" if minutes > 30 else "medium" if minutes > 10 else "low"
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} ended session #{s.session_count} "
            f"on {device}: {minutes} min, {pages} pages ({engagement} engagement). "
            f"Cumulative: {s.total_session_minutes} total minutes, {s.session_count} sessions "
            f"(avg {s.avg_session_minutes} min/session)."
        )

    def _login(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        device = p.get("device", "unknown")
        country = p.get("country", "")

        s.login_count += 1
        freq = "frequent" if s.login_count > 20 else "regular" if s.login_count > 5 else "occasional"
        loc_str = f" from {country}" if country else ""
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} logged in{loc_str} on {device} "
            f"(login #{s.login_count}, {freq} user)."
        )

    def _feature(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        feature = p.get("feature_name", p.get("feature", "unknown"))
        duration = p.get("duration_seconds")

        s.features_used[feature] += 1
        total_uses = s.features_used[feature]
        top = s.features_used.most_common(1)[0]
        dur_str = f" for {duration}s" if duration else ""
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} used feature '{feature}'{dur_str} "
            f"({total_uses} total uses). "
            f"Distinct features explored: {len(s.features_used)}. "
            f"Most-used feature: '{top[0]}' ({top[1]} uses)."
        )

    def _referral(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        channel = p.get("channel", "email")
        referred = p.get("referred_user_id", "")
        ref_str = f" Referred user ID: {referred}." if referred else ""
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} referred a new user via {channel} channel.{ref_str} "
            f"Indicates high brand advocacy and community orientation."
        )

    def _profile(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        if "age" in p:
            s.age = int(p["age"])
        if "occupation" in p:
            s.occupation = str(p["occupation"])
        if "location" in p:
            s.location = str(p["location"])
        if "interests" in p:
            s.interests = list(p["interests"])

        parts = [f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} updated profile:"]
        if s.age:
            parts.append(f"age {s.age}")
        if s.occupation:
            parts.append(f"occupation '{s.occupation}'")
        if s.location:
            parts.append(f"location '{s.location}'")
        if s.interests:
            parts.append(f"interests [{', '.join(s.interests)}]")
        return " ".join(parts) + "."

    def _subscription(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        from_tier = p.get("from_tier", "unknown")
        to_tier = p.get("to_tier", "unknown")
        reason = p.get("reason", "")

        s.subscription_tier = to_tier
        tier_ranks = {"free": 0, "basic": 1, "standard": 1, "premium": 2, "enterprise": 3}
        direction = (
            "upgrade"
            if tier_ranks.get(to_tier.lower(), 0) > tier_ranks.get(from_tier.lower(), 0)
            else "downgrade"
        )
        reason_str = f" Reason: '{reason}'." if reason else ""
        signal = " CHURN RISK: subscription downgrade." if direction == "downgrade" else " Positive revenue event."
        return (
            f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} changed subscription: "
            f"{from_tier} → {to_tier} ({direction}).{reason_str}{signal}"
        )

    def _generic(self, s: UserSignals, e: RichUserEvent, p: dict, ts: datetime) -> str:
        props_str = ", ".join(f"{k}={v}" for k, v in p.items()) if p else "no additional data"
        return f"[{ts:%Y-%m-%d %H:%M}] {e.user_id} performed '{e.event_type}': {props_str}."
