# -*- coding: utf-8 -*-
"""Factory Reset engine for DynamicPro ERP.

Deletes all transactional data while preserving schema, admin user,
system settings, and reference data. Optionally seeds demo data.
"""
import logging
from datetime import date, timedelta

from database import db

log = logging.getLogger(__name__)

PRESERVE_TABLES = {
    "users", "roles", "system_settings",
    "hr_departments", "hr_positions", "unit_types",
    "crm_pipeline_stages", "crm_pipelines", "module_catalog",
}

DELETE_ORDER = [
    # --- Audit / Notifications / Mobile / DMS / BI / E-Sign ---
    ("audit_logs", "سجلات التدقيق"),
    ("license_activity", "نشاط الترخيص"),
    ("owner_notifications", "إشعارات المالك"),
    ("notification_logs", "سجلات الإشعارات"),
    ("notification_queue", "قائمة انتظار الإشعارات"),
    ("notification_preferences", "تفضيلات الإشعارات"),
    ("notification_templates", "قوالب الإشعارات"),
    ("notification_channels", "قنوات الإشعارات"),
    ("mobile_app_notifications", "إشعارات التطبيق"),
    ("mobile_device_tokens", "رموز الأجهزة"),
    ("mobile_gps_locations", "المواقع الجغرافية"),
    ("mobile_field_visits", "الزيارات الميدانية"),
    ("document_shares", "مشاركة المستندات"),
    ("document_annotations", "تعليقات المستندات"),
    ("documents", "المستندات"),
    ("document_folders", "مجلدات المستندات"),
    ("bi_filter_templates", "قوالب فلتر BI"),
    ("bi_dashboards", "لوحات BI"),
    ("bi_providers", "مزوّدي BI"),
    ("signature_audit_logs", "سجلات التوقيع"),
    ("signature_requests", "طلبات التوقيع"),
    ("signature_providers", "مزوّدي التوقيع"),
    # --- Payment Gateway ---
    ("payment_refunds", "استردادات الدفع"),
    ("payment_transactions", "معاملات الدفع"),
    ("payment_method_tokens", "رموز طرق الدفع"),
    ("payment_gateways", "بوابات الدفع"),
    ("payment_plan_installments", "أقساط خطط الدفع"),
    # --- Workflow / Approvals ---
    ("approval_step_records", "سجلات خطوات الاعتماد"),
    ("approval_requests", "طلبات الاعتماد"),
    ("workflow_steps", "خطوات سير العمل"),
    ("workflow_templates", "قوالب سير العمل"),
    # --- PropTech / Escrow / OffPlan ---
    ("escrow_transactions", "معاملات ESCROW"),
    ("title_deeds", "شهادات الملكية"),
    ("dsp_plans", "خطط DSP"),
    ("service_charges", "رسوم الخدمة"),
    ("unit_documents", "مستندات الوحدات"),
    ("delivery_checklist_items", "بنود قائمة التسليم"),
    ("tenant_screenings", "فحص المستأجرين"),
    ("unit_mortgages", "رهن الوحدات"),
    ("escrow_accounts", "حسابات ESCROW"),
    ("construction_milestones", "مرحلة البناء"),
    ("owner_associations", "جمعية المالكين"),
    ("real_estate_brokers", "الوسطاء العقاريون"),
    # --- CRM ---
    ("crm_quote_items", "بنود عروض CRM"),
    ("crm_contracts", "عقود CRM"),
    ("crm_complaints", "الشكاوى"),
    ("crm_tickets", "تذاكر الدعم"),
    ("crm_campaign_leads", "عملاء الحملات"),
    ("crm_follow_ups", "المتابعات"),
    ("crm_quotes", "عروض CRM"),
    ("crm_tasks", "مهام CRM"),
    ("crm_meetings", "الاجتماعات"),
    ("crm_calls", "المكالمات"),
    ("crm_opportunities", "الفرص"),
    ("crm_leads", "العملاء المحتملون"),
    ("crm_campaigns", "الحملات"),
    # --- Real Estate Invest ---
    ("commissions", "العمولات"),
    ("sales_contracts", "عقود البيع"),
    ("unit_reservations", "حجوزات الوحدات"),
    ("unit_allocations", "توزيعات الوحدات"),
    ("unit_deliveries", "تسليمات الوحدات"),
    ("maintenance_requests", "طلبات الصيانة"),
    ("unit_shares", "أسهم الوحدات"),
    ("unit_price_history", "سجل أسعار الوحدات"),
    # --- Rental ---
    ("rental_payments", "مدفوعات الإيجار"),
    ("rental_renewals", "تجديدات الإيجار"),
    ("rental_contracts", "عقود الإيجار"),
    # --- Payment Plans ---
    ("installments", "الأقساط"),
    ("payment_plans", "خطط الدفع"),
    # --- Real Estate Core ---
    ("real_estate_units", "الوحدات العقارية"),
    ("real_estate_floors", "الأدوار"),
    ("real_estate_buildings", "المباني"),
    ("real_estate_owners", "المالكون"),
    # --- Sales ---
    ("sales_return_items", "بنود مرتجعات البيع"),
    ("sales_returns", "مرتجعات البيع"),
    ("sales_commissions", "عمولات المبيعات"),
    ("sales_order_items", "بنود أوراق البيع"),
    ("sales_orders", "أوراق البيع"),
    # --- Procurement ---
    ("purchase_return_items", "بنود مرتجعات الشراء"),
    ("purchase_returns", "مرتجعات الشراء"),
    ("purchase_receiving_items", "بنود استلام الشراء"),
    ("purchase_receivings", "استلامات الشراء"),
    ("rfq_quote_items", "بنود عروض الأسعار"),
    ("rfq_quotes", "عروض أسعار الموردين"),
    ("rfq_items", "بنود طلبات عروض الأسعار"),
    ("rfqs", "طلبات عروض الأسعار"),
    ("purchase_request_items", "بنود طلبات الشراء"),
    ("purchase_requests", "طلبات الشراء"),
    ("purchase_order_items", "بنود أوامر الشراء"),
    ("purchase_orders", "أوامر الشراء"),
    # --- Invoices ---
    ("invoice_items", "بنود الفواتير"),
    ("invoices", "الفواتير"),
    # --- Project Management ---
    ("project_quality", "جودة المشاريع"),
    ("project_site_logs", "سجلات الموقع"),
    ("project_execution_logs", "سجلات التنفيذ"),
    ("project_risks", "مخاطر المشاريع"),
    ("project_cost_items", "بنود تكاليف المشاريع"),
    ("project_costs", "تكاليف المشاريع"),
    ("project_change_orders", "أوامر التغيير"),
    ("progress_statements", "بيانات التقدم"),
    ("project_contracts", "عقود المشاريع"),
    ("project_boq_items", "بنود BOQ"),
    ("project_wbs_items", "بنود WBS"),
    ("project_price_analysis", "تحليل الأسعار"),
    ("project_phases", "مراحل المشاريع"),
    ("subcontractors", "المقاولون من الباطن"),
    ("labor_assignments", "توزيع العمالة"),
    ("equipment", "المعدات"),
    ("project_milestones", "مراحل المشاريع"),
    ("project_budgets", "ميزانيات المشاريع"),
    ("project_progress", "تقدم المشاريع"),
    # --- Inventory ---
    ("stock_movements", "حركات المخزون"),
    ("stock_take_items", "بنود جرد المخزون"),
    ("stock_takes", "جرد المخزون"),
    ("stock_transfer_items", "بنود نقل المخزون"),
    ("stock_transfers", "نقل المخزون"),
    ("stock_serials", "أرقام التسلسل"),
    ("stock_batches", "دفعات المخزون"),
    ("item_stocks", "أرصدة الأصناف"),
    ("items", "الأصناف"),
    ("item_categories", "فئات الأصناف"),
    ("units_of_measure", "وحدات القياس"),
    ("warehouses", "المخازن"),
    # --- Manufacturing ---
    ("quality_inspections", "الفحوصات"),
    ("production_operations", "عمليات الإنتاج"),
    ("production_orders", "أوامر الإنتاج"),
    ("bom_lines", "بنود شجرة التصنيع"),
    ("boms", "شجرة التصنيع"),
    ("raw_materials", "المواد الخام"),
    ("work_centers", "مراكز العمل"),
    # --- Assets ---
    ("asset_custodies", "الحيازات"),
    ("asset_movements", "حركات الأصول"),
    ("asset_maintenance", "صيانة الأصول"),
    ("asset_items", "الأصول"),
    ("asset_categories", "فئات الأصول"),
    # --- Accounting ---
    ("budget_lines", "بنود الميزانية"),
    ("depreciation_records", "سجلات الإهلاك"),
    ("fixed_assets", "الأصول الثابتة"),
    ("journal_entry_lines", "بنود القيود اليومية"),
    ("journal_entries", "القيود اليومية"),
    ("company_expenses", "مصروفات الشركة"),
    ("cost_centers", "مراكز التكلفة"),
    ("accounts", "الحسابات"),
    # --- HR ---
    ("payroll_lines", "بنود الرواتب"),
    ("payroll_runs", "تشغيلات الرواتب"),
    ("payroll_salaries", "رواتب الموظفين"),
    ("payroll_tax_brackets", "شرائح ضريبة الرواتب"),
    ("payroll_end_of_service", "مستحقات نهاية الخدمة"),
    ("payroll_bonuses", "المكافآت"),
    ("payroll_deductions", "الخصومات"),
    ("payroll_allowances", "البدلات"),
    ("payroll_settings", "إعدادات الرواتب"),
    ("hr_training_enrollments", "تسجيلات التدريب"),
    ("hr_trainings", "برامج التدريب"),
    ("hr_reviews", "تقييمات الأداء"),
    ("hr_loans", "قروض الموظفين"),
    ("hr_advances", "سلف الموظفين"),
    ("hr_penalties", "الجزاءات"),
    ("hr_leaves", "طلبات الإجازات"),
    ("hr_attendance", "سجلات الحضور"),
    ("hr_contracts", "عقود العمل"),
    ("hr_recruitments", "التوظيف"),
    ("employees", "الموظفين"),
    ("departments", "الأقسام"),
    # --- Core ---
    ("customers", "العملاء"),
    ("suppliers", "الموردين"),
    ("projects", "المشاريع"),
    ("company_modules", "وحدات الشركة"),
    ("companies", "الشركات"),
    ("financial_years", "السنوات المالية"),
    ("tax_types", "أنواع الضرائب"),
    ("currencies", "العملات"),
    ("exchange_rate_history", "سجل أسعار الصرف"),
    ("lic_activity_log", "سجل نشاط الترخيص"),
    ("lic_company_users", "مستخدمي الشركة"),
    ("lic_payments", "مدفوعات الترخيص"),
    ("lic_subscriptions", "الاشتراكات"),
    ("licenses", "التراخيص"),
    ("lic_master_users", "المستخدمون الرئيسيون"),
    ("master_audit_logs", "سجلات التدقيق الرئيسية"),
    ("master_permissions", "أذونات الماستر"),
    ("master_role_permissions", "أذونات الأدوار"),
    ("master_sessions", "جلسات الماستر"),
    ("master_two_factor", "التحقق الثنائي"),
    ("security_events", "الأحداث الأمنية"),
    ("master_role_permissions", "أذونات الأدوار"),
]


