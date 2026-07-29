"""
demo_match.py — proves the matching engine end-to-end with the seed data,
no network required. Run: python demo_match.py

This is the exact logic the web app runs, just printed to the terminal so you
can verify the scoring is sane before trusting the UI.
"""

from __future__ import annotations

import json
import os
from datetime import date

from match import Profile, rank

SEED = os.path.join(os.path.dirname(__file__), "..", "data", "seed_grants.json")
# Fixed "today" so the demo is reproducible regardless of when you run it.
TODAY = date(2026, 7, 15)


def main() -> None:
    with open(SEED, encoding="utf-8") as fh:
        grants = json.load(fh)["grants"]

    # Example user: a California clean-energy startup.
    profile = Profile(state="CA", entity_type="startup",
                      use_cases=["clean_energy", "rd_innovation", "solar"])

    ranked = rank(grants, profile, today=TODAY)
    eligible = [g for g in ranked if g["eligible"]]

    print(f"Profile: {profile.entity_type} in {profile.state}, "
          f"interested in {', '.join(profile.use_cases)}")
    print(f"Scanned {len(grants)} grants -> {len(eligible)} you can apply for.\n")

    for g in ranked:
        tag = "OK " if g["eligible"] else "-- "
        dl = f"{g['days_left']}d" if g["days_left"] is not None else "  "
        print(f"{tag}[{g['match_score']:3d}] {dl:>4}  {g['title'][:58]}")
        for r in g["match_reasons"]:
            print(f"        + {r}")
        for d in g["match_disqualifiers"]:
            print(f"        x {d}")
    print()


if __name__ == "__main__":
    main()
