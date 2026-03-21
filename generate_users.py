"""
generate_users.py — LLM-powered user profile generator.

Uses Ollama (qwen3.5:9b by default) to create diverse, non-repeating user
personas and appends them to data/user_profiles.json.

Usage:
    # Generate 10 users, auto-avoiding existing archetypes
    python3 generate_users.py --count 10

    # Generate 5 users of a specific archetype type
    python3 generate_users.py --count 5 --type "night-life, creative, low-income"

    # Change model or batch size
    python3 generate_users.py --count 15 --batch-size 3 --model qwen3.5:9b
"""

import argparse
import asyncio
import json
import random
import re
import sys
import httpx


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_profiles(path: str) -> list[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_profiles(path: str, profiles: list[dict]) -> None:
    with open(path, "w") as f:
        json.dump(profiles, f, indent=2)


def get_existing_summary(profiles: list[dict]) -> str:
    """Return a human-readable list of existing occupations + archetypes."""
    if not profiles:
        return "(none yet)"
    lines = []
    for p in profiles:
        occ = p.get("persona", {}).get("occupation", "Unknown")
        username = p.get("username", "?")
        tier = p.get("persona", {}).get("behavior", {}).get("subscription_tier", "?")
        lines.append(f"  - {username} ({occ}, {tier} tier)")
    return "\n".join(lines)


def generate_hourly_activity(occupation: str) -> list[float]:
    """Generate a 24-element activity curve based on occupation keywords."""
    occ = occupation.lower()
    if any(w in occ for w in ["gamer", "streamer", "dj", "bartender", "night"]):
        peak = list(range(20, 24)) + list(range(0, 4))
    elif any(w in occ for w in ["farmer", "retiree", "retired", "early"]):
        peak = list(range(5, 10))
    elif any(w in occ for w in ["student", "artist", "creator", "freelance", "crypto"]):
        peak = list(range(14, 24))  # afternoon-evening
    elif any(w in occ for w in ["executive", "manager", "director", "lawyer", "ceo"]):
        peak = list(range(7, 12)) + list(range(13, 17))  # business hours
    else:
        peak = list(range(18, 23))  # default evening peak

    activity = []
    for h in range(24):
        if h in peak:
            activity.append(round(random.uniform(0.14, 0.22), 3))
        elif any(abs(h - p) <= 2 or abs(h + 24 - p) <= 2 for p in peak):
            activity.append(round(random.uniform(0.06, 0.13), 3))
        else:
            activity.append(round(random.uniform(0.01, 0.04), 3))

    return activity


def build_prompt(
    count: int,
    start_id: int,
    existing_summary: str,
    archetype_hint: str,
) -> str:
    archetype_section = (
        f"\nFocus specifically on these archetypes / demographics: {archetype_hint}\n"
        if archetype_hint
        else "\nChoose a wide variety of archetypes not listed above (diverse age, income, culture, tech level).\n"
    )

    return f"""You are an expert synthetic user persona generator for a digital platform simulation.

EXISTING USERS (DO NOT REPEAT THESE ARCHETYPES OR OCCUPATIONS):
{existing_summary}
{archetype_section}
Generate exactly {count} NEW user personas, starting at user_id "user_{start_id:03d}" and incrementing.

Each persona must be a JSON object with this EXACT schema:
{{
  "user_id": "user_{start_id:03d}",
  "username": "firstnamedescriptor",
  "persona": {{
    "age": <integer 18-80>,
    "occupation": "<specific job title>",
    "location": "<City, Country>",
    "interests": ["<interest1>", "<interest2>", "<interest3>"],
    "values": ["<value1>", "<value2>", "<value3>"],
    "traits": {{
      "price_sensitivity": <0.0-1.0>,
      "tech_savviness": <0.0-1.0>,
      "brand_loyalty": <0.0-1.0>,
      "optimism": <0.0-1.0>,
      "skepticism": <0.0-1.0>,
      "community_orientation": <0.0-1.0>
    }},
    "behavior": {{
      "avg_session_minutes": <int 3-90>,
      "actions_per_session": <int 1-30>,
      "engagement_rate": <0.0-1.0>,
      "subscription_tier": <"free"|"basic"|"premium">,
      "account_age_months": <int 1-72>
    }},
    "past_opinions": [
      "<1 authentic sentence about the platform from their POV>",
      "<1 more authentic sentence showing their personality>"
    ]
  }}
}}

RULES:
- Make traits consistent with the occupation and values (e.g. farmers: low tech_savviness; hackers: high skepticism)
- Use diverse global locations (not just the USA)
- Distribute subscription_tier realistically (≈50% free, 30% basic, 20% premium across the batch)
- DO NOT add an "hourly_activity" field (the script adds it)
- Return ONLY a valid JSON array of {count} objects. No markdown, no commentary.
"""


async def call_ollama(
    prompt: str,
    model: str,
    base_url: str,
    num_predict: int,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.9,
            "num_predict": num_predict,
        },
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(f"{base_url}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


def try_parse_json(raw: str) -> list[dict] | None:
    """Try to parse JSON with multi-layer repair heuristics.
    
    Handles:
    - Markdown code block wrappers
    - Missing closing bracket (])
    - Mid-string / mid-object truncation (most common with LLMs)
    """
    # Strip markdown wrappers
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Attempt 1: parse as-is
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, list) else None
    except json.JSONDecodeError:
        pass

    # Attempt 2: append closing bracket
    for suffix in ["]", "}]", "}}", "}}"]:
        try:
            result = json.loads(cleaned + suffix)
            if isinstance(result, list):
                print("  [REPAIR] Recovered with suffix.", flush=True)
                return result
        except Exception:
            pass

    # Attempt 3: truncation recovery — find the last COMPLETE top-level object.
    # Walk backwards through } chars and try to close the array at each one.
    depth = 0
    last_valid_end = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(cleaned):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:  # closed a top-level object inside the array
                last_valid_end = i

    if last_valid_end > 0:
        salvaged = cleaned[:last_valid_end + 1] + "]"
        # Ensure it starts with [
        if not salvaged.strip().startswith("["):
            salvaged = "[" + salvaged
        try:
            result = json.loads(salvaged)
            if isinstance(result, list) and len(result) > 0:
                print(
                    f"  [REPAIR] Salvaged {len(result)} complete object(s) from truncated response.",
                    flush=True,
                )
                return result
        except Exception:
            pass

    return None


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic user profiles using an Ollama LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Total number of NEW users to generate (default: 10)",
    )
    parser.add_argument(
        "--type", "-t",
        dest="archetype",
        default="",
        help=(
            "Comma-separated archetype hints so the LLM focuses on specific demographics. "
            "E.g. 'rural farmer, elderly retiree, crypto enthusiast'"
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Profiles to request per LLM call (default: 5, keep ≤5 for reliability)",
    )
    parser.add_argument(
        "--model",
        default="qwen3.5:9b",
        help="Ollama model to use (default: qwen3.5:9b)",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama base URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--profiles",
        default="data/user_profiles.json",
        help="Path to user_profiles.json (default: data/user_profiles.json)",
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=8192,
        help="Max tokens per LLM call (default: 8192)",
    )
    args = parser.parse_args()

    profiles = load_profiles(args.profiles)
    print(f"📂 Loaded {len(profiles)} existing profiles from {args.profiles}")

    existing_summary = get_existing_summary(profiles)

    total_to_add = args.count
    batch_size = min(args.batch_size, total_to_add)
    total_added = 0
    batch_num = 0

    while total_added < total_to_add:
        batch_num += 1
        remaining = total_to_add - total_added
        this_batch = min(batch_size, remaining)

        next_id = len(profiles) + 1
        print(
            f"\n🤖 Batch {batch_num}: requesting {this_batch} personas "
            f"(IDs user_{next_id:03d}–user_{next_id + this_batch - 1:03d})...",
            flush=True,
        )

        prompt = build_prompt(
            count=this_batch,
            start_id=next_id,
            existing_summary=existing_summary,
            archetype_hint=args.archetype,
        )

        try:
            raw = await call_ollama(prompt, args.model, args.ollama_url, args.num_predict)
        except Exception as e:
            print(f"  [ERROR] Ollama call failed: {e}")
            break

        new_profiles = try_parse_json(raw)

        if new_profiles is None:
            print(f"  [ERROR] Could not parse JSON for batch {batch_num}. Skipping.")
            print(f"  Raw response (first 500 chars): {raw[:500]}")
            continue

        # Reassign IDs sequentially and inject hourly_activity
        added_this_batch = 0
        for p in new_profiles:
            uid = len(profiles) + 1
            p["user_id"] = f"user_{uid:03d}"
            occ = p.get("persona", {}).get("occupation", "")
            p["persona"]["hourly_activity"] = generate_hourly_activity(occ)
            profiles.append(p)
            added_this_batch += 1
            total_added += 1

            # Update summary to avoid repeats in next batch
            existing_summary = get_existing_summary(profiles)

        save_profiles(args.profiles, profiles)
        print(f"  ✅ Added {added_this_batch} profiles. Total: {len(profiles)}")

    print(f"\n🎉 Done! Added {total_added} new profiles. Total in file: {len(profiles)}")


if __name__ == "__main__":
    asyncio.run(main())
