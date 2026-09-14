# Changelog — 2TO ERP (DynamicPro)

## [2.1.2] — 2026-09-14

### Dual-Logo Branding System
- Login page now shows **both logos simultaneously**: 2TO parent company logo (always prominent) + licensed company logo (conditional on active subscription + branding override enabled)
- New `ls-customer` CSS section with gradient accent border for the customer logo card
- Auth route (`routes/auth.py`) passes branding context (`customer_logo`, `branding_override`, `has_active_customer`) to `login.html`
- i18n keys added: `login.parentCompany`, `login.licensedCompany` (AR/EN)
- Settings UI labels clarified: parent company vs licensed company, override hint updated
- Version bumped to 2.1.2

## [2.1.1] — (Unreleased)

### Brand Identity — 2TO Flat Geometric Redesign
- `static/img/logo-mark.svg`: square shield symbol (fracStr geometric shield + hollow "2" + double V/chevron) — used in sidebar, admin panel, prints
- `static/img/logo-2to.svg`: primary flat lockup — `[2 Shield] + TO` + `ENTERPRISE OS` tagline, flat navy/steel/cyan (official)
- `static/img/logo-2to-3d.svg`: secondary 3D/metallic marketing variant (signage/presentations only)
- `static/img/logo-2to.png`: transparent 1200x400 raster of the flat lockup (login + PDF `system_logo` path)
- Sidesteps removed: no 3D bevels/gradients/shadows in the official mark; flat two-tone navy + light-steel "2", cyan accent
- Templates: `base.html`, `admin_panel.html`, 7 prints, `financial_year_report.html` use the square mark (object-fit cover); `login.html` uses the wide lockup (contain)
- Brand rollout across the whole program (owner company identity):
  - `favicon.svg`: shield + hollow 2 icon for browser tabs (`base`, `admin_panel`, `billing_portal`)
  - PWA icons `icon-192.png` / `icon-512.png`: regenerated from `logo-mark.svg` (centered, maskable safe zone)
  - `app.ico` (16-256px): installer + EXE icon now the shield mark
  - `billing_portal.html`, `register.html`: logo chips replaced with the shield mark image
  - `login.html` owner footer: no more initials fallback — shows the shield mark
  - `general_settings` branding card: owner preview defaults to the shield mark (HTML + JS)
  - `sw.js`: cache bumped to `2to-cache-v5`, precaches the mark

### Emblem Rework — Metallic 2-in-Shield (from reference poster)
- `static/img/logo-mark.svg` replaced with the metallic emblem traced from the reference art: wide head, straight left column, large right bowl with cyan rim, light "2" counters, lower-left diagonal tail to a point — navy `#14344C → #081C2E` metal gradients + `#00AEEF` rim, transparent counters
- `static/img/logo-2to.png` rebuilt: metallic emblem + `TO` / `ENTERPRISE OS` lockup (1200x400 RGBA) for `login.html` and PDF `system_logo` path
- `static/img/logo-2to-3d.svg` regenerated as metallic horizontal lockup (marketing/signage)
- `sw.js` cache bumped `2to-cache-v5` -> `2to-cache-v6`
- Small-surface assets also rebuilt from the metallic emblem: `favicon.svg` (64x64), PWA `icon-192.png` / `icon-512.png` (centered, maskable safe zone), `app.ico` (16-256 multi-size) — installer + EXE icon now the metallic mark; `sw.js` cache -> `2to-cache-v7`
- Icons re-rendered at full resolution (2048px source, not the tiny 32px crop) to remove green anti-alias fringing and keep crisp edges; `logo-2to.png` rebuilt likewise; `favicon.svg` regenerated with all 8 emblem paths (defs-only bug fixed); `app.ico` + EXE icon re-injected (overlay preserved); `sw.js` cache -> `2to-cache-v8`

### Billing Portal
- Added `templates/billing_portal.html`: company self-service billing page wired to all `/billing/*` endpoints
  - Subscription hero card (plan, status, end date, days remaining, user/project limits)
  - Billing summary KPIs and invoice table with status filter + pagination
  - Plan upgrade/downgrade modal (monthly / yearly billing cycle)
  - Cancel subscription flow (end of period or immediate)
  - Payment methods notice, CSRF-protected POST calls, theme toggle, logout

### Annual Sale (Admin / Billing)
- Added `POST /admin/companies/<id>/sale`: one-step paid sale (default: full year)
  - Renews the active/trial/grace/expired subscription for the chosen period or creates a fresh one
  - Optional plan switch on the same call (`plan_code`)
  - Auto-creates a `confirmed` `LicPayment` (amount, method, reference, `paid_at`, `confirmed_by`) wired to the subscription
  - Logs `sale_recorded` activity; returns subscription + payment + license
- Admin panel: new "بيع / تجديد" modal (`mSale`) in company profile and company rows
  - Plan selector (pre-filled), period presets (3/6/12/24 months, default سنة كاملة), suggested amount from plan prices, payment method, reference
  - `sale_recorded` added to activity feed labels/icons

### Executive Analytics (2026 roadmap)
- New `/analytics` page (finance hub card, `reports` permission): native, local KPIs — no external dependency
  - KPIs: revenue/collected/pending sales, expenses, net margin, receivables/payables (incl. overdue), stock value, reorder-alarm items, customers & suppliers counts
  - Charts (Chart.js): 12-month revenue vs expenses, overdue aging buckets (0-30/31-60/61-90/90+), top products, top customers
  - Low-stock table with quantity vs reorder level
- `GET /api/bi/analytics` (`require_api_any` view on reports/finance/sales/inventory)
- `GET /api/bi/alerts` — smart, actionable alerts:
  - Reorder level breaches, overdue sales invoices (with days), rental contracts expiring ≤30 days, pending purchase orders, expired open quotes
