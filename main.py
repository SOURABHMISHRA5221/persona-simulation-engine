#!/usr/bin/env python3
"""
main.py — CLI entry point for the voting/opinion simulation.

Usage examples:
  # Ollama (default)
  python main.py --campaign "We are increasing prices by 20%" --agents 10

  # Gemini 2.5 Flash (requires GEMINI_API_KEY env var)
  python main.py --provider gemini --campaign "We are removing the free tier" --agents 20

  # Interactive mode
  python main.py

  # With export
  python main.py --campaign "New dark mode" --agents 50 --export results.json

  # Load from campaigns.json
  python main.py --campaign-id campaign_002 --agents 20
"""

import argparse
import asyncio
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.simulation import Simulation


# ── Campaign helpers ──────────────────────────────────────────────────────────

def load_campaign_by_id(campaign_id: str, campaigns_path: str = "data/campaigns.json") -> tuple[str, str]:
    path = Path(campaigns_path)
    if not path.exists():
        print(f"[ERROR] campaigns.json not found at {path}")
        sys.exit(1)
    with open(path) as f:
        campaigns = json.load(f)
    for c in campaigns:
        if c["id"] == campaign_id:
            return c["title"], c["description"]
    print(f"[ERROR] Campaign ID '{campaign_id}' not found in {campaigns_path}")
    print("Available IDs:", [c["id"] for c in campaigns])
    sys.exit(1)


def list_campaigns(campaigns_path: str = "data/campaigns.json") -> None:
    path = Path(campaigns_path)
    if not path.exists():
        print("No campaigns.json found.")
        return
    with open(path) as f:
        campaigns = json.load(f)
    print("\nAvailable sample campaigns:")
    print("-" * 50)
    for c in campaigns:
        print(f"  [{c['id']}]  {c['title']}")
        print(f"    {c['description'][:80]}...")
    print()


# ── Interactive prompt ────────────────────────────────────────────────────────

def prompt_campaign() -> tuple[str, str]:
    print("\n" + "=" * 60)
    print("  OASIS-LITE: User Opinion Simulation System")
    print("=" * 60)
    print("  No campaign specified. Enter one interactively.\n")
    list_campaigns()
    print("  Or enter your own campaign description below.")
    print("  (Press Enter twice when done)\n")

    title = input("  Campaign title: ").strip() or "Untitled Campaign"
    print("  Description (press Enter twice to finish):")

    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    description = "\n".join(lines).strip() or title

    return title, description


# ── Arg parsing ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simulation",
        description="Run a user opinion simulation on a proposed campaign.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # Campaign
    camp = parser.add_mutually_exclusive_group()
    camp.add_argument(
        "--campaign", "-c",
        metavar="TEXT",
        help="Campaign description text (use quotes for multi-word strings)",
    )
    camp.add_argument(
        "--campaign-id",
        metavar="ID",
        help="Load a predefined campaign from data/campaigns.json by ID",
    )
    camp.add_argument(
        "--list-campaigns",
        action="store_true",
        help="List available sample campaigns and exit",
    )

    # Simulation params
    parser.add_argument(
        "--agents", "-n",
        type=int,
        default=10,
        help="Number of agents to simulate (default: 10, max: 1000)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Number of simulated hours (default: 24)",
    )
    parser.add_argument(
        "--start-hour",
        type=int,
        default=8,
        help="Starting hour of simulation (0-23, default: 8)",
    )
    parser.add_argument(
        "--profiles",
        default="data/user_profiles.json",
        help="Path to user profiles JSON (default: data/user_profiles.json)",
    )

    # Provider
    parser.add_argument(
        "--provider",
        choices=["ollama", "gemini"],
        default="ollama",
        help="LLM provider: 'ollama' (local) or 'gemini' (Google API). Default: ollama",
    )

    # Ollama options
    parser.add_argument(
        "--model",
        default="qwen3:4b",
        help="Ollama model name (default: qwen3:4b, only used with --provider ollama)",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama base URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--ollama-cloud",
        action="store_true",
        help="Use Ollama cloud endpoint (https://ollama.com). Overrides --ollama-url and requires OLLAMA_API_KEY env var.",
    )

    # Gemini options
    parser.add_argument(
        "--gemini-model",
        default="gemini-2.5-flash",
        help="Gemini model name (default: gemini-2.5-flash)",
    )

    # Output
    parser.add_argument(
        "--export",
        metavar="PATH",
        help="Export full results to JSON file",
    )
    parser.add_argument(
        "--actions",
        metavar="PATH",
        default=None,
        help=(
            "Path to a custom action set JSON file (default: data/actions/vote.json). "
            "Examples: data/actions/ecommerce.json, data/actions/social.json"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--no-ai-summary",
        action="store_true",
        default=False,
        help="Skip the LLM-generated executive narrative summary at the end",
    )
    parser.add_argument(
        "--title",
        metavar="TITLE",
        help="Short title for the campaign (used in summary output)",
    )

    return parser


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Handle --list-campaigns
    if args.list_campaigns:
        list_campaigns()
        return

    # Resolve campaign
    if args.campaign_id:
        title, description = load_campaign_by_id(args.campaign_id)
    elif args.campaign:
        title = args.title or "Custom Campaign"
        description = args.campaign
    else:
        # Interactive
        title, description = prompt_campaign()

    # Clamp agents
    agents = max(1, min(args.agents, 1000))
    if agents != args.agents:
        print(f"[INFO] Clamped agent count to {agents}")

    # Resolve Ollama URL and Model for cloud
    ollama_url = "https://ollama.com" if args.ollama_cloud else args.ollama_url
    ollama_model = "gpt-oss:120b" if args.ollama_cloud and args.model == "qwen3:4b" else args.model

    # Build + run simulation
    sim = Simulation(
        campaign_title=title,
        campaign_description=description,
        profiles_path=args.profiles,
        max_agents=agents,
        num_hours=args.hours,
        start_hour=args.start_hour,
        seed=args.seed,
        provider=args.provider,
        ollama_model=ollama_model,
        ollama_url=ollama_url,
        gemini_model=args.gemini_model,
        export_path=args.export,
        actions_path=args.actions,
        ai_summary=not args.no_ai_summary,
    )

    # Health check first
    provider_label = (
        f"Gemini ({args.gemini_model})"
        if args.provider == "gemini"
        else f"Ollama ({ollama_url}, model: {ollama_model})"
    )
    print(f"\n🔍 Checking {provider_label}...")
    ok = await sim.check_model()
    if not ok:
        sys.exit(1)
    print(f"✅ {args.provider.capitalize()} is ready.")

    sim.setup()
    await sim.run()


if __name__ == "__main__":
    asyncio.run(main())