def _get_raw_conn():
    return db.engine.raw_connection()


def _table_exists(raw_conn, table_name):
    try:
        cur = raw_conn.cursor()
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s)",
            (table_name,)
        )
        result = cur.fetchone()[0]
        cur.close()
        return result
    except Exception:
        try:
            raw_conn.rollback()
        except Exception:
            pass
        return False


def _count_table(raw_conn, table_name):
    if not _table_exists(raw_conn, table_name):
        return 0
    try:
        cur = raw_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM %s" % table_name)
        result = cur.fetchone()[0]
        cur.close()
        return result or 0
    except Exception:
        try:
            raw_conn.rollback()
        except Exception:
            pass
        return 0


def _delete_table(raw_conn, table_name):
    if not _table_exists(raw_conn, table_name):
        return 0
    try:
        cur = raw_conn.cursor()
        cur.execute("DELETE FROM %s" % table_name)
        count = cur.rowcount
        cur.close()
        return count
    except Exception:
        try:
            raw_conn.rollback()
        except Exception:
            pass
        return 0


def get_reset_preview():
    try:
        db.session.rollback()
    except Exception:
        pass
    preview = []
    total = 0
    raw_conn = _get_raw_conn()
    try:
        for table_name, desc in DELETE_ORDER:
            if table_name in PRESERVE_TABLES:
                continue
            count = _count_table(raw_conn, table_name)
            if count > 0:
                preview.append({"table": table_name, "description": desc, "count": count})
                total += count
        raw_conn.commit()
    finally:
        try:
            raw_conn.close()
        except Exception:
            pass
    return {"items": preview, "total_rows": total}


def _seed_demo_data(raw_conn):
    cur = raw_conn.cursor()
    today = date.today()

    def _exec(sql, params=None):
        try:
            cur.execute(sql, params or ())
        except Exception:
            try:
                raw_conn.rollback()
            except Exception:
                pass

    # Company
    _exec(
        "INSERT INTO companies (id, name, legal_name, tax_number, is_active) "
        "VALUES (1, %s, %s, '123456789', true) "
        "ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name",
        ('شركة بورسعيد للمقاولات', 'شركة بورسعيد للمقاولات المحدودة')
    )

    # Financial Year 2026
    _exec(
        "INSERT INTO financial_years (id, company_id, name, start_date, end_date, is_active, is_closed) "
        "VALUES (1, 1, '2026', '2026-01-01', '2026-12-31', true, false) "
        "ON CONFLICT (id) DO UPDATE SET is_active=true, is_closed=false"
    )

    # Currency
    _exec(
        "INSERT INTO currencies (id, company_id, code, name, symbol, rate, is_base, is_active) "
        "VALUES (1, 1, 'EGP', %s, 'ج.م', 1.0, true, true) "
        "ON CONFLICT (id) DO NOTHING",
        ('جنيه مصري',)
    )

    # Customers
    customers = [
        ("شركة النخبة للمقاولات", "company", "01012345678", "info@nokhba.com", "القاهرة"),
        ("مؤسسة الأفق العقارية", "company", "01098765432", "info@alofoq.com", "الإسكندرية"),
        ("عبداللهحمد العتيبي", "individual", "05011112233", "abdullah@test.com", "الرياض"),
        ("فاطمة أحمد حسن", "individual", "05022223344", "fatma@test.com", "جدة"),
        ("م. خالد محمد العلي", "individual", "05033334455", "khaled@test.com", "الدمام"),
        ("شركة البنيان للمقاولات", "company", "01055556677", "info@elbonyan.com", "المنصورة"),
        ("مؤسسة الزهراء للتجارة", "company", "01077778899", "info@zahra.com", "أسوان"),
        ("عمر سعيد القحطاني", "individual", "05044445566", "omar@test.com", "المدينة"),
        ("نورا حسن محمود", "individual", "05066667788", "noura@test.com", "طنطا"),
        ("مجموعة الفجر الاستثمارية", "company", "01088889900", "info@fajr.com", "المنيا"),
    ]
    for i, (name, ctype, phone, email, addr) in enumerate(customers, 1):
        _exec(
            "INSERT INTO customers (id, full_name, type, phone, email, address, is_active) "
            "VALUES (%s, %s, %s, %s, %s, %s, true) "
            "ON CONFLICT (id) DO UPDATE SET full_name=EXCLUDED.full_name",
            (i, name, ctype, phone, email, addr)
        )

    # Suppliers
    suppliers = [
        ("شركة الأهرام للمواد", "محمد إبراهيم", "01011112222", "مواد بناء"),
        ("مصنع النور للسبك", "حسن النور", "01033334444", "معدات"),
        ("مؤسسة البنيان", "خالد البنيان", "01055556666", "مقاول"),
        ("شركة الكهرباء العربية", "فهد العيسى", "01077778888", "خدمات"),
        ("شركة الرمال للنقل", "عمر الشهري", "01099990000", "نقل"),
    ]
    for i, (name, contact, phone, cat) in enumerate(suppliers, 1):
        _exec(
            "INSERT INTO suppliers (id, company_name, contact_name, phone, category) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (i, name, contact, phone, cat)
        )

    # Employees
    employees = [
        ("أحمد محمد علي", "الهندسة", "مهندس مدني", 18000),
        ("سارة علي حسن", "المالية", "محاسبة", 15000),
        ("خالد حسن إبراهيم", "المبيعات", "مدير مبيعات", 20000),
        ("نورا سعيد محمود", "الموارد البشرية", "أخصائية موارد بشرية", 14000),
        ("عمر خالد الشهري", "المخازن", "أمين مخزن", 9000),
    ]
    for i, (name, dept, pos, salary) in enumerate(employees, 1):
        _exec(
            "INSERT INTO employees (id, full_name, department, position, phone, salary, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'active') "
            "ON CONFLICT (id) DO NOTHING",
            (i, name, dept, pos, "055%07d" % i, salary)
        )

    # Projects
    projects = [
        ("برج النيل", "القاهرة - حي النرجس", "active", "high", 8700000, 3900000, 45, "2027-06-30"),
        ("مشروع الواحة", "الإسكندرية - أبحر", "active", "medium", 5200000, 3100000, 60, "2026-12-15"),
        ("مجمع الزهراء", "الرياض - الشاطئ", "finishing", "high", 3100000, 2800000, 90, "2026-08-20"),
        ("مدينة الرياض", "الرياض - حي الملقا", "active", "low", 12500000, 3700000, 25, "2028-01-01"),
    ]
    for i, (name, loc, status, prio, budget, spent, comp, deadline) in enumerate(projects, 1):
        _exec(
            "INSERT INTO projects (id, name, location, status, priority, budget, spent, completion, deadline) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::date) "
            "ON CONFLICT (id) DO NOTHING",
            (i, name, loc, status, prio, budget, spent, comp, deadline)
        )

    # Units
    units = [
        ("A-101", 1, "شقة", 150, 1, 2500000, "available"),
        ("A-102", 1, "شقة", 150, 1, 2500000, "reserved"),
        ("B-201", 1, "بنتهاوس", 250, 3, 5500000, "sold"),
        ("C-101", 2, "فيلا", 350, 1, 8000000, "available"),
        ("C-102", 2, "فيلا", 400, 1, 10000000, "sold"),
        ("D-101", 3, "شقة", 120, 2, 1500000, "rented"),
        ("D-102", 3, "محل", 80, 0, 1200000, "available"),
    ]
    for i, (code, proj, utype, area, floor, price, status) in enumerate(units, 1):
        _exec(
            "INSERT INTO real_estate_units (id, unit_code, project_id, unit_type, area, floor, price, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (i, code, proj, utype, area, floor, price, status)
        )

    # Invoices
    invoices = [
        ("INV-2026-001", "sales", 1, 5500000, 5500000, "paid", "بيع وحدة B-201"),
        ("INV-2026-002", "sales", 2, 10000000, 4000000, "partial", "بيع فيلا C-102"),
        ("INV-2026-003", "purchase", None, 450000, 200000, "partial", "أسمنت وحديد"),
        ("INV-2026-004", "purchase", None, 750000, 750000, "paid", "أعمال مقاولات"),
        ("INV-2026-005", "sales", 4, 3200000, 0, "pending", "حجز وحدة E-101"),
        ("INV-2026-010", "sales", 10, 9000000, 0, "pending", "بيع بنتهاوس J-102"),
    ]
    for i, (num, itype, cust, amount, paid, status, desc) in enumerate(invoices, 1):
        _exec(
            "INSERT INTO invoices (id, invoice_number, invoice_type, customer_id, amount, paid_amount, "
            "status, issue_date, description, financial_year_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1) "
            "ON CONFLICT (id) DO NOTHING",
            (i, num, itype, cust, amount, paid, status,
             (today - timedelta(days=30 - i * 3)).isoformat(), desc)
        )

    # Purchase Orders
    pos = [
        ("PO-2026-001", 1, "أسمنت - حديد تسليح", 450000, "pending"),
        ("PO-2026-002", 2, "سبائك حديد", 1200000, "approved"),
        ("PO-2026-003", 3, "طوب أحمر", 320000, "delivered"),
        ("PO-2026-004", 4, "أسلاك كهربائية", 95000, "pending"),
        ("PO-2026-005", 5, "نقل مواد", 180000, "approved"),
    ]
    for i, (num, sup, desc, total, status) in enumerate(pos, 1):
        _exec(
            "INSERT INTO purchase_orders (id, po_number, supplier_id, items_description, total, status, order_date, financial_year_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 1) "
            "ON CONFLICT (id) DO NOTHING",
            (i, num, sup, desc, total, status, (today - timedelta(days=i * 5)).isoformat())
        )

    # Rental Contracts
    rentals = [
        (1, 3, 12000, "active", "2026-01-15", "2026-12-31"),
        (6, 5, 15000, "active", "2026-02-01", "2027-01-31"),
        (11, 9, 11000, "active", "2026-03-01", "2027-02-28"),
        (15, 4, 18000, "active", "2026-01-01", "2026-12-31"),
    ]
    for i, (unit, cust, rent, status, start, end) in enumerate(rentals, 1):
        _exec(
            "INSERT INTO rental_contracts (id, contract_number, unit_id, customer_id, monthly_rent, status, start_date, end_date, financial_year_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::date, %s::date, 1) "
            "ON CONFLICT (id) DO NOTHING",
            (i, "RC-2026-%03d" % i, unit, cust, rent, status, start, end)
        )

    # Installments
    installments = [
        ("INS-2026-001", 1, 1100000, 550000, "active", "2026-01-15"),
        ("INS-2026-002", 2, 2000000, 1000000, "active", "2026-02-15"),
        ("INS-2026-003", 3, 520000, 260000, "pending", "2026-03-15"),
    ]
    for i, (num, inv, total, paid, status, due) in enumerate(installments, 1):
        _exec(
            "INSERT INTO installments (id, invoice_id, amount, paid_amount, status, due_date) "
            "VALUES (%s, %s, %s, %s, %s, %s::date) "
            "ON CONFLICT (id) DO NOTHING",
            (i, inv, total, paid, status, due)
        )

    cur.close()
    raw_conn.commit()
    log.info("Demo data seeded successfully")


def factory_reset(seed_demo=True):
    deleted = []
    total_deleted = 0

    try:
        db.session.rollback()
    except Exception:
        pass

    raw_conn = _get_raw_conn()
    try:
        for table_name, desc in DELETE_ORDER:
            if table_name in PRESERVE_TABLES:
                continue
            count = _delete_table(raw_conn, table_name)
            if count > 0:
                deleted.append({"table": table_name, "description": desc, "count": count})
                total_deleted += count
                log.info("Deleted %d rows from %s", count, table_name)

        raw_conn.commit()

        if seed_demo:
            _seed_demo_data(raw_conn)

    finally:
        try:
            raw_conn.close()
        except Exception:
            pass

    return {
        "success": True,
        "deleted": deleted,
        "total_deleted": total_deleted,
        "seeded_demo": seed_demo,
    }
