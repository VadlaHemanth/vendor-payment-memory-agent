# Vendor Payment Memory Agent

An AP clerk never solves the same GST invoice exception twice. This agent
retains every vendor pattern, exception, and approval resolution, and
recalls it on the next invoice to suggest the fix that worked last time.

Built on **Hindsight** (Vectorize) — memory is the product, not a feature.

## Why this problem is real (verified)

- **$9.84** to process one invoice, **8.2 days**, **18.4%** exception rate;
  48% of AP teams call exceptions their top hurdle. Best-in-class: $2.65,
  2.9 days, 11.1% exceptions. (Ardent Partners, State of ePayables 2025)
- Exceptions are 5–15% of volume but **30–50% of cost**, +15–45 min each. (IOFM 2024)
- India: **Rs 36,374 cr** fake ITC, 9,190 cases in FY23-24; 29,273 bogus
  firms, Rs 44,015 cr evasion since May 2023. (PIB, CBIC)
- Without memory: generic "hold for manual review" (conf 0.35).
  With memory: vendor-specific fix + evidence, e.g. "seen 8x" (conf 0.95, AUTO_RESOLVE).

## How Hindsight memory is used

- **Bank:** `ap-vendor-memory` — one isolated brain for the AP function.
- **`retain()`** — every scored invoice + human-approved resolution is stored
  as a narrative: vendor, amounts, exception codes, fix, approver, terms.
  Hindsight extracts facts/entities and consolidates repeats into observations
  (e.g. "Keerthi Foods GSTIN mismatches resolve by auto-correct to master").
- **`recall()`** — on each new invoice, query = vendor + exception codes.
  TEMPR 4-way retrieval (semantic + BM25 keyword + graph + temporal),
  RRF + rerank, `prefer_observations=True` so consolidated vendor patterns
  supersede raw repeats. Returned evidence count drives confidence and action
  (ROUTE_APPROVER → AUTO_RESOLVE → BLOCK for duplicates).
- **Learning curve:** Interaction 1 (empty bank): conf 0.55, ROUTE.
  Interaction 5: conf 0.75, AUTO. Interaction 10+: conf 0.95, AUTO with 8x evidence.
  Run `scripts/demo.py` on an empty store to watch it learn.
- **Fallback:** if no Hindsight server is reachable, a local JSONL keyword
  store with the identical retain/recall shape keeps the demo alive.
  `/api/health` always reports the active mode. Real Hindsight is tried first.

## Quick start

```bash
cd vendor-memory-agent
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env   # edit HINDSIGHT_* for Cloud (below)

# Option A: Hindsight Cloud (recommended for judging)
# Sign up https://ui.hindsight.vectorize.io, billing -> promo MEMHACK99 ($50)
# .env: HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
#       HINDSIGHT_API_KEY=<your key>

# Option B: local server (needs any LLM key, e.g. Groq free at groq.com)
# docker run -p 8888:8888 -e HINDSIGHT_API_LLM_API_KEY=$GROQ_API_KEY \
#   -e HINDSIGHT_API_LLM_PROVIDER=groq ghcr.io/vectorize-io/hindsight:latest

./.venv/bin/python scripts/seed_memory.py 200
./.venv/bin/python -m uvicorn app.main:app --port 8902
# open http://127.0.0.1:8902/ (dark/light toggle, responsive down to 390px)
```

Run the edge-case suite (14 checks: validation, duplicates, fallback store):

```bash
./.venv/bin/python tests/test_edge.py
```

Watch the learning curve from zero:

```bash
rm -f data/memory_fallback.jsonl
./.venv/bin/python scripts/demo.py   # Int 1 generic -> Int 20 personalized
```

## API

- `GET /` — demo UI (without vs with memory, seed, stats)
- `POST /api/score` — score one invoice both ways
- `POST /api/feedback` — retain a human resolution (compounds memory)
- `POST /api/seed?n=200` — seed vendor history
- `GET /api/stats` — straight-through rate, confidence with vs without
- `GET /api/vendors`, `GET /api/health`

## Structure

```
app/main.py      FastAPI + endpoints
app/memory.py    Hindsight wrapper (retain/recall + fallback)
app/invoices.py  8 Hyderabad vendors, GSTIN/HSN/PO validators, generator
app/agent.py     without/with-memory scoring + fix playbook
scripts/seed_memory.py  seed 200 historical resolutions
scripts/demo.py         Interaction 1->20 learning-curve demo
static/index.html       before/after demo UI
```

## Links

- Hindsight GitHub: https://github.com/vectorize-io/hindsight
- Hindsight docs: https://hindsight.vectorize.io/
- What is agent memory: https://vectorize.io/what-is-agent-memory
