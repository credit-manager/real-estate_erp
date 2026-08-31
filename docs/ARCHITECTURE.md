# DynamicPro ERP — Architecture Roadmap (Control Center)

> قرار معماري معتمد: **تطوير البنية الحالية نحو المعمارية الجديدة** (وليس
> استبدالاً من الصفر). النظام الحالي (Flask 3.1 + SQLAlchemy + PostgreSQL)
> يعمل ومُختبَر؛ نبني عليه وحدات الأرشيتكتشر الجديدة دون هدر العمل المنجز.

---

## 1. الهدف

`ERP Control Center` = لوحة مالك/مدير المنصة التي تدير منها:
الشركات، العملاء، الباقات، التجارب، الاشتراكات، التراخيص، الوحدات،
الفوترة، قواعد البيانات، التقارير، الأمان، وسجل التدقيق.

العميل يدخل إلى **ERP شركته فقط** (Company Portal) ولا يصل إلى هذه اللوحة.

---

## 2. المعمارية المستهدفة

```text
                  ERP CONTROL CENTER (Master Admin)
                                   │
                          Master API (auth + RBAC)
                                   │
       ┌───────────────┬───────────┴───────────┬───────────────┐
       ▼               ▼                       ▼               ▼
  Companies       Licensing              Platform        Security
  Modules         Plans/Trials           Databases       Audit
  Users           Subscriptions          Versions        2FA
  Apps            Licenses/Billing       Settings        Sessions
```

**Master DB** منفصلة عن قواعد بيانات الشركات (عزل قوي بين العملاء).

---

## 3. خريطة البنية الحالية → المطلوبة

| المطلوب (تصميم جديد) | الحالي / الخطة |
|---|---|
| `licensing/` | ✅ موجود (Plans, Subscriptions, Licenses, Databases, Payments, Master/Company auth) — سيُطوَّر |
| `billing/` | 🆕 جديد (Phase 4): فوترة/تجديد/إيراد حول `LicPayment` |
| `security/` | 🆕 جديد (Phase 1+6): RBAC مركزي، JWT، TOTP 2FA، جلسات، مراقبة دخول |
| `audit/` | 🆕 جديد (Phase 6): تدقيق غني حول `LicActivityLog` |
| `notifications/` | 🆕 جديد (Phase 6+): إشعارات المنصة والشركات |
| `modules/` | 🆕 جديد (Phase 5): كتالوج وحدات بدل `plan.modules` الثابت |
| `database/` | موجود تحت `migrations/` (Alembic) — يُستكمل |
| الواجهة (Control Center) | موجودة حالياً كـ HTML/RTL في `templates/admin_panel.html` |
| البنية التحتية | 🆕 `docker-compose.yml` + `deployment/` + `.env.example` |

---

## 4. فلسفة الصلاحيات (Master Security)

لا نعتمد `if user.is_admin: allow_everything()`.
التحقق عبر: `Master User → Role → Permissions → Resource → Action`.

أمثلة على الصلاحيات بالـ dot-notation:

```
companies.view   companies.create   companies.edit   companies.suspend
licenses.create  licenses.renew     licenses.suspend licenses.revoke
subscriptions.view subscriptions.create subscriptions.extend
modules.view     modules.enable     modules.disable
```

كل عملية حساسة تمر عبر الصيغة الإلزامية:

```text
Authentication → Authorization → Validation → Business Logic → Database → Audit
```

---

## 5. سلسلة الـ Access (Subscription + License)

الوصول مسموح **فقط** عند توفر الاثنين معاً:

```text
Subscription = active      و  License = active      → ACCESS = ALLOWED
Subscription = expired     رغم License = active     → ACCESS = BLOCKED
```

(مطبَّق حالياً في `licensing.engine.can_access` — يُحافَظ عليه ويُوسَّع.)

---

## 6. خريطة المراحل

| المرحلة | المحتوى | الحالة |
|---|---|---|
| **Phase 0** | Foundation (هيكل، .env، تسجيل، docker، docs) | ✅ **هذه الجلسة** |
| **Phase 1** | Master Auth + RBAC + JWT + TOTP 2FA + Sessions | ⏳ التالية |
| **Phase 2** | Company Management + Database Registry + Lifecycle | تمت أغلبه (licensing) — يُستكمل |
| **Phase 3** | Licensing (Plans/Trials/Subscriptions/Licenses/User Limits/Modules) | أغلبها موجود |
| **Phase 4** | Billing (Payments/Invoices/Renewals/Revenue) | 🆕 |
| **Phase 5** | ERP Modules (Catalog/Company Modules/Feature Flags/Versions) | 🆕 |
| **Phase 6** | Security (Audit/Security Events/Login Monitoring/Sessions/Emergency) | 🆕 |
| **Phase 7** | Analytics (Platform/Company/Usage/Revenue/Modules/Users) | 🆕 |
| **Phase 8** | Frontend Control Center المتقدمة | تحسين تدريجي |
| **Phase 9** | Production (Docker/HTTPS/Backups/CI-CD) | البنية جاهزة — يُنشر |
| **Phase 10** | Testing (Unit/API/Security/RBAC/Tenant/License/2FA/Load) | يُبنى |

---

## 7. الفصل بين الـ APIs

```text
Master API   → /admin/*  (لوحة المالك)
Company API  → /api/*    (شركة واحدة عبر session)
Public API   → محدودة (تسجيل/تحقق)
```

Foundation only — تُكتب الوظائف الفعلية في مراحل كل وحدة.
