"""FastAPI backend for Vendor Payment Memory Agent."""
from __future__ import annotations

import math
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

load_dotenv()

from .agent import memory_narrative, score_with_memory, score_without_memory
from .invoices import VENDORS, detect_exceptions, generate_invoices, vendor_by_id
from .memory import build_memory_from_env

app = FastAPI(title="Vendor Payment Memory Agent", version="1.0.0")
memory = build_memory_from_env()
SEEN: set[str] = set()
HISTORY: list[dict] = []
HISTORY_CAP = 500

STATIC = Path(__file__).resolve().parent.parent / "static"
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

VALID_VENDOR_IDS = {v["vendor_id"] for v in VENDORS}


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "error": message})


class InvoiceIn(BaseModel):
    invoice_no: str = "INV-DEMO-001"
    vendor_id: str = "V001"
    gstin: str = ""
    hsn: str = ""
    po_number: str = "PO-UNKNOWN"
    amount: float = 125000.0
    tax_rate: float = 0.12
    tax_amount: float = 15000.0
    approver: str = ""

    @field_validator("invoice_no", "vendor_id")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("gstin", "hsn", "po_number", "approver")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("amount", "tax_amount")
    @classmethod
    def _sane_money(cls, v: float) -> float:
        if not math.isfinite(v) or v < 0 or v > 1_00_00_00_000:
            raise ValueError("must be a finite amount between 0 and 100 crore")
        return v

    @field_validator("tax_rate")
    @classmethod
    def _sane_rate(cls, v: float) -> float:
        if not math.isfinite(v) or v < 0 or v > 0.28:
            raise ValueError("must be between 0 and 0.28 (GST slabs)")
        return v


class FeedbackIn(BaseModel):
    invoice_no: str
    vendor_id: str
    resolution: str
    action: str
    vendor_name: str = ""
    amount: float = 0.0
    approver: str = ""

    @field_validator("invoice_no", "vendor_id", "resolution", "action")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("must not be empty")
        return v


@app.get("/")
def root():
    idx = STATIC / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"ok": True, "memory": memory.status()}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return JSONResponse(status_code=204, content=None)


@app.get("/api/health")
def health():
    return {"ok": True, "memory": memory.status(), "seen": len(SEEN)}


@app.get("/api/vendors")
def vendors():
    return {"vendors": VENDORS}


@app.post("/api/score")
def score(inv: InvoiceIn):
    if inv.vendor_id not in VALID_VENDOR_IDS:
        return _err(f"Unknown vendor_id '{inv.vendor_id}'. Pick one from /api/vendors.")
    vendor = vendor_by_id(inv.vendor_id)
    data = inv.model_dump()
    data["vendor_name"] = vendor["name"]
    without = score_without_memory(data, vendor, SEEN)
    withm = score_with_memory(data, vendor, SEEN, memory)
    SEEN.add(data["invoice_no"])
    HISTORY.append({"invoice_no": data["invoice_no"], "vendor_id": data["vendor_id"],
                    "without": without, "with": withm})
    del HISTORY[:-HISTORY_CAP]  # bounded demo history; memory itself lives in Hindsight
    return {"invoice": data, "vendor": vendor,
            "without_memory": without, "with_memory": withm,
            "memory": memory.status()}


@app.post("/api/feedback")
def feedback(fb: FeedbackIn):
    if fb.vendor_id not in VALID_VENDOR_IDS:
        return _err(f"Unknown vendor_id '{fb.vendor_id}'.")
    vendor = vendor_by_id(fb.vendor_id)
    clean_resolution = fb.resolution.split(" (seen")[0].split(" (1 prior")[0]
    narrative = memory_narrative(
        {"invoice_no": fb.invoice_no, "amount": fb.amount,
         "gstin": vendor["gstin"], "hsn": vendor["hsn_default"]},
        vendor, clean_resolution, fb.action)
    res = memory.retain(narrative, context=f"AP resolution {fb.vendor_id}",
                        metadata={"vendor": fb.vendor_id, "action": fb.action})
    return {"ok": True, "retained": narrative, **res}


@app.get("/api/stats")
def stats():
    total = len(HISTORY) or 1
    auto = sum(1 for h in HISTORY if h["with"].get("action") in ("AUTO_RESOLVE", "APPROVE"))
    manual_flags = sum(len(h["without"].get("exceptions", [])) for h in HISTORY)
    return {
        "scored": len(HISTORY),
        "straight_through_with_memory": round(auto / total, 2),
        "avg_confidence_with": round(sum(h["with"].get("confidence", 0) for h in HISTORY) / total, 2),
        "avg_confidence_without": round(sum(h["without"].get("confidence", 0) for h in HISTORY) / total, 2),
        "manual_review_flags_without": manual_flags,
        "memory": memory.status(),
    }


@app.post("/api/seed")
def seed(n: int = 200):
    n = max(1, min(int(n), 500))  # clamp: protects Cloud credits and demo time
    invoices = generate_invoices(n=n)
    kept = 0
    for inv in invoices:
        vendor = vendor_by_id(inv["vendor_id"])
        exc = detect_exceptions(inv, vendor)
        codes = ",".join(sorted(e["code"] for e in exc)) or "CLEAN"
        narrative = (f"Vendor {vendor['vendor_id']} {vendor['name']}: invoice {inv['invoice_no']} "
                     f"Rs {inv['amount']} had {codes}. "
                     f"Resolution: prior {codes} handled per playbook; approver {vendor['approver']}.")
        memory.retain(narrative, context=f"seed {vendor['vendor_id']}")
        kept += 1
    return {"seeded": kept, "memory": memory.status()}
