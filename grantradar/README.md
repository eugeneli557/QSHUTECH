# GrantRadar

**Grants scattered across 3,000 government sites — filtered to the ones a user can actually win.**

A paid grant-discovery service for US small businesses, founders, and nonprofits.
The user sets a profile once (state, entity type, funding need); GrantRadar scans
federal + state + local funding and ranks only what they're *eligible* for — with
the deadline, the dollars, and a link to the official source.

This repo is a working prototype: the data pipeline, eligibility engine, and
product UI are all real and runnable.

---

## Why this makes money (the thesis)

- **Information asymmetry**: grant info is real, public, and *painfully* scattered.
  Aggregating it is genuine value a Google search can't replace.
- **High conversion**: the buyer uses grants to get money. Paying $19/mo to not
  miss a $50k grant is a rounding error. Willingness-to-pay is structurally high.
- **Recurring**: grants reopen and expire constantly, so the data is never "done."
  That's what turns a one-time lookup into a subscription.
- **AI is the tool, not the product**: AI normalizes 5,000 differently-worded
  pages into one queryable schema and translates bureaucratese into plain English.
  The *product* is the curated, matched, deadline-aware data.

## What's in here

```
grantradar/
├── backend/
│   ├── schema.py         # the one data model every source normalizes into
│   ├── fetch_federal.py  # REAL pipeline: Grants.gov + USASpending (free, no key)
│   ├── extract.py        # AI layer: raw synopsis -> structured eligibility
│   ├── match.py          # the eligibility engine (this is the paid product)
│   └── demo_match.py     # runs the engine over seed data, no network needed
├── data/
│   └── seed_grants.json  # 14 records modeled on real programs, in live schema
├── web/
│   ├── index.html        # UI source (SEED_PLACEHOLDER token gets injected)
│   └── grantradar.html   # built, self-contained demo (open this in a browser)
└── requirements.txt
```

## Try it in 30 seconds

**The product UI** — open `web/grantradar.html` in any browser. Change the
profile on the left; results re-rank live. Toggle "Preview Pro" to see past the
paywall. (Also published as a shareable link — ask and I'll paste it.)

**The engine, in the terminal** — no network required:

```bash
cd backend
python demo_match.py
```

You'll see it scan 14 grants and pick the exact 3 a California clean-energy
startup can apply for, with reasons, disqualifiers, and deadline urgency.

**The live data pipeline** — on your own machine (US gov APIs may be blocked in
sandboxes, never in production):

```bash
pip install -r requirements.txt
cd backend
python fetch_federal.py --keyword "solar" --status posted --enrich --out ../data/federal.json
```

`--enrich` also asks USASpending what this program *historically* paid out, so
the UI can show "median award ~$42k" — a trust signal competitors don't have.

## The data strategy (the actual moat)

| Layer | Source | Difficulty | How |
|-------|--------|-----------|-----|
| 1. Federal | Grants.gov + USASpending APIs | **Easy** | Free, key-less JSON. `fetch_federal.py` already does this. |
| 2. State / local / utility | ~thousands of gov sites | **Hard (the moat)** | Targeted scrapers + **AI extraction** (`extract.py`) instead of per-site parsers. |
| 3. Private foundations | Candid / Foundation Directory | Later | Paid data; only after there's revenue. |

Start with Layer 1 (ships day one) + one vertical of Layer 2. Deepen Layer 2
over time — that's what makes GrantRadar hard to copy.

## Go-to-market (validate before you build more)

1. **Weeks 1–2**: hand-curate a free weekly email for one niche (e.g. "new
   clean-energy grants for CA small businesses"). Post it to relevant subreddits
   / FB groups. Watch subscribes and replies.
2. **Weeks 3–4**: at a few hundred subscribers, put up a landing page with a
   pre-sell ("$19/mo — full database + match + deadline alerts"). **A real
   payment** is the green light.
3. **Then** ship the MVP: Layer 1 + one state, matching + alerts, to the
   pre-sold users.

## Pricing

- Consumer: **$9–19/mo**
- Pro (nonprofits, consultants): **$49–99/mo**
- Free email newsletter as the top of the funnel (3–5% converts).

---

*Prototype status: engine, ranking, deadline logic, and paywall are live. Seed
records are modeled on real US programs in the exact schema the pipeline
produces; swap in live `fetch_federal.py` output to go real.*
