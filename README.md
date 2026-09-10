# Dynamic Pro ERP — نظام الإدارة المتكامل

منصة ERP متعددة الأنشطة للعقارات والمقاولات وإدارة الشركات، تشمل المحاسبة، المخازن، الموارد البشرية والرواتب، المبيعات والمشتريات، التأجير، التصنيع، CRM، المشاريع، سير العمل، الأصول، التقارير، PWA وGPS.

## المتطلبات

- **Windows 10/11** لنسخة سطح المكتب.
- **Python 3.12+**.
- **PostgreSQL 16** للنشر السحابي.
- **Redis** للتحديد الموزع للمعدل والجلسات/الحماية في الإنتاج.

## إعداد الإنتاج

بيانات الاعتماد والأسرار يجب توفيرها من مدير أسرار خارجي وعدم وضعها داخل Git. يلزم في البيئة السحابية: `DB_USER` و`DB_PASSWORD` و`DB_HOST` و`DB_PORT` و`DB_NAME` و`SECRET_KEY` وRedis.

لا توجد كلمة مرور مدير ثابتة منشورة في المشروع. يمكن استخدام `DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD` أثناء التهيئة الأولى فقط، ويجب تفعيل 2FA لحساب Control Center ثم إزالة سر التهيئة.

## قاعدة البيانات والمهاجرات

إدارة مخطط PostgreSQL تتم عبر **Alembic**. سلسلة المهاجرات الحالية تصل إلى:

`0000_initial_schema → 0001_accounting_integrity → 0002_legacy_schema_alignment → 0003_financial_safety_checks → 0004_journal_cancelled_status → 0005_financial_year_integrity → 0006_journal_entry_immutability → 0007_harden_journal_delete_guards → 0008_seal_cancelled_journals`

يجب تطبيق:

```bat
alembic upgrade head
```

قبل تشغيل workers في الإنتاج. لا تعدّل migration تاريخية بعد اعتمادها؛ أضف migration جديدة لكل تغيير.

القيود المالية الأساسية أصبحت على مستوى قاعدة البيانات أيضًا: صحة السنوات المالية، توازن القيود، منع القيم السالبة، وعدم تعديل أو حذف القيود المنشورة أو الملغاة بشكل مباشر.

## التشغيل

### التطوير

```bat
start.bat
```

أو:

```bat
pip install -r requirements.txt
python app.py
```

### سطح المكتب

```bat
python desktop.py
python desktop.py --background
python desktop.py --dev
```

### الإنتاج عبر Docker

استخدم `deployment/deploy.sh` بعد تجهيز `.env` وشهادة TLS موثوقة. سكربت النشر يطبّق migrations قبل تشغيل التطبيق ويتحقق من readiness وPostgreSQL وRedis.

## الأمان

يتضمن المشروع:

- جلسات Flask قابلة للإلغاء.
- MFA/2FA للـControl Center مع pending session قبل OTP.
- Redis distributed login throttling في الإنتاج.
- CSRF للطلبات التي تغيّر الحالة.
- CORS مقيد.
- Security headers وHSTS وCSP.
- حاويات non-root و`no-new-privileges`.
- سجل تدقيق وأحداث أمنية.
- حماية tenant/company lifecycle وRBAC.

## الموبايل وGPS

يجب تشغيل GPS عبر HTTPS. سياسة المتصفح تسمح الآن بـ`geolocation=(self)` للواجهة من نفس الأصل، مع منع الكاميرا والميكروفون افتراضيًا.

## الواجهة

الواجهة الحديثة الرسمية موجودة في `frontend/` باستخدام Next.js، بينما `templates/` و`static/` تغطي الواجهات التقليدية والنسخة المحلية.

## الجودة وCI/CD

يجب أن يمر الإصدار التجاري بجميع بوابات CI/CD: lint، compilation، dependency audit، backend tests، migration smoke، frontend build/typecheck/audit، Docker build، اختبارات الأمن، واختبارات artifacts ونسخة Windows.

نجاح unit tests وحده لا يعني Commercial Ready.

## البنية الرئيسية

| المسار | الغرض |
|---|---|
| `app.py` | إنشاء التطبيق وتسجيل الوحدات |
| `config.py` | إعدادات التشغيل والأسرار |
| `runtime_hardening.py` | حواجز الإنتاج وسلامة البيانات المالية |
| `models/` | نماذج ERP |
| `routes/` | API وصفحات الوحدات |
| `frontend/` | واجهة Next.js الحديثة |
| `licensing/` | الترخيص والاشتراكات وControl Center |
| `security/` | RBAC و2FA والجلسات والتدقيق |
| `migrations/` | مخطط Alembic |
| `deployment/` | Docker/Nginx والنشر |
| `desktop.py` | تطبيق سطح المكتب |

## مبدأ التطوير

تسلسل التطوير المعتمد:

**CI → Core Hardening → Metadata Platform → Security → Financial Core → Workflow → Industry Packs → AI → Integrations → Globalization → UX → Production Scale**

لا يتوقف الإصدار عند عبارة «الفحص ناجح»؛ الهدف هو منصة ERP قابلة للتشغيل التجاري الفعلي مع سلامة البيانات، الأمن، قابلية الاسترجاع، وتكرارية النشر.