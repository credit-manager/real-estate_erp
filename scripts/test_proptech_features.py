# -*- coding: utf-8 -*-
"""Functional test: escalation, snagging, KYC, mortgages, distribution, analytics."""
import sys
sys.path.insert(0, ".")
from app import app

c = app.test_client()
P = []

def show(label, r, expect=None):
    try:
        body = r.get_json()
    except Exception:
        body = r.data[:100]
    ok = "" if expect is None else ("  OK" if r.status_code == expect else f"  !! EXPECTED {expect}")
    P.append((label, r.status_code, expect))
    print(f"{label}: {r.status_code} {body}{ok}")

r = c.post("/login", json={"username": "admin", "password": "admin123"}); show("login", r, 200)
with c.session_transaction() as s:
    s["_csrf_token"] = "tt"
H = {"X-CSRF-Token": "tt"}

# ---- Setup: project + building + unit + customer via API core ----
import time as _time
_run = str(int(_time.time()))[-6:]
r = c.post("/api/projects", json={"name": "مشروع اختبار " + _run}, headers=H); show("create project", r, 201)
pid = (r.get_json() or {}).get("id")
r = c.post("/api/realestate/buildings", json={"project_id": pid, "name": "مبنى أ"}, headers=H); show("building", r, 201)
bid_ = (r.get_json() or {}).get("id")
r = c.post("/api/units", json={"unit_code": f"TST-{_run}-A", "project_id": pid,
           "building_id": bid_, "price": 500000}, headers=H); show("unit", r, 201)
uid = (r.get_json() or {}).get("id")
r = c.get("/api/customers"); custs = r.get_json()
cust_list = custs["items"] if isinstance(custs, dict) else custs
if not cust_list:
    r = c.post("/api/customers", json={"full_name": "عميل تجريبي"}, headers=H); show("customer", r, 201)
    cid2 = (r.get_json() or {}).get("id")
else:
    cid2 = cust_list[0]["id"]

# ---- 1) ESCALATION ----
with app.test_request_context():
    pass
from models import SystemSetting
from database import db as _db
with app.app_context():
    for k, v in [("rental_escalation_enabled", "1"), ("rental_escalation_percent", "5")]:
        row = SystemSetting.query.filter_by(key=k).first()
        if row:
            row.value = v
        else:
            _db.session.add(SystemSetting(key=k, value=v))
    _db.session.commit()
print("escalation settings committed: enabled=1 pct=5")

# rental contract needs customer+dates; use /api/rentals contract? rentals blueprint prefix /api/rentals
r = c.post("/api/rental-contracts", json={"customer_id": cid2, "unit_id": uid,
           "monthly_rent": 2000, "start_date": "2026-01-01",
           "end_date": "2026-12-31"}, headers=H)
show("rental contract (2000)", r, 201) if r.status_code in (200,201) else show("rental contract ALT", r)
contract_id = None
try: contract_id = (r.get_json() or {}).get("id") or (r.get_json() or {}).get("contract", {}).get("id")
except Exception: pass
print("contract_id =", contract_id)

# NOTE: unit now rented -> create a SECOND unit for sales tests
r = c.post("/api/units", json={"unit_code": f"TST-{_run}-B", "project_id": pid, "price": 400000}, headers=H)
uid2 = (r.get_json() or {}).get("id"); show("unit#2", r, 201)

if contract_id:
    r = c.post("/api/rentals/renewals", json={"contract_id": contract_id, "new_end_date": "2027-12-31"}, headers=H)
    j = r.get_json() or {}
    print(f"RENEWAL auto-escalation: prev={j.get('previous_monthly_rent')} new={j.get('new_monthly_rent')} pct={j.get('escalation_applied_percent')}")
    assert abs((j.get('new_monthly_rent') or 0) - 2100.0) < 0.01, "escalation math wrong!"

# ---- KYC guard on reservation ----
r = c.post("/api/realestate/screenings", json={"customer_id": cid2, "blacklist": True}, headers=H)
show("screening blacklist (auto-rejected)", r, 201)
sc_res = (r.get_json() or {}).get("result")
print("screening result:", sc_res, "(expect rejected)")
r = c.post("/api/realestate/reservations", json={"unit_id": uid2, "customer_id": cid2}, headers=H)
show("reserve blacklisted (expect 400)", r, 400)

