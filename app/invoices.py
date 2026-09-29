"""Synthetic but realistic Indian GST invoice data + deterministic validators.

Design: 8 Hyderabad vendors with stable GSTINs, HSN codes, payment terms
and approval chains. Invoices are generated with controlled exception
injection so the demo can show repeat patterns (the exact thing
Hindsight observations consolidate).
"""
from __future__ import annotations

import random
import re
from datetime import datetime, timedelta, timezone

VENDORS = [
    {"vendor_id": "V001", "name": "Keerthi Foods & Supplies", "gstin": "36AAKFK4821P1Z6",
     "hsn_default": "1006", "terms": "Net 30", "approver": "R. Sharma", "city": "Hyderabad"},
    {"vendor_id": "V002", "name": "Deccan Logistics Pvt Ltd", "gstin": "36AABCD1234E1Z2",
     "hsn_default": "9965", "terms": "Net 15", "approver": "S. Iyer", "city": "Secunderabad"},
    {"vendor_id": "V003", "name": "Sri Balaji Stationery House", "gstin": "36ABJFS8841K1Z9",
     "hsn_default": "4820", "terms": "Net 30", "approver": "R. Sharma", "city": "Hyderabad"},
    {"vendor_id": "V004", "name": "Nirmaan Constructions Material", "gstin": "36AAQCN5512M1Z4",
     "hsn_default": "2523", "terms": "Net 45", "approver": "A. Khan", "city": "Kompally"},
    {"vendor_id": "V005", "name": "CloudNine IT Services", "gstin": "36AAQCC9021N1Z7",
     "hsn_default": "9983", "terms": "Net 30", "approver": "P. Rao", "city": "HITEC City"},
    {"vendor_id": "V006", "name": "FreshLine Dairy Coop", "gstin": "36AABCF7712A1Z3",
     "hsn_default": "0401", "terms": "Net 7", "approver": "S. Iyer", "city": "Uppal"},
    {"vendor_id": "V007", "name": "Vijaya Electricals", "gstin": "36AAKFV2209B1Z8",
     "hsn_default": "8536", "terms": "Net 30", "approver": "A. Khan", "city": "Begumpet"},
    {"vendor_id": "V008", "name": "Harsha Packaging Industries", "gstin": "36AAHHP6630C1Z5",
     "hsn_default": "4819", "terms": "Net 45", "approver": "P. Rao", "city": "Jeedimetla"},
]

# Exception types mirror Ardent/IOFM reality: GSTIN/HSN/PO/tax/duplicate/approval
EXCEPTION_TYPES = ["GSTIN_MISMATCH", "HSN_ERROR", "PO_MISMATCH",
                   "TAX_MISMATCH", "DUPLICATE", "MISSING_APPROVAL"]

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def _mutate_gstin(gstin: str, rng: random.Random) -> str:
    lst = list(gstin)
    lst[rng.randrange(len(lst))] = rng.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return "".join(lst)


def generate_invoices(n: int = 200, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    invoices, seen = [], set()
    start = datetime(2025, 6, 1, tzinfo=timezone.utc)
    for i in range(n):
        v = rng.choice(VENDORS)
        # Repeat-offender pattern: V001 GSTIN issues, V002 PO issues, V005 HSN issues
        inject = None
        r = rng.random()
        if v["vendor_id"] == "V001" and r < 0.45:
            inject = "GSTIN_MISMATCH"
        elif v["vendor_id"] == "V002" and r < 0.35:
            inject = "PO_MISMATCH"
        elif v["vendor_id"] == "V005" and r < 0.30:
            inject = "HSN_ERROR"
        elif r < 0.22:
            inject = rng.choice(EXCEPTION_TYPES)

        inv_no = f"INV-{v['vendor_id']}-{2025001 + i}"
        if inject == "DUPLICATE" and seen:
            inv_no = rng.choice(sorted(seen))  # true duplicate number
        seen.add(inv_no)

        amount = round(rng.uniform(8500, 485000), 2)
        gstin = _mutate_gstin(v["gstin"], rng) if inject == "GSTIN_MISMATCH" else v["gstin"]
        hsn = "9999" if inject == "HSN_ERROR" else v["hsn_default"]
        po = "PO-UNKNOWN" if inject == "PO_MISMATCH" else f"PO-{rng.randint(1000, 9999)}"
        tax_rate = 0.05 if inject == "TAX_MISMATCH" else (0.18 if hsn in ("9983", "8536") else 0.12)
        approver = "" if inject == "MISSING_APPROVAL" else v["approver"]
        invoices.append({
            "invoice_no": inv_no,
            "vendor_id": v["vendor_id"],
            "vendor_name": v["name"],
            "gstin": gstin,
            "hsn": hsn,
            "po_number": po,
            "amount": amount,
            "tax_rate": tax_rate,
            "tax_amount": round(amount * tax_rate, 2),
            "approver": approver,
            "invoice_date": (start + timedelta(days=i % 90)).date().isoformat(),
            "injected": inject,
        })
    return invoices


def detect_exceptions(inv: dict, vendor: dict) -> list[dict]:
    """Deterministic validator. Returns [{code, detail}]. Empty = clean."""
    out = []
    if not GSTIN_RE.match(inv.get("gstin", "")) or inv["gstin"] != vendor["gstin"]:
        out.append({"code": "GSTIN_MISMATCH",
                    "detail": f"Billed GSTIN {inv['gstin']} != master {vendor['gstin']}"})
    if inv.get("hsn") != vendor["hsn_default"]:
        out.append({"code": "HSN_ERROR",
                    "detail": f"HSN {inv['hsn']} != vendor default {vendor['hsn_default']}"})
    if inv.get("po_number") == "PO-UNKNOWN":
        out.append({"code": "PO_MISMATCH", "detail": "PO not found in procurement"})
    expected_tax = round(inv.get("amount", 0) * inv.get("tax_rate", 0), 2)
    if abs(expected_tax - inv.get("tax_amount", -1)) > 1.0:
        out.append({"code": "TAX_MISMATCH",
                    "detail": f"Tax {inv['tax_amount']} inconsistent with rate {inv['tax_rate']}"})
    if not inv.get("approver"):
        out.append({"code": "MISSING_APPROVAL", "detail": "No approver assigned"})
    return out


def vendor_by_id(vendor_id: str) -> dict:
    for v in VENDORS:
        if v["vendor_id"] == vendor_id:
            return v
    raise KeyError(vendor_id)
