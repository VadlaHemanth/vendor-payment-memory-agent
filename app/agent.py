"""Resolution agent: WITHOUT memory = generic flags.
WITH memory (Hindsight recall) = vendor-specific fix + evidence.
"""
from __future__ import annotations

import re

from .invoices import detect_exceptions
from .memory import HindsightMemory

# Canonical fix playbook learned from AP best practice
FIX_PLAYBOOK = {
    "GSTIN_MISMATCH": "Auto-correct to vendor master GSTIN and re-validate via GSTR-2B; block ITC claim until matched.",
    "HSN_ERROR": "Replace HSN with vendor default and recompute tax slab.",
    "PO_MISMATCH": "Route to procurement to link correct PO; hold payment.",
    "TAX_MISMATCH": "Recompute tax from amount x rate; request revised invoice if delta > Rs 100.",
    "DUPLICATE": "Block as duplicate; reference original invoice for payment status.",
    "MISSING_APPROVAL": "Route to vendor's default approver per approval matrix.",
}


def score_without_memory(inv: dict, vendor: dict, seen_invoice_nos: set) -> dict:
    exceptions = detect_exceptions(inv, vendor)
    if inv["invoice_no"] in seen_invoice_nos:
        exceptions = exceptions + [{"code": "DUPLICATE",
                                    "detail": f"Invoice {inv['invoice_no']} seen before"}]
    return {
        "mode": "without_memory",
        "exceptions": exceptions,
        "suggestion": "Generic: hold for manual review." if exceptions else "Clean: approve.",
        "confidence": 0.35 if exceptions else 0.6,
        "evidence": [],
        "action": "MANUAL_REVIEW" if exceptions else "APPROVE",
    }


def _evidence_count(memories: list[dict], code: str, vendor_id: str,
                     vendor_name: str = "") -> int:
    # One prior case = one recalled memory mentioning this vendor + code.
    # (Do NOT parse "Nx" markers - those are display strings from prior
    # suggestions and would compound exponentially.)
    # Match vendor by ID or by name: Hindsight consolidates facts into
    # observations that sometimes use one form ("Keerthi Foods") and
    # sometimes the other ("vendor V001").
    name_bits = [b for b in re.findall(r"[A-Za-z]+", vendor_name) if len(b) > 3]
    n = 0
    for m in memories:
        c = m.get("content", "")
        if code not in c:
            continue
        if vendor_id in c or (name_bits and all(b in c for b in name_bits[:2])):
            n += 1
    return n


def score_with_memory(inv: dict, vendor: dict, seen_invoice_nos: set,
                      memory: HindsightMemory) -> dict:
    exceptions = detect_exceptions(inv, vendor)
    duplicate = inv["invoice_no"] in seen_invoice_nos
    if duplicate and not any(e["code"] == "DUPLICATE" for e in exceptions):
        exceptions = exceptions + [{"code": "DUPLICATE",
                                    "detail": f"Invoice {inv['invoice_no']} seen before"}]
    if not exceptions:
        return {"mode": "with_memory", "exceptions": [], "suggestion": "Clean: approve.",
                "confidence": 0.92, "evidence": [], "action": "APPROVE"}

    query = (f"vendor {vendor['vendor_id']} {vendor['name']} "
             + ", ".join(e["code"] for e in exceptions)
             + " past resolution approver")
    recalled = memory.recall(query)
    memories = recalled.get("memories", [])

    suggestions, evidence, counts = [], [], []
    for e in exceptions:
        code = e["code"]
        cnt = _evidence_count(memories, code, vendor["vendor_id"], vendor["name"])
        counts.append(cnt)
        base_fix = FIX_PLAYBOOK[code]
        if code == "MISSING_APPROVAL":
            base_fix = f"Route to {vendor['approver']} (default approver for {vendor['name']})."
        if cnt >= 2:
            suggestions.append(f"{code}: {base_fix} (seen {cnt}x for this vendor - auto-apply)")
        elif cnt == 1:
            suggestions.append(f"{code}: {base_fix} (1 prior case recalled)")
        else:
            suggestions.append(f"{code}: {base_fix}")
        evidence.append({"code": code, "prior_cases": cnt})

    total_prior = sum(counts)
    confidence = 0.55 + min(0.4, total_prior * 0.05)
    action = "AUTO_RESOLVE" if total_prior >= 3 and not duplicate else (
        "BLOCK" if duplicate else "ROUTE_APPROVER")
    return {
        "mode": "with_memory",
        "exceptions": exceptions,
        "suggestion": " | ".join(suggestions),
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "action": action,
        "recall_mode": recalled.get("mode"),
    }


def memory_narrative(inv: dict, vendor: dict, resolution: str, action: str) -> str:
    codes = ",".join(sorted({e["code"] for e in detect_exceptions(inv, vendor)} | set())) or "CLEAN"
    return (f"Vendor {vendor['vendor_id']} {vendor['name']}: invoice {inv['invoice_no']} "
            f"Rs {inv['amount']} had {codes}. Resolution: {resolution}. Action: {action}. "
            f"Approver {vendor['approver'] or 'unassigned'}. Terms {vendor['terms']}.")
