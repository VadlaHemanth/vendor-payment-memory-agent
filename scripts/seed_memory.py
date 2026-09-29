"""Seed Hindsight (or local fallback) with realistic AP history."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

from app.invoices import detect_exceptions, generate_invoices, vendor_by_id
from app.memory import build_memory_from_env


def main(n: int = 200):
    mem = build_memory_from_env()
    print(f"memory mode: {mem.status()}")
    invoices = generate_invoices(n=n)
    for inv in invoices:
        vendor = vendor_by_id(inv["vendor_id"])
        exc = detect_exceptions(inv, vendor)
        codes = ",".join(sorted(e["code"] for e in exc)) or "CLEAN"
        narrative = (f"Vendor {vendor['vendor_id']} {vendor['name']}: invoice {inv['invoice_no']} "
                     f"Rs {inv['amount']} had {codes}. "
                     f"Resolution: {codes} handled per playbook; approver {vendor['approver']}; "
                     f"terms {vendor['terms']}.")
        mem.retain(narrative, context=f"seed history {vendor['vendor_id']}",
                   metadata={"vendor": vendor["vendor_id"], "codes": codes})
    print(f"seeded {len(invoices)} memories -> {mem.status()}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
