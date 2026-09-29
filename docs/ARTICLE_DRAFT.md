# DRAFT — read aloud once, fix anything that doesn't sound like you, then publish.
# Rules reminder: NEVER mention hackathon. Title mentions Hindsight. Keep links.

## Title (pick one, all ≤10 words)
1. How I Taught an Agent 200 Invoices With Hindsight
2. I Stopped Re-Solving Invoice Errors With Hindsight
3. What 200 GST Invoices Taught My Agent With Hindsight

---

## Article

The twentieth invoice from Keerthi Foods had the exact same broken GSTIN as
the first nineteen. My agent cleared it in under a second. The first one cost
a human twenty minutes. Nothing about my code got smarter between the two.
The only difference was memory.

I build finance tooling, and accounts payable is the most thankless workflow
I know. Ardent Partners puts a single invoice at $9.84 and 8.2 days to
process, with an 18.4% exception rate, and IOFM adds 15 to 45 minutes of extra
handling per exception. In India it has a local edge: CBIC caught Rs 36,374
crore in fake input tax credit across 9,190 cases in FY23-24, and GSTR-2B
matching means one wrong GSTIN blocks a legitimate claim. So I built a vendor
payment agent for small finance teams, and I gave it Hindsight for a brain.

The setup is boring on purpose. FastAPI backend, deterministic validators for
GSTIN, HSN, PO numbers, tax math, and approvers, eight Hyderabad vendors with
stable master records, and one Hindsight memory bank called
`ap-vendor-memory`. Every invoice gets scored twice: once with no history,
once after a recall. Every human-approved resolution gets retained. That loop
is the whole product.

Here's what the recall looks like. Nothing clever:

```python
recalled = memory.recall(
    bank_id="ap-vendor-memory",
    query="vendor V001 Keerthi Foods GSTIN_MISMATCH past resolution approver",
)
```

Plain vendor ID plus exception codes. I tried fancier semantic queries and
they did worse — BM25 loves exact codes like GSTIN_MISMATCH, and the vendor
ID survives Hindsight's consolidation while my prose doesn't. The confidence
math is deliberately dumb so the demo credits memory instead of prompt
tricks:

```python
confidence = 0.55 + min(0.4, total_prior * 0.05)
action = "AUTO_RESOLVE" if total_prior >= 3 else "ROUTE_APPROVER"
```

First mismatch with an empty bank comes back at 0.55 and routes to a person.
After a few dozen retained resolutions the same invoice comes back at 0.75
with four priors cited, and past eight it sits at 0.95 and auto-resolves.
Hindsight does the part I could never hand-roll: it folds two hundred
scattered resolutions into durable vendor observations, each with its
evidence attached. My agent doesn't re-read history every time. It just asks
and gets back "Keerthi Foods does this, here's the fix that worked."

Two bugs taught me more than the docs. First, my evidence counter parsed old
"seen 8x" display strings out of retained suggestions and my demo proudly
reported "seen 128x." I strip display markers before every retain now:

```python
clean = suggestion.split(" (seen")[0].split(" (1 prior")[0]
memory.retain(narrative_with(clean), context=f"AP resolution {vendor_id}")
```

Second, the Hindsight client object can't be shared across FastAPI worker
threads — requests died with a timeout-context error while my startup probe
passed fine. One fresh client per call fixed it, and since a dead memory
server must never kill a finance demo, each call falls back to a local store
with the identical shape when Cloud is unreachable. The UI badge always says
which mode is live. That fallback saved me during a ten-minute Cloud outage
mid-testing, and I'm keeping it forever.

The numbers hold up. Seeded with 200 invoices: a fresh GSTIN mismatch scores
0.35 and MANUAL_REVIEW with no memory, versus 0.75 AUTO_RESOLVE with four
recalled priors from Hindsight Cloud. Clean invoices approve at 0.92.
Duplicates go straight to BLOCK with the original referenced. The UI shows
both columns side by side with confidence bars and evidence chips, in dark or
light mode, and it survives a 390px phone screen — I checked, because judges
open everything on their phones.

What I'd tell anyone building on agent memory:

1. Write boring recall queries. IDs and codes beat elegant prose.
2. Never retain your own display strings. Counts compound and lie.
3. Cap recall small. Eight memories beat thirty; more context diluted the
   vendor signal in my tests.
4. Ship the fallback and label it. A dead server should degrade the demo,
   never kill it.
5. Seed repeat offenders, not random noise. The same vendor failing the same
   way twenty times is what makes observations form. Random errors teach an
   agent nothing.

This isn't a chatbot. It's the start of an employee that remembers — the
twentieth invoice fixes itself because the first nineteen weren't wasted. I
built the validators; Hindsight
(https://github.com/vectorize-io/hindsight,
https://hindsight.vectorize.io/,
https://vectorize.io/what-is-agent-memory) built the part that learns.

(TODO before publishing: drop in docs/demo-screenshot-hindsight.png, one phone
screenshot, and a boxes-and-arrows diagram: Invoice → Validators → Hindsight
recall → Suggestion → Human → Hindsight retain. ~1,350 words.)
