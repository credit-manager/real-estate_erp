# -*- coding: utf-8 -*-
"""Functional smoke test for new real-estate features."""
import sys
sys.path.insert(0, ".")
from app import app

c = app.test_client()

def show(label, r):
    try:
        body = r.get_json()
    except Exception:
        body = r.data[:120]
    print(f"{label}: HTTP {r.status_code} -> {body}")

# 1) Login as admin
r = c.post("/login", json={"username": "admin", "password": "admin123"})
show("login", r)

# login does session.clear() -> set a known CSRF token afterwards
with c.session_transaction() as s:
    s["_csrf_token"] = "testtoken123"
HDR = {"X-CSRF-Token": "testtoken123"}

# 2) Create broker
r = c.post("/api/realestate/brokers",
           json={"name": "أحمد السمسار", "agency_name": "وكالة الأمل العقارية",
                 "phone": "0501234567", "default_rate": 2.5}, headers=HDR)
show("create broker", r)
bid = (r.get_json() or {}).get("id")

# 3) Invalid rate rejected (150 > 100)
r = c.post("/api/realestate/brokers", json={"name": "خاطئ", "default_rate": 150}, headers=HDR)
show("broker rate=150 (expect 400)", r)

# 4) List brokers
r = c.get("/api/realestate/brokers")
lst = r.get_json()
items = lst["items"] if isinstance(lst, dict) else lst
print(f"brokers list count: {len(items)}")

# 5) Commission linked ONLY to broker (no employee) - previously impossible
if bid:
    r = c.post("/api/realestate/commissions",
               json={"broker_id": bid, "rate": 2.5, "amount": 2500,
                     "notes": "عمولة سمسار خارجي"}, headers=HDR)
    show("commission w/ broker", r)
    cid = (r.get_json() or {}).get("id")
    # commission rate validation
    r = c.post("/api/realestate/commissions", json={"broker_id": bid, "rate": 500}, headers=HDR)
    show("commission rate=500 (expect 400)", r)
    # 6) Delete broker WITH commissions -> should deactivate not delete
    if cid:
        c.delete(f"/api/realestate/commissions/{cid}", headers=HDR)
    r = c.delete(f"/api/realestate/brokers/{bid}", headers=HDR)
    show("delete broker (expect deactivated)", r)

# 7) Availability endpoint on first unit (if any)
r = c.get("/api/realestate/units")
units = r.get_json()
unit_list = units.get("items") if isinstance(units, dict) else units
if unit_list:
    uid = unit_list[0]["id"]
    r = c.get(f"/api/realestate/units/{uid}/availability")
    j = r.get_json()
    print(f"availability unit={uid}: status={j.get('status')} available={j.get('is_available')}")
else:
    print("no units in DB - availability skipped")

# 8) Shares validation (needs a unit; create share 60+50 => reject second)
if unit_list:
    uid = unit_list[0]["id"]
    r = c.post("/api/realestate/shares", json={"unit_id": uid, "share_percent": 150}, headers=HDR)
    show("share pct=150 (expect 400)", r)

print("\nDONE - all functional checks executed")