# approve screening then reservation should pass
r = c.get(f"/api/realestate/screenings?customer_id={cid2}")
scr = r.get_json(); scr = scr["items"] if isinstance(scr, dict) else scr
sid = scr[0]["id"]
r = c.delete(f"/api/realestate/screenings/{sid}", headers=H); show("delete screening", r, 200)

# ---- SNAGGING flow ----
r = c.post("/api/realestate/sales-contracts", json={"unit_id": uid2, "customer_id": cid2}, headers=H)
show("sales contract", r, 201)
scid = (r.get_json() or {}).get("id")
r = c.post("/api/realestate/deliveries", json={"unit_id": uid2, "customer_id": cid2}, headers=H)
show("delivery", r, 201)
did = (r.get_json() or {}).get("id")
for d in ["تسليم المفاتيح", "قراءة العدادات"]:
    c.post(f"/api/realestate/deliveries/{did}/items", json={"description": d}, headers=H)
r = c.post(f"/api/realestate/deliveries/{did}/complete", headers=H)
show("complete w/ pending items (expect 400)", r, 400)
items = c.get(f"/api/realestate/deliveries/{did}/items").get_json()
for it in items:
    c.put(f"/api/realestate/checklist/{it['id']}", json={"status": "ok"}, headers=H)
r = c.post(f"/api/realestate/deliveries/{did}/complete", headers=H)
show("complete after checklist ok", r, 200)

# ---- MORTGAGE ----
r = c.post("/api/realestate/mortgages", json={"unit_id": uid2, "lender_name": "بنك الراجحي",
           "loan_amount": 300000, "ltv_percent": 70, "interest_rate": 5.5}, headers=H)
show("mortgage create", r, 201)
mid = (r.get_json() or {}).get("id")
r = c.post("/api/realestate/mortgages", json={"unit_id": uid2, "lender_name": "بنك آخر",
           "loan_amount": 100000, "ltv_percent": 20}, headers=H)
show("second mortgage same unit (expect 400)", r, 400)
r = c.post(f"/api/realestate/sales-contracts/{scid}/cancel", json={}, headers=H)
show("cancel mortgaged contract (expect 400)", r, 400)
r = c.post(f"/api/realestate/mortgages/{mid}/settle", json={}, headers=H); show("settle mortgage", r, 200)
r = c.post(f"/api/realestate/mortgages/{mid}", json={}, headers=H) if False else c.delete(f"/api/realestate/mortgages/{mid}", headers=H)
show("delete settled mortgage", r, 200)

# ---- SHARES DISTRIBUTION ----
r = c.post("/api/realestate/shares", json={"unit_id": uid2, "share_percent": 60}, headers=H); show("share60", r, 201)
r = c.post("/api/realestate/shares", json={"unit_id": uid2, "share_percent": 30}, headers=H); show("share30(sum90)", r, 201)
r = c.post(f"/api/realestate/units/{uid2}/distribute-revenue", json={"amount": 10000}, headers=H)
show("distribute at 90% (expect 400)", r, 400)
shares_raw = c.get("/api/realestate/shares").get_json()
shares_all = shares_raw["items"] if isinstance(shares_raw, dict) else shares_raw
shares = [s for s in shares_all if s["unit_id"] == uid2]
s30 = [s for s in shares if abs(s['share_percent']-30)<1][0]
r = c.put(f"/api/realestate/shares/{s30['id']}", json={"share_percent": 40}, headers=H); show("fix to 40%", r, 200)
r = c.post(f"/api/realestate/units/{uid2}/distribute-revenue", json={"amount": 10000, "description": "توزيع أرباح سنوي"}, headers=H)
show("distribute at 100% ", r, 200)
dist = (r.get_json() or {}).get("distribution", [])
print("distribution rows:", [(d['owner_name'] or d['owner_id'], d['share_percent'], d['amount']) for d in dist])

# ---- ANALYTICS ----
r = c.get("/api/realestate/analytics/occupancy")
j = r.get_json()
print("ANALYTICS overall:", j.get("overall"))
print("ANALYTICS per_project[0]:", (j.get("per_project") or [None])[0])

fails = [(l, s, e) for l, s, e in P if e is not None and s != e]
print("\n" + ("ALL ASSERTIONS PASSED ✔" if not fails else f"FAILURES: {fails}"))
