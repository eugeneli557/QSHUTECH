"""
extract.py — Layer that turns messy grant text into structured eligibility.

This is where AI earns its place in the project. A grant synopsis is long,
bureaucratic, and every source writes it differently. Rather than hand-writing
a parser per website, we give one LLM prompt a fixed schema and let it map the
free text onto our controlled vocabularies (schema.ENTITY_TYPES / USE_CASES).

The point of AI here is NOT to invent content — every field is grounded in the
official text, and the official_url is always kept so a user can verify. AI is
the normalizer that makes 5,000 differently-worded pages queryable.

Provider-agnostic: plug in whichever model you use. The prompt + JSON contract
below is the stable part. `extract_eligibility()` is a thin wrapper you point
at your LLM client.
"""

from __future__ import annotations

import json
from typing import Any

from schema import Grant, ENTITY_TYPES, USE_CASES

EXTRACTION_SYSTEM_PROMPT = """You structure US grant descriptions for a search \
database. You are given the raw title, agency, and synopsis text of ONE funding \
opportunity. Extract ONLY what the text supports. Never guess. If the text does \
not state something, leave it empty.

Return STRICT JSON with exactly these keys:
{
  "summary_plain": "1-2 plain-English sentences a non-expert understands. \
No jargon, no 'the purpose of this NOFO is'. Say who it's for and what it funds.",
  "eligibility_entity_types": [subset of: %s],
  "eligibility_states": ["2-letter codes if geographically restricted; [] if nationwide"],
  "eligibility_use_cases": [subset of: %s],
  "award_min": number or null,
  "award_max": number or null,
  "eligibility_notes": "short caveats not captured above (deadlines, cost share, \
citizenship, revenue caps). One or two sentences max."
}
Output JSON only. No prose before or after.""" % (ENTITY_TYPES, USE_CASES)


def build_user_prompt(title: str, agency: str, synopsis_text: str) -> str:
    # Truncate very long synopses; the eligibility section is usually early.
    synopsis_text = (synopsis_text or "")[:8000]
    return (
        f"TITLE: {title}\n"
        f"AGENCY: {agency}\n"
        f"SYNOPSIS:\n{synopsis_text}\n"
    )


def extract_eligibility(
    title: str,
    agency: str,
    synopsis_text: str,
    llm_call,
) -> dict[str, Any]:
    """Run the extraction.

    `llm_call(system: str, user: str) -> str` is YOUR model client. It must
    return the model's text response. This keeps extract.py provider-neutral:
    Anthropic, OpenAI-compatible, or a local model all fit the same signature.

    Example wiring (Anthropic Python SDK):

        from anthropic import Anthropic
        client = Anthropic()
        def llm_call(system, user):
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",   # cheap + fast for batch
                max_tokens=800,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text

    Haiku-class models are the right call here: extraction is high-volume and
    schema-bound, so you want cheap-per-call, not maximum reasoning.
    """
    raw = llm_call(EXTRACTION_SYSTEM_PROMPT,
                   build_user_prompt(title, agency, synopsis_text))
    return _safe_json(raw)


def apply_extraction(grant: Grant, extracted: dict[str, Any]) -> Grant:
    """Merge validated extractor output onto a Grant, dropping any tokens that
    aren't in our controlled vocabulary (defends against model drift)."""
    grant.summary_plain = str(extracted.get("summary_plain", "")).strip()
    grant.eligibility_entity_types = [
        t for t in extracted.get("eligibility_entity_types", [])
        if t in ENTITY_TYPES
    ]
    grant.eligibility_use_cases = [
        u for u in extracted.get("eligibility_use_cases", [])
        if u in USE_CASES
    ]
    grant.eligibility_states = [
        s.upper() for s in extracted.get("eligibility_states", [])
        if isinstance(s, str) and len(s) == 2
    ]
    grant.eligibility_notes = str(extracted.get("eligibility_notes", "")).strip()
    if extracted.get("award_min") is not None:
        grant.award_min = _num(extracted["award_min"])
    if extracted.get("award_max") is not None:
        grant.award_max = _num(extracted["award_max"])
    return grant


def _safe_json(raw: str) -> dict[str, Any]:
    """Models sometimes wrap JSON in prose or fences. Recover the object."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _num(v: Any) -> Any:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