- New `utils/analytics.py` (pure SQLAlchemy, SQLite + Postgres safe) + regression test `tests/test_analytics.py`

### PWA (installable app)
- Added `static/manifest.webmanifest`, `static/sw.js` (root scope served at `/sw.js`), generated `img/icon-192.png` + `img/icon-512.png`
- Wired manifest / theme-color / apple-touch-icon + SW registration into `base.html`

### Version & Update Readiness
- New `version.py` single source of truth (2.1.1, build 20260913)
- `GET /api/version` (`require_any_view`) + version shown on the analytics page

### Documentation
- Added `ROADMAP_2026.md`: market research summary (Forrester/ERP industry/ETA-ZATCA) + status matrix (implemented / existing / deferred with reasons + next steps)

### Master Control Panel Access
- Topbar shield button (`#btn-master-panel`) + first card in system hub — both open `/admin` in a new tab
- Admin-only visibility: gated client-side via `GET /api/me` (`role === "admin"`) and server-side in `system_hub()` (only `session["role"] == "admin"` receives the card)
- New i18n keys `nav.masterPanel` / `hub.masterPanelSub` (ar + en) + regression tests `tests/test_panel_access.py`

### Smart Reorder Recommendations
- `utils/analytics.py::compute_reorder_recommendations` — monthly consumption from stock out-movements (last 90 days) → coverage days + suggested order qty (lead time setting `reorder_lead_days`, default 14)
- `low_stock_list` enriched (consumption/suggested) and displayed in `/analytics` alongside a full recommendations table
- Low-stock alerts now include the suggested order quantity

### Project KPIs (construction/contracting)
- `compute_project_kpis`: budget vs spent, budget utilization, completion %, delayed milestones, deadline/budget risk flags
- New `project_at_risk` smart alert (budget overrun / deadline passed-or-soon / delayed milestones)

### Cloud Backup (WebDAV / S3)
- New `utils/cloud_backup.py` (stdlib only): WebDAV PUT with Basic auth + S3-compatible PUT signed AWS Signature V4 (path-style) — works with AWS/MinIO/R2
- Auto-backup now pushes the encrypted file to cloud when enabled; last status/error stored in settings
- New `GET|POST /api/backup/cloud` endpoints (status, save, connection test, masked secrets)
- New "Cloud backup" card in the backup page with type switcher, credentials, bucket/region, connection test + i18n keys (ar + en)

### Per-Contract Branding (owner vs licensed company logo)
- New `utils/branding.py`: resolves the *effective* program logo — the owner company's logo by default, switching to the licensed company's own logo while a usable subscription is running (`trial` / `active` / `grace` up to the subscription end date), then returning automatically to the owner logo when the contract expires
- `settings.get("system_logo")` now returns the effective logo, so the PDF generator (`utils/pdf.py`), login, sidebar and all print templates show the same result without touching every template
- New **Branding** section in General Settings: owner logo preview, licensed-company logo upload (file → data-URL, ≤1.5MB) or URL, override toggle, live contract-period card (company / status / valid-until) + validation + i18n keys (ar + en)
- New `POST /general-settings/api/branding` endpoint; `GET /api` now includes a `branding` block
- Ships the owner logo as the new default brand mark: rebuilt `static/img/logo-2to.svg` (angular hex shield + hollow vector «2» in steel gradient, navy «TO» logotype, electric-blue «ENTERPRISE OS» tagline, transparent) rendered to a transparent high-res `static/img/logo-2to.png` (1200×400) replacing the old `logo-2to.svg` / Gemini-JPEG / `DP` fallbacks in `base.html`, `login.html`, `admin_panel.html` and the 8 print templates
- Regression tests `tests/test_branding.py` (9 tests: effective logo owner/customer/expired/suspended, override off, empty logo, validation, API save + invalid)

## [2.1.0] — 2026-09-13

### Security Fixes
- **SQL injection** in `factory_reset.py`: whitelist table names + validation guard
- **SQL injection** in `db_indexes.py`: identifier regex validation before DDL
- **Password comparison** hardening in `server_config.py`: TypeError handling, UTF-8 encoding, plain-text warning
- **Recovery codes entropy** doubled in `security/two_factor.py`: 32-bit → 64-bit
- **Error handling** in `security/licensing.py`: try/except for suspend/revoke/renew operations

### Type Hints (68 files)
- Full type annotations across all core modules, models, routes, security, licensing, and utils
- 250+ functions with return type annotations
- 120+ `to_dict()` methods typed as `-> Dict[str, Any]`

### Error Handling Improvements
- Replaced 27 silent `except Exception: pass` blocks with proper logging
- Added `log.debug()`/`log.warning()` with `exc_info=True` across 19 files

### Code Quality
- **Deduplicated `parse_date()`**: removed 11 copy-pasted definitions, centralized in `utils.pagination`
- **Replaced `datetime.utcnow()`**: 29 occurrences → `datetime.now(timezone.utc)` (Python 3.12+ compat)
- **Modern f-strings**: converted 6 old-style `%` formatting instances
- **Fixed duplicate `__all__`** entries in `models/__init__.py` (11 duplicates removed)
- **Removed duplicate `import time`** in `utils/docnum.py`

### Tests
- **261 tests** (258 passed, 3 xfailed)
- 42 new tests added for: `validation.py`, `passwords.py`, `crypto.py`, `docnum.py`

---

## [2.0.8] — Previous Release
- Initial Inno Setup installer
- Core ERP modules: Projects, Sales, Procurement, Inventory, HR, Payroll, Accounting, Real Estate, Rentals, CRM
- License management with owner protection
- Two-factor authentication
- Workflow engine with approval chains
- E-invoicing (Saudi Arabia / Egypt)
- Desktop (WebView2) + Cloud deployment support
