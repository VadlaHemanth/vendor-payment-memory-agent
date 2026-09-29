"""Before/after demo: Interaction 1 (generic) vs Interaction 20 (personalized)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

from app.agent import score_with_memory, score_without_memory
from app.invoices import vendor_by_id
from app.memory import build_memory_from_env

mem = build_memory_from_env()
print(f"MEMORY MODE: {mem.status()}\n")

vendor = vendor_by_id("V001")  # Keerthi Foods: repeat GSTIN offender
seen: set[str] = set()

def show(i: int, inv: dict):
    wo = score_without_memory(inv, vendor, seen)
    wi = score_with_memory(inv, vendor, seen, mem)
    print(f"--- Interaction {i}: {inv['invoice_no']} Rs {inv['amount']} ---")
    print(f"WITHOUT: {wo['suggestion']} (conf {wo['confidence']})")
    print(f"WITH   : {wi['suggestion']} (conf {wi['confidence']}, action {wi['action']}, recall={wi.get('recall_mode')})")
    # retain the outcome so memory compounds (strip display markers to avoid feedback loop)
    from app.agent import memory_narrative
    clean = wi["suggestion"].split(" (seen")[0].split(" (1 prior")[0]
    mem.retain(memory_narrative(inv, vendor, clean, wi["action"]),
               context="demo resolution V001")
    seen.add(inv["invoice_no"])
    print()

# Interaction 1: first ever GSTIN mismatch - no history
show(1, {"invoice_no": "INV-V001-2025001", "vendor_id": "V001", "vendor_name": vendor["name"],
         "gstin": "36XXXXK4821P1Z6", "hsn": "1006", "po_number": "PO-1001",
         "amount": 95000.0, "tax_rate": 0.12, "tax_amount": 11400.0, "approver": "R. Sharma"})
# Interactions 2..20: same pattern repeats, memory compounds
for i in range(2, 21):
    show(i, {"invoice_no": f"INV-V001-2025{i:03d}", "vendor_id": "V001", "vendor_name": vendor["name"],
             "gstin": "36XXXXK4821P1Z6", "hsn": "1006", "po_number": "PO-1001",
             "amount": 88000.0 + i * 1000, "tax_rate": 0.12, "tax_amount": (88000.0 + i * 1000) * 0.12,
             "approver": "R. Sharma"})
print("Done. Interaction 1 = generic. Interaction 20 = vendor-specific with evidence.")
