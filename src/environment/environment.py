"""
Environment server — tracks all simulation state: agents, votes, opinions.
Actions are now fully data-driven via an action set JSON (see data/actions/).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime


DEFAULT_ACTION_SET = {
    "action_set_id": "vote",
    "description": "Standard approval voting",
    "primary_action_label": "ACTION",
    "actions": [
        {"id": "LIKE",    "label": "Like",    "emoji": "👍", "sentiment": "positive"},
        {"id": "DISLIKE", "label": "Dislike", "emoji": "👎", "sentiment": "negative"},
        {"id": "ABSTAIN", "label": "Abstain", "emoji": "😐", "sentiment": "neutral"},
    ],
    "approval_actions": ["LIKE"],
    "verdict_thresholds": {"strong_approval": 70, "mixed": 50, "majority_opposition": 30},
}


@dataclass
class ActionRecord:
    agent_id: str
    username: str
    action: str          # the action ID (e.g. "LIKE", "PURCHASE", "SHARE")
    opinion: str
    persona_summary: str
    timestamp: int       # simulation step


@dataclass
class Environment:
    """Central state store for the simulation."""

    campaign_title: str = ""
    campaign_description: str = ""
    current_step: int = 0
    current_hour: int = 0
    action_set: dict = field(default_factory=lambda: DEFAULT_ACTION_SET)

    _agents: dict[str, dict] = field(default_factory=dict)
    _records: list[ActionRecord] = field(default_factory=list)
    _acted_agents: set[str] = field(default_factory=set)

    # ------------------------------------------------------------------ #
    # Setup                                                                #
    # ------------------------------------------------------------------ #

    def set_campaign(self, title: str, description: str) -> None:
        self.campaign_title = title
        self.campaign_description = description

    def register_agent(self, profile: dict) -> None:
        uid = profile["user_id"]
        self._agents[uid] = profile

    # ------------------------------------------------------------------ #
    # Action recording (was: voting)                                       #
    # ------------------------------------------------------------------ #

    def record_vote(
        self,
        agent_id: str,
        vote: str,
        opinion: str,
        persona_summary: str,
    ) -> None:
        """Record an action. Each agent may only act once."""
        if agent_id in self._acted_agents:
            return
        self._acted_agents.add(agent_id)
        username = self._agents.get(agent_id, {}).get("username", agent_id)
        self._records.append(
            ActionRecord(
                agent_id=agent_id,
                username=username,
                action=vote,
                opinion=opinion,
                persona_summary=persona_summary,
                timestamp=self.current_step,
            )
        )

    def has_voted(self, agent_id: str) -> bool:
        return agent_id in self._acted_agents

    # ------------------------------------------------------------------ #
    # Aggregation                                                          #
    # ------------------------------------------------------------------ #

    def _action_meta(self) -> dict[str, dict]:
        """Map action id → metadata dict."""
        return {a["id"]: a for a in self.action_set.get("actions", [])}

    def get_results(self) -> dict:
        meta = self._action_meta()
        approval_ids = set(self.action_set.get("approval_actions", ["LIKE"]))
        total = len(self._records)

        # Count per action ID
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.action] = counts.get(r.action, 0) + 1

        # Group by sentiment
        by_sentiment: dict[str, list[ActionRecord]] = {
            "positive": [], "negative": [], "neutral": []
        }
        for r in self._records:
            sentiment = meta.get(r.action, {}).get("sentiment", "neutral")
            by_sentiment[sentiment].append(r)

        approval_count = sum(counts.get(aid, 0) for aid in approval_ids)
        approval_rate = round(approval_count / total * 100, 1) if total else 0.0

        return {
            "total_votes": total,
            "counts": counts,
            "by_sentiment": by_sentiment,
            "approval_count": approval_count,
            "approval_rate": approval_rate,
            "all_votes": self._records,
        }

    # ------------------------------------------------------------------ #
    # CLI Output                                                           #
    # ------------------------------------------------------------------ #

    def print_summary(self, verbose: bool = True) -> None:
        r = self.get_results()
        meta = self._action_meta()
        thresholds = self.action_set.get("verdict_thresholds", {})
        width = 60

        print("\n" + "=" * width)
        print("  SIMULATION RESULTS")
        print("=" * width)
        print(f"  Campaign : {self.campaign_title}")
        print(f"  Ran at   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * width)

        # Action tally — dynamic rows
        print(f"\n  ACTION TALLY  (total agents acted: {r['total_votes']})")
        for action in self.action_set.get("actions", []):
            aid = action["id"]
            emoji = action.get("emoji", "  ")
            label = action.get("label", aid)
            count = r["counts"].get(aid, 0)
            pct = self._pct(count, r["total_votes"])
            print(f"  {emoji} {label:<12}: {count:>4}  ({pct}%)")

        print(f"\n  ✅ Approval rate : {r['approval_rate']}%")
        approval_ids = ", ".join(self.action_set.get("approval_actions", ["LIKE"]))
        print(f"     (counts: {approval_ids})")

        # Verdict
        print("\n" + "-" * width)
        ap = r["approval_rate"]
        if ap >= thresholds.get("strong_approval", 70):
            verdict = "🟢 STRONG APPROVAL — Users are likely to welcome this change."
        elif ap >= thresholds.get("mixed", 50):
            verdict = "🟡 MIXED RECEPTION — Significant opposition, consider adjustments."
        elif ap >= thresholds.get("majority_opposition", 30):
            verdict = "🟠 MAJORITY OPPOSITION — Most users would react negatively."
        else:
            verdict = "🔴 STRONG REJECTION — This change is likely to cause backlash."
        print(f"  Verdict: {verdict}")

        if verbose and r["total_votes"] > 0:
            print("\n" + "-" * width)
            print("  SAMPLE OPINIONS")

            # Show samples grouped by sentiment
            positives = r["by_sentiment"]["positive"][:3]
            negatives = r["by_sentiment"]["negative"][:3]

            if positives:
                sample_action = meta.get(positives[0].action, {})
                emoji = sample_action.get("emoji", "👍")
                label = sample_action.get("label", positives[0].action)
                print(f"\n  {emoji} Why users chose {label.upper()} (or similar):")
                for rec in positives:
                    a_meta = meta.get(rec.action, {})
                    print(f"\n  [{rec.username} | {rec.persona_summary}]")
                    print(f"  Action: {a_meta.get('emoji','')} {rec.action}")
                    print(f"  \"{rec.opinion}\"")

            if negatives:
                sample_action = meta.get(negatives[0].action, {})
                emoji = sample_action.get("emoji", "👎")
                label = sample_action.get("label", negatives[0].action)
                print(f"\n  {emoji} Why users chose {label.upper()} (or similar):")
                for rec in negatives:
                    a_meta = meta.get(rec.action, {})
                    print(f"\n  [{rec.username} | {rec.persona_summary}]")
                    print(f"  Action: {a_meta.get('emoji','')} {rec.action}")
                    print(f"  \"{rec.opinion}\"")

            self._print_tier_breakdown(r["all_votes"])

        print("\n" + "=" * width + "\n")

    def _print_tier_breakdown(self, records: list[ActionRecord]) -> None:
        action_ids = [a["id"] for a in self.action_set.get("actions", [])]
        tiers: dict[str, dict[str, int]] = {}

        for rec in records:
            profile = self._agents.get(rec.agent_id, {})
            tier = profile.get("persona", {}).get("behavior", {}).get("subscription_tier", "unknown")
            if tier not in tiers:
                tiers[tier] = {aid: 0 for aid in action_ids}
            tiers[tier][rec.action] = tiers[tier].get(rec.action, 0) + 1

        if tiers:
            col_w = 8
            header = f"  {'Tier':<12}" + "".join(f"{aid:>{col_w}}" for aid in action_ids)
            print("\n  BREAKDOWN BY SUBSCRIPTION TIER")
            print(header)
            print("  " + "-" * (12 + col_w * len(action_ids)))
            for tier, counts in sorted(tiers.items()):
                row = f"  {tier:<12}" + "".join(f"{counts.get(aid,0):>{col_w}}" for aid in action_ids)
                print(row)

    @staticmethod
    def _pct(part: int, total: int) -> str:
        if total == 0:
            return "0.0"
        return f"{part / total * 100:.1f}"

    def get_llm_context(self, max_opinions: int = 6) -> str:
        """Return a condensed text summary of results for feeding into an LLM."""
        r = self.get_results()
        meta = self._action_meta()
        approval_ids = set(self.action_set.get("approval_actions", ["LIKE"]))

        lines = [
            f"CAMPAIGN: {self.campaign_title}",
            f"DESCRIPTION: {self.campaign_description}",
            "",
            "ACTION RESULTS:",
        ]
        total = r["total_votes"]
        for action in self.action_set.get("actions", []):
            aid = action["id"]
            count = r["counts"].get(aid, 0)
            pct = f"{count/total*100:.1f}%" if total else "0%"
            lines.append(f"  {aid}: {count} ({pct})")
        lines.append(f"  Approval rate: {r['approval_rate']}% (actions counted: {', '.join(approval_ids)})")

        # Sample opinions grouped by sentiment
        positives = r["by_sentiment"]["positive"][:max_opinions // 2]
        negatives = r["by_sentiment"]["negative"][:max_opinions // 2]

        if positives:
            lines.append("\nPOSITIVE REACTIONS:")
            for rec in positives:
                profile = self._agents.get(rec.agent_id, {})
                p = profile.get("persona", {})
                occ = p.get("occupation", "?")
                tier = p.get("behavior", {}).get("subscription_tier", "?")
                lines.append(f"  [{occ}, {tier} tier, action={rec.action}]: \"{rec.opinion[:200]}\"")

        if negatives:
            lines.append("\nNEGATIVE REACTIONS:")
            for rec in negatives:
                profile = self._agents.get(rec.agent_id, {})
                p = profile.get("persona", {})
                occ = p.get("occupation", "?")
                tier = p.get("behavior", {}).get("subscription_tier", "?")
                lines.append(f"  [{occ}, {tier} tier, action={rec.action}]: \"{rec.opinion[:200]}\"")

        # Tier breakdown
        action_ids = [a["id"] for a in self.action_set.get("actions", [])]
        tiers: dict[str, dict[str, int]] = {}
        for rec in r["all_votes"]:
            profile = self._agents.get(rec.agent_id, {})
            tier = profile.get("persona", {}).get("behavior", {}).get("subscription_tier", "unknown")
            if tier not in tiers:
                tiers[tier] = {aid: 0 for aid in action_ids}
            tiers[tier][rec.action] = tiers[tier].get(rec.action, 0) + 1

        if tiers:
            lines.append("\nTIER BREAKDOWN:")
            for tier, counts in sorted(tiers.items()):
                breakdown = ", ".join(f"{aid}={counts.get(aid,0)}" for aid in action_ids)
                lines.append(f"  {tier}: {breakdown}")

        return "\n".join(lines)

    def export_json(self, path: str) -> None:
        """Dump full results to a JSON file for further analysis."""
        r = self.get_results()
        export = {
            "campaign_title": self.campaign_title,
            "campaign_description": self.campaign_description,
            "action_set_id": self.action_set.get("action_set_id", "unknown"),
            "summary": {
                "total_votes": r["total_votes"],
                "counts": r["counts"],
                "approval_rate": r["approval_rate"],
            },
            "votes": [
                {
                    "agent_id": rec.agent_id,
                    "username": rec.username,
                    "action": rec.action,
                    "opinion": rec.opinion,
                    "persona_summary": rec.persona_summary,
                    "step": rec.timestamp,
                }
                for rec in r["all_votes"]
            ],
        }
        with open(path, "w") as f:
            json.dump(export, f, indent=2)
        print(f"  Results exported → {path}")
