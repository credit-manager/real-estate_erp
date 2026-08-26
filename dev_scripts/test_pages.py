# -*- coding: utf-8 -*-
"""Render smoke test: pages compile with new tabs/modals, i18n resolves."""
import sys
sys.path.insert(0, ".")
from app import app

c = app.test_client()
r = c.post("/login", json={"username": "admin", "password": "admin123"})
print("login:", r.status_code)

pages = ["/realestate", "/rentals/renewals"]
ok = True
for p in pages:
    r = c.get(p)
    html = r.get_data(as_text=True)
    marks = {
        "/realestate": ["re-brokers", "re-analytics", "re-screenings", "re-mortgages",
                        "checklist-modal", "distribute-modal", "screening-modal",
                        "mortgage-modal", "التحليلات", "فحص الاستادة", "الرهون"],
        "/rentals/renewals": ["renewal-escalation-hint"],
    }.get(p, [])
    missing = [m for m in marks if m not in html]
    print(f"{p}: {r.status_code} {'OK' if not missing else 'MISSING: ' + str(missing)}")
    ok = ok and r.status_code == 200 and not missing

# escalation config API
with c.session_transaction() as s:
    s["_csrf_token"] = "tt"
r = c.get("/api/rentals/escalation-config")
print("escalation-config:", r.status_code, r.get_json())

print("PAGES RENDER OK" if ok else "RENDER ISSUES FOUND")
