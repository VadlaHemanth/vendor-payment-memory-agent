# Demo video script (3 min) — Vendor Payment Memory Agent

## 0:00-0:30 Intro (show UI at http://127.0.0.1:8902/)
"I'm [name]. AP teams spend $9.84 and 8 days per invoice, and 18% need
exception handling. I built an agent with Hindsight memory so no vendor
exception is ever solved twice."

## 0:30-1:00 The problem (fresh memory)
`rm -f data/memory_fallback.jsonl`, restart server.
Score INV-V001 with wrong GSTIN.
WITHOUT memory: "Generic: hold for manual review", conf 0.35.
"Every invoice looks new. This is the $19.8M/yr-style toil, in finance."

## 1:00-2:45 Live demo (retain/recall in action)
Run `scripts/demo.py`. Narrate 3 beats:
1. Interaction 1: conf 0.55, ROUTE_APPROVER, no evidence.
2. Interaction 5: "seen 4x", conf 0.75, AUTO_RESOLVE.
3. Interaction 10+: "seen 8x", conf 0.95.
Then in UI: `POST /api/seed` 200, score a duplicate invoice -> BLOCK with
evidence; score clean invoice -> APPROVE 0.92. Show `/api/stats`:
straight-through + confidence with vs without. Mention Hindsight
retain/recall + observation consolidation by name; show code
`app/memory.py` retain/recall calls.

## 2:45-3:00 Takeaway
"What surprised me: memory compounds. The 20th invoice from the same
vendor resolves itself. That is the difference between a chatbot and an
employee."
End card: GitHub repo link + Hindsight links.

Record: 1080p, terminal font 18+, close notifications. Thumbnail: invoice +
memory graph + "8x auto-resolved".
