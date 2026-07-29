"""
fetch_federal.py — Layer 1 data pipeline: US federal grant opportunities.

This is the REAL, runnable integration. It pulls live data from two free,
public, key-less US government APIs:

  1. Grants.gov Search2 API   -> open/forecasted federal funding opportunities
  2. USASpending.gov Award API -> historical awards (used to enrich a program
                                   with "who actually got funded / typical $")

Both are documented as authentication-free. Grants.gov Search2 default rate
limit is generous; USASpending needs no key. In a restricted sandbox these
hosts may be blocked at the network layer — run this on your own machine/server.

Usage:
    python fetch_federal.py --keyword "solar" --status posted --rows 25
    python fetch_federal.py --keyword "small business" --out ../data/federal.json

Output is normalized into the shared Grant schema (see schema.py) so Layer 1
(federal) and Layer 2 (state/local scraped) records look identical downstream.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any

import requests  # pip install requests

from schema import Grant, normalize_date

GRANTS_GOV_SEARCH = "https://api.grants.gov/v1/api/search2"
GRANTS_GOV_FETCH = "https://api.grants.gov/v1/api/fetchOpportunity"
USASPENDING_AWARDS = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

# A polite default. Grants.gov Search2 allows well above this; we stay gentle.
_REQUEST_PAUSE_SECONDS = 0.4


def search_grants_gov(
    keyword: str,
    statuses: str = "posted|forecasted",
    rows: int = 25,
    eligibilities: str = "",
    agencies: str = "",
    aln: str = "",
    funding_categories: str = "",
) -> list[dict[str, Any]]:
    """Call the Grants.gov Search2 endpoint and return raw oppHits.

    `statuses` is a pipe-joined subset of: forecasted|posted|closed|archived.
    All the filter args are pipe-joined strings exactly as the API expects.
    """
    payload = {
        "rows": rows,
        "keyword": keyword,
        "oppStatuses": statuses,
        "eligibilities": eligibilities,
        "agencies": agencies,
        "aln": aln,
        "fundingCategories": funding_categories,
    }
    resp = requests.post(GRANTS_GOV_SEARCH, json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errorcode", 0) != 0:
        raise RuntimeError(f"Grants.gov error: {body.get('msg')}")
    return body.get("data", {}).get("oppHits", [])


def fetch_grant_detail(opportunity_id: int) -> dict[str, Any]:
    """Fetch the full synopsis (description, eligibility text, award ceiling)
    for a single opportunity. This is the text we feed to the AI extractor
    to structure eligibility (see extract.py)."""
    resp = requests.post(
        GRANTS_GOV_FETCH, json={"opportunityId": opportunity_id}, timeout=30
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


def _award_stats_for_aln(assistance_listing: str) -> dict[str, Any]:
    """Ask USASpending how this program actually paid out historically.

    Returns typical award size signal so the product can tell a user
    'grants under this program have averaged ~$X' — a real trust signal
    competitors don't show. Best-effort; returns {} on any failure.
    """
    if not assistance_listing:
        return {}
    payload = {
        "filters": {
            "award_type_codes": ["02", "03", "04", "05"],  # grant award types
            "program_numbers": [assistance_listing],
        },
        "fields": ["Award Amount", "Recipient Name", "Award Type"],
        "page": 1,
        "limit": 25,
        "sort": "Award Amount",
        "order": "desc",
    }
    try:
        resp = requests.post(USASPENDING_AWARDS, json=payload, timeout=30)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        amounts = [r.get("Award Amount") or 0 for r in results]
        amounts = [a for a in amounts if a]
        if not amounts:
            return {}
        return {
            "historical_award_count_sampled": len(amounts),
            "historical_award_max": max(amounts),
            "historical_award_median": sorted(amounts)[len(amounts) // 2],
        }
    except requests.RequestException:
        return {}


def normalize_hit(hit: dict[str, Any], enrich: bool = False) -> Grant:
    """Map one Grants.gov oppHit into the shared Grant schema."""
    aln_list = hit.get("alnist") or hit.get("cfdaList") or []
    primary_aln = aln_list[0] if aln_list else ""

    grant = Grant(
        source="grants.gov",
        source_id=str(hit.get("id", "")),
        opportunity_number=hit.get("number", ""),
        title=(hit.get("title") or "").strip(),
        agency=hit.get("agency", ""),
        level="federal",
        jurisdiction="US",
        status=hit.get("oppStatus", ""),
        open_date=normalize_date(hit.get("openDate")),
        close_date=normalize_date(hit.get("closeDate")),
        assistance_listing=primary_aln,
        official_url=f"https://www.grants.gov/search-results-detail/{hit.get('id','')}",
        # eligibility_* fields are populated by the AI extractor (extract.py)
        # from the full synopsis text; left empty here on purpose.
    )

    if enrich:
        stats = _award_stats_for_aln(primary_aln)
        grant.enrichment = stats
        time.sleep(_REQUEST_PAUSE_SECONDS)

    return grant


def run(keyword: str, statuses: str, rows: int, enrich: bool) -> list[Grant]:
    hits = search_grants_gov(keyword=keyword, statuses=statuses, rows=rows)
    print(f"[grants.gov] {len(hits)} opportunities for '{keyword}'", file=sys.stderr)
    grants: list[Grant] = []
    for hit in hits:
        grants.append(normalize_hit(hit, enrich=enrich))
    return grants


def main() -> None:
    ap = argparse.ArgumentParser(description="Pull live US federal grant data.")
    ap.add_argument("--keyword", default="", help="search keyword, e.g. 'solar'")
    ap.add_argument("--status", default="posted|forecasted",
                    help="pipe-joined: forecasted|posted|closed|archived")
    ap.add_argument("--rows", type=int, default=25)
    ap.add_argument("--enrich", action="store_true",
                    help="also query USASpending for historical award sizes")
    ap.add_argument("--out", default="", help="write normalized JSON to this path")
    args = ap.parse_args()

    grants = run(args.keyword, args.status, args.rows, args.enrich)
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "query": {"keyword": args.keyword, "status": args.status},
        "count": len(grants),
        "grants": [g.to_dict() for g in grants],
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {len(grants)} grants -> {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
