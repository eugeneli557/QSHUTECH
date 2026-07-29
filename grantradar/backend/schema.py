"""
schema.py — the one data model every layer normalizes into.

Federal API records (fetch_federal.py) and state/local scraped records
(scrape_state.py) both become a `Grant`, so matching, dedup, and the frontend
never care where a record came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


# Controlled vocabularies used by the eligibility matcher. Keeping them small
# and explicit is what makes rule-based matching reliable and AI extraction
# consistent (the extractor is told to map free text onto these tokens).
ENTITY_TYPES = [
    "small_business", "nonprofit", "individual", "local_government",
    "tribal", "research_institution", "farmer", "startup",
]

USE_CASES = [
    "clean_energy", "energy_efficiency", "ev_charging", "solar",
    "hiring_training", "rd_innovation", "export_trade", "disaster_recovery",
    "broadband", "agriculture", "housing", "arts_culture", "general_operating",
]


def normalize_date(raw: Optional[str]) -> Optional[str]:
    """Grants.gov returns MM/DD/YYYY. Store ISO (YYYY-MM-DD) or None."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


@dataclass
class Grant:
    # provenance
    source: str                      # "grants.gov" | "state:CA" | ...
    source_id: str
    title: str
    official_url: str

    opportunity_number: str = ""
    agency: str = ""
    level: str = "federal"           # federal | state | county | city | utility
    jurisdiction: str = "US"         # "US" or a 2-letter state, e.g. "CA"
    status: str = ""                 # posted | forecasted | closed
    open_date: Optional[str] = None
    close_date: Optional[str] = None

    # money
    award_min: Optional[float] = None
    award_max: Optional[float] = None
    assistance_listing: str = ""     # CFDA / ALN, links to USASpending history

    # plain-language layer (filled by AI: extract.py)
    summary_plain: str = ""          # 1-2 sentences, no bureaucratese
    eligibility_entity_types: list[str] = field(default_factory=list)
    eligibility_states: list[str] = field(default_factory=list)  # [] == nationwide
    eligibility_use_cases: list[str] = field(default_factory=list)
    eligibility_notes: str = ""

    # enrichment (USASpending historical award stats)
    enrichment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
