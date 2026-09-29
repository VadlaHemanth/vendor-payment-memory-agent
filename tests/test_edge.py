"""Edge-case tests: validation, unknown vendors, bad money, seed clamp, fallback memory."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def good_invoice(**kw):
    base = {"invoice_no": "INV-V001-T01", "vendor_id": "V001",
            "gstin": "36XXXXK4821P1Z6", "hsn": "1006", "po_number": "PO-1001",
            "amount": 95000, "tax_rate": 0.12, "tax_amount": 11400, "approver": "R. Sharma"}
    base.update(kw)
    return base


print("== validation ==")
r = client.post("/api/score", json=good_invoice(vendor_id="V999"))
check("unknown vendor -> 400", r.status_code == 400, r.status_code)

r = client.post("/api/score", json=good_invoice(invoice_no="   "))
check("blank invoice_no -> 422", r.status_code == 422, r.status_code)

r = client.post("/api/score", json=good_invoice(amount=-50))
check("negative amount -> 422", r.status_code == 422, r.status_code)

r = client.post("/api/score", json=good_invoice(tax_rate=0.99))
check("tax_rate 0.99 -> 422", r.status_code == 422, r.status_code)

r = client.post("/api/score", json=good_invoice(amount=0))
check("zero amount accepted", r.status_code == 200, r.status_code)

r = client.post("/api/score", json=good_invoice())
check("good invoice -> 200", r.status_code == 200, r.status_code)
d = r.json()
check("without/with keys", "without_memory" in d and "with_memory" in d)
check("memory status present", d["memory"]["mode"] in ("hindsight", "fallback"), d["memory"])

print("== duplicates ==")
r = client.post("/api/score", json=good_invoice())
check("rescore same no flags DUPLICATE",
      any(e["code"] == "DUPLICATE" for e in r.json()["with_memory"]["exceptions"]))

print("== clean invoice ==")
from app.invoices import vendor_by_id
v = vendor_by_id("V001")
r = client.post("/api/score", json=good_invoice(
    invoice_no="INV-V001-CLEAN1", gstin=v["gstin"], hsn=v["hsn_default"],
    po_number="PO-4242", tax_amount=11400, approver="R. Sharma"))
check("clean -> APPROVE", r.json()["with_memory"]["action"] == "APPROVE", r.json()["with_memory"])

print("== feedback ==")
r = client.post("/api/feedback", json={"invoice_no": "", "vendor_id": "V001",
                                       "resolution": "x", "action": "APPROVE"})
check("blank feedback invoice_no -> 422", r.status_code == 422, r.status_code)
r = client.post("/api/feedback", json={"invoice_no": "INV-X", "vendor_id": "V999",
                                       "resolution": "x", "action": "APPROVE"})
check("feedback unknown vendor -> 400", r.status_code == 400, r.status_code)

print("== fallback memory unit ==")
from app.memory import HindsightMemory
m = HindsightMemory("http://127.0.0.1:9", None, "test-bank", "/tmp/tmem.jsonl")
open("/tmp/tmem.jsonl", "w").write("")
m.retain("Vendor V001 Keerthi Foods GSTIN_MISMATCH resolved by auto-correct", context="t")
m.retain("garbage line intact", context="t")
open("/tmp/tmem.jsonl", "a").write("{not json\n")
res = m.recall("vendor V001 GSTIN_MISMATCH")
check("fallback recall skips corrupt lines", len(res["memories"]) >= 1, res)
check("fallback mode reported", res["mode"] == "fallback")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
