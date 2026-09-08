"""End-to-end integration test: one full negotiation to settlement.

Run:  python test_negotiation.py [scenario_id]
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

from app import store  # noqa: E402
from app.agent.engine import start_negotiation  # noqa: E402
from app.scenarios import SCENARIOS  # noqa: E402

DB = ROOT / "test.db"
if DB.exists():
    DB.unlink()
store.DB_PATH = DB
store._conn = None

scenario_id = sys.argv[1] if len(sys.argv) > 1 else "fitlife_gym"
sc = SCENARIOS[scenario_id]
print(f"[1] opening dispute against {sc['provider_name']}")
nid = store.create_negotiation(sc["label"], sc["customer_text"], scenario_id)
start_negotiation(nid)

print("[2] waiting for a decision card (max 12 min)...")
decision = None
t0 = time.time()
while time.time() - t0 < 720:
    pend = [d for d in store.list_decisions(nid=nid, pending_only=True)
            if d["kind"] in {"settlement_approval", "impasse_review"}]
    if pend:
        decision = pend[0]
        break
    time.sleep(2)
    neg = store.get_negotiation(nid)
    if neg["status"] in {"failed"}:
        break

neg = store.get_negotiation(nid)
if not decision:
    print(f"FAIL: no settlement card. status={neg['status']}")
    for t in store.list_turns(nid):
        print(f"  [{t['side']}|{t['intent']}] {t['message'][:150]}")
    sys.exit(1)

print(f"[3] card after {time.time()-t0:.0f}s: {decision['question']}")
print(f"    offer: {decision['payload'].get('offer')}")
print("[4] approving and waiting for settlement...")

store.resolve_decision(decision["id"], "approved", "looks fair")
for _ in range(60):
    neg = store.get_negotiation(nid)
    if neg["status"] in {"settled", "declined", "failed"}:
        break
    time.sleep(1)

neg = store.get_negotiation(nid)
print(f"[5] final status: {neg['status']} | outcome: {neg.get('outcome')}")
print("transcript:")
for t in store.list_turns(nid):
    off = f"  [{t['offer']['kind']} {t['offer']['amount']}]" if t["offer"] else ""
    print(f"  [{t['side']}|{t['intent']}]{off} {t['message'][:120]}")

led = store.total_saved()
print("ledger:", led)
ok = neg["status"] == "settled" and sum(led.values()) > 0
print("RESULT:", "PASS" if ok else "FAIL")
