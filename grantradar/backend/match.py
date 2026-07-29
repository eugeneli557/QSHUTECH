"""
match.py — the eligibility matching engine. This is the paid product.

A user tells us their profile once (state, entity type, what they want funding
for). For every grant we compute a 0-100 match score and a short human reason.
"Out of 500 grants, here are the 8 you can actually apply for" is the thing
people pay $19/month for and Google can't do.

Pure functions, no dependencies — trivially unit-testable and fast enough to
run over the whole database on every profile change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional


@dataclass
class Profile:
    state: str = ""                     # 2-letter, e.g. "CA"
    entity_type: str = ""               # one of schema.ENTITY_TYPES
    use_cases: Optional[list[str]] = None  # subset of schema.USE_CASES

    def __post_init__(self) -> None:
        self.state = (self.state or "").upper()
        self.use_cases = self.use_cases or []


@dataclass
class MatchResult:
    score: int
    reasons: list[str]
    disqualifiers: list[str]
    days_left: Optional[int]

    @property
    def eligible(self) -> bool:
        # A hard geographic/entity disqualifier drops it out of "eligible".
        return not self.disqualifiers and self.score >= 40


def _days_left(close_date: Optional[str], today: Optional[date] = None) -> Optional[int]:
    if not close_date:
        return None
    today = today or date.today()
    try:
        cd = datetime.strptime(close_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (cd - today).days


def score_grant(grant: dict[str, Any], profile: Profile,
                today: Optional[date] = None) -> MatchResult:
    """Score one grant (as a dict, i.e. Grant.to_dict()) against a profile."""
    reasons: list[str] = []
    disqualifiers: list[str] = []
    score = 50  # neutral base

    # --- Geography: a hard gate -------------------------------------------
    elig_states = grant.get("eligibility_states") or []
    if not elig_states:
        score += 10
        reasons.append("Open nationwide")
    elif profile.state and profile.state in elig_states:
        score += 25
        reasons.append(f"Available in your state ({profile.state})")
    elif profile.state and profile.state not in elig_states:
        disqualifiers.append(
            f"Restricted to {', '.join(elig_states)} — not {profile.state}"
        )
        score -= 40

    # --- Entity type: a hard gate -----------------------------------------
    elig_entities = grant.get("eligibility_entity_types") or []
    if not elig_entities:
        reasons.append("No entity-type restriction stated")
    elif profile.entity_type and profile.entity_type in elig_entities:
        score += 25
        reasons.append(f"Matches your entity type ({_label(profile.entity_type)})")
    elif profile.entity_type and profile.entity_type not in elig_entities:
        disqualifiers.append(
            f"For {', '.join(_label(e) for e in elig_entities)}, "
            f"not {_label(profile.entity_type)}"
        )
        score -= 35

    # --- Use case: soft signal, drives ranking not eligibility ------------
    elig_uses = set(grant.get("eligibility_use_cases") or [])
    overlap = elig_uses.intersection(profile.use_cases or [])
    if overlap:
        score += 15
        reasons.append("Funds " + ", ".join(_label(u) for u in overlap))

    # --- Deadline: urgency + a closed-grant guard -------------------------
    days_left = _days_left(grant.get("close_date"), today)
    if days_left is not None:
        if days_left < 0:
            disqualifiers.append("Deadline has passed")
            score -= 50
        elif days_left <= 14:
            reasons.append(f"Closes soon — {days_left} days left")
        elif days_left <= 45:
            reasons.append(f"{days_left} days to apply")

    score = max(0, min(100, score))
    return MatchResult(score=score, reasons=reasons,
                       disqualifiers=disqualifiers, days_left=days_left)


def rank(grants: list[dict[str, Any]], profile: Profile,
         today: Optional[date] = None) -> list[dict[str, Any]]:
    """Return grants annotated with match info, best first, closed/ineligible
    pushed to the bottom."""
    out = []
    for g in grants:
        m = score_grant(g, profile, today)
        out.append({
            **g,
            "match_score": m.score,
            "match_reasons": m.reasons,
            "match_disqualifiers": m.disqualifiers,
            "days_left": m.days_left,
            "eligible": m.eligible,
        })
    out.sort(key=lambda x: (x["eligible"], x["match_score"]), reverse=True)
    return out


_LABELS = {
    "small_business": "small business", "nonprofit": "nonprofit",
    "individual": "individual", "local_government": "local government",
    "tribal": "tribal entity", "research_institution": "research institution",
    "farmer": "farmer/agricultural producer", "startup": "startup",
    "clean_energy": "clean energy", "energy_efficiency": "energy efficiency",
    "ev_charging": "EV charging", "solar": "solar", "hiring_training": "hiring & training",
    "rd_innovation": "R&D / innovation", "export_trade": "export & trade",
    "disaster_recovery": "disaster recovery", "broadband": "broadband",
    "agriculture": "agriculture", "housing": "housing",
    "arts_culture": "arts & culture", "general_operating": "general operating",
}


def _label(token: str) -> str:
    return _LABELS.get(token, token.replace("_", " "))
