# -*- coding: utf-8 -*-
"""Factory Reset engine for DynamicPro ERP.

Deletes all transactional data while preserving schema, admin user,
system settings, and reference data. Optionally seeds demo data.

Usage:
    from factory_reset import factory_reset, get_reset_preview
    preview = get_reset_preview()
    result = factory_reset(seed_demo=True)
"""
import logging
from datetime import date, timedelta

from sqlalchemy import text
from database import db

log = logging.getLogger(__name__)

# ── Tables to DELETE (FK-safe order: children before parents) ────
# Each tuple: (table_name, description_ar)
# We use raw SQL table names to avoid import issues.
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
    ("sales_commission_items", "عمولات المبيعات"),
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
    ("asset_custodies", "ال_custodies"),
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
    ("cost_centers", "مراكز التكلفة"),
    ("accounts", "الحسابات"),
    # --- HR ---
    ("payroll_lines", "بنود الرواتب"),
    ("payroll_runs", "تشغيلات الرواتب"),
    ("end_of_service", "مستحقات نهاية الخدمة"),
    ("tax_brackets", "شرائح الضرائب"),
    ("payroll_bonuses", "المكافآت"),
    ("payroll_deductions", "الخصومات"),
    ("payroll_allowances", "البدلات"),
    ("employee_salaries", "رواتب الموظفين"),
    ("payroll_settings", "إعدادات الرواتب"),
    ("training_enrollments", "تسجيلات التدريب"),
    ("training_programs", "برامج التدريب"),
    ("performance_reviews", "تقييمات الأداء"),
    ("employee_loans", "قروض الموظفين"),
    ("employee_advances", "سلف الموظفين"),
    ("penalties", "الجزاءات"),
    ("leave_requests", "طلبات الإجازات"),
    ("attendance_records", "سجلات الحضور"),
    ("employment_contracts", "عقود العمل"),
    ("recruitments", "التوظيف"),
    # --- Core ---
    ("customers", "العملاء"),
    ("suppliers", "الموردين"),
    ("projects", "المشاريع"),
    ("employees", "الموظفين"),
    ("financial_years", "السنوات المالية"),
    ("tax_types", "أنواع الضرائب"),
    ("currencies", "العملات"),
    ("companies", "الشركات"),
    # --- Users (keep admin) ---
    # Users are handled separately: delete all except admin
]

# ── Tables to PRESERVE (never delete) ───────────────────────────
PRESERVE_TABLES = {
    "users",           # Keep admin user
    "roles",           # Keep admin/employee roles
    "system_settings", # Keep app settings
    "hr_departments",  # Keep reference departments
    "hr_positions",    # Keep reference positions
    "unit_types",      # Keep reference unit types
    "crm_pipeline_stages",  # Keep CRM pipeline
}


def _table_exists(conn, table_name):
    """Check if a table exists in the database."""
    result = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t)"
    ), {"t": table_name})
    return result.scalar()


def _count_table(conn, table_name):
    """Count rows in a table."""
    if not _table_exists(conn, table_name):
        return 0
    try:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar() or 0
    except Exception:
        return 0


def _delete_table(conn, table_name):
    """Delete all rows from a table."""
    if not _table_exists(conn, table_name):
        return 0
    try:
        result = conn.execute(text(f"DELETE FROM {table_name}"))
        return result.rowcount
    except Exception as e:
        log.warning("Failed to delete %s: %s", table_name, e)
        return 0


def get_reset_preview():
    """Return a preview of what would be deleted."""
    try:
        db.session.rollback()
    except Exception:
        pass
    preview = []
    total = 0
    with db.engine.connect() as conn:
        for table_name, desc in DELETE_ORDER:
            if table_name in PRESERVE_TABLES:
                continue
            count = _count_table(conn, table_name)
            if count > 0:
                preview.append({"table": table_name, "description": desc, "count": count})
                total += count
    return {"items": preview, "total_rows": total}


def _seed_demo_data(conn, company_id, fy_id):
    """Seed demo data after reset."""
    today = date.today()

    # ── Company (if not exists) ──
    conn.execute(text(
        "INSERT INTO companies (id, name, legal_name, tax_number, is_active) "
        "VALUES (1, 'شركة بورسعيد للمقاولات', 'شركة بورسعيد للمقاولات المحدودة', '123456789', true) "
        "ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name"
    ))

    # ── Financial Year 2026 ──
    conn.execute(text(
        "INSERT INTO financial_years (id, company_id, name, start_date, end_date, is_active, is_closed) "
        "VALUES (1, 1, '2026', '2026-01-01', '2026-12-31', true, false) "
        "ON CONFLICT (id) DO UPDATE SET is_active=true, is_closed=false"
    ))

    # ── Currency ──
    conn.execute(text(
        "INSERT INTO currencies (id, company_id, code, name, symbol, rate, is_base, is_active) "
        "VALUES (1, 1, 'EGP', 'جنيه مصري', 'ج.م', 1.0, true, true) "
        "ON CONFLICT (id) DO NOTHING"
    ))

    # ── Customers ──
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
        conn.execute(text(
            "INSERT INTO customers (id, full_name, type, phone, email, address, is_active) "
            "VALUES (:id, :name, :type, :phone, :email, :addr, true) "
            "ON CONFLICT (id) DO UPDATE SET full_name=EXCLUDED.full_name"
        ), {"id": i, "name": name, "type": ctype, "phone": phone, "email": email, "addr": addr})

    # ── Suppliers ──
    suppliers = [
        ("شركة الأهرام للمواد", "محمد إبراهيم", "01011112222", "مواد بناء"),
        ("مصنع النور للسبك", "حسن النور", "01033334444", "معدات"),
        ("مؤسسة البنيان", "خالد البنيان", "01055556666", "مقاول"),
        ("شركة الكهرباء العربية", "فهد العيسى", "01077778888", "خدمات"),
        ("شركة الرمال للنقل", "عمر الشهري", "01099990000", "نقل"),
    ]
    for i, (name, contact, phone, cat) in enumerate(suppliers, 1):
        conn.execute(text(
            "INSERT INTO suppliers (id, company_name, contact_name, phone, category) "
            "VALUES (:id, :name, :contact, :phone, :cat) "
            "ON CONFLICT (id) DO NOTHING"
        ), {"id": i, "name": name, "contact": contact, "phone": phone, "cat": cat})

    # ── Employees ──
    employees = [
        ("أحمد محمد علي", "الهندسة", "مهندس مدني", 18000),
        ("سارة علي حسن", "المالية", "محاسبة", 15000),
        ("خالد حسن إبراهيم", "المبيعات", "مدير مبيعات", 20000),
        ("نورا سعيد محمود", "الموارد البشرية", "أخصائية موارد بشرية", 14000),
        ("عمر خالد الشهري", "المخازن", "أمين مخزن", 9000),
    ]
    for i, (name, dept, pos, salary) in enumerate(employees, 1):
        conn.execute(text(
            "INSERT INTO employees (id, full_name, department, position, phone, salary, status) "
            "VALUES (:id, :name, :dept, :pos, :phone, :salary, 'active') "
            "ON CONFLICT (id) DO NOTHING"
        ), {"id": i, "name": name, "dept": dept, "pos": pos, "phone": f"055{i:07d}", "salary": salary})

    # ── Projects ──
    projects = [
        ("برج النيل", "القاهرة - حي النرجس", "active", "high", 8700000, 3900000, 45, "2027-06-30"),
        ("مشروع الواحة", "الإسكندرية - أبحر", "active", "medium", 5200000, 3100000, 60, "2026-12-15"),
        ("مجمع الزهراء", "الرياض - الشاطئ", "finishing", "high", 3100000, 2800000, 90, "2026-08-20"),
        ("مدينة الرياض", "الرياض - حي الملقا", "active", "low", 12500000, 3700000, 25, "2028-01-01"),
    ]
    for i, (name, loc, status, prio, budget, spent, comp, deadline) in enumerate(projects, 1):
        conn.execute(text(
            "INSERT INTO projects (id, name, location, status, priority, budget, spent, completion, deadline) "
            "VALUES (:id, :name, :loc, :status, :prio, :budget, :spent, :comp, CAST(:deadline AS date)) "
            "ON CONFLICT (id) DO NOTHING"
        ), {"id": i, "name": name, "loc": loc, "status": status, "prio": prio,
            "budget": budget, "spent": spent, "comp": comp, "deadline": deadline})

    # ── Real Estate Units ──
    units = [
        ("A-101", 1, "شقة", 150, 1, 2500000, "available"),
        ("A-102", 1, "شقة", 150, 1, 2500000, "reserved"),
        ("B-201", 1, "بنتهاوس", 250, 3, 5500000, "sold"),
        ("C-101", 2, "فيلا", 350, 1, 8000000, "available"),
        ("C-102", 2, "فيلا", 400, 1, 10000000, "sold"),
        ("D-101", 3, "شقة", 120, 2, 1500000, "rented"),
        ("D-102", 3, "محل", 80, 0, 1200000, "available"),
        ("E-101", 4, "شقة", 180, 5, 3200000, "reserved"),
        ("E-102", 4, "شقة", 200, 5, 4000000, "available"),
        ("F-101", 3, "شقة", 100, 1, 1100000, "available"),
        ("F-102", 3, "شقة", 130, 2, 1600000, "rented"),
        ("G-101", 4, "محل", 60, 0, 900000, "available"),
        ("G-102", 4, "محل", 90, 0, 1350000, "sold"),
        ("H-101", 2, "فيلا", 500, 1, 15000000, "available"),
        ("H-102", 2, "شقة", 180, 2, 3500000, "rented"),
        ("I-101", 1, "شقة", 160, 2, 2800000, "available"),
        ("I-102", 1, "محل", 70, 0, 1050000, "reserved"),
        ("J-101", 4, "شقة", 220, 6, 5000000, "available"),
        ("J-102", 4, "بنتهاوس", 300, 7, 9000000, "sold"),
        ("K-101", 3, "شقة", 110, 1, 1300000, "available"),
    ]
    for i, (code, proj, utype, area, floor, price, status) in enumerate(units, 1):
        conn.execute(text(
            "INSERT INTO real_estate_units (id, unit_code, project_id, unit_type, area, floor, price, status) "
            "VALUES (:id, :code, :proj, :utype, :area, :floor, :price, :status) "
            "ON CONFLICT (id) DO NOTHING"
        ), {"id": i, "code": code, "proj": proj, "utype": utype, "area": area,
            "floor": floor, "price": price, "status": status})

    # ── Invoices ──
    invoices = [
        ("INV-2026-001", "sales", 1, 5500000, 5500000, "paid", "بيع وحدة B-201"),
        ("INV-2026-002", "sales", 2, 10000000, 4000000, "partial", "بيع فيلا C-102"),
        ("INV-2026-003", "purchase", None, 450000, 200000, "partial", "أسمنت وحديد"),
        ("INV-2026-004", "purchase", None, 750000, 750000, "paid", "أعمال مقاولات"),
        ("INV-2026-005", "sales", 4, 3200000, 0, "pending", "حجز وحدة E-101"),
        ("INV-2026-006", "sales", 6, 1500000, 1500000, "paid", "بيع وحدة D-102"),
        ("INV-2026-007", "sales", 7, 1100000, 550000, "partial", "بيع وحدة F-101"),
        ("INV-2026-008", "purchase", None, 320000, 0, "pending", "طوب أحمر"),
        ("INV-2026-009", "sales", 8, 4000000, 2000000, "partial", "بيع وحدة E-102"),
        ("INV-2026-010", "sales", 10, 9000000, 0, "pending", "بيع بنتهاوس J-102"),
    ]
    for i, (num, itype, cust, amount, paid, status, desc) in enumerate(invoices, 1):
        conn.execute(text(
            "INSERT INTO invoices (id, invoice_number, invoice_type, customer_id, amount, paid_amount, "
            "status, issue_date, description, financial_year_id) "
            "VALUES (:id, :num, :itype, :cust, :amount, :paid, :status, :date, :desc, 1) "
            "ON CONFLICT (id) DO NOTHING"
        ), {"id": i, "num": num, "itype": itype, "cust": cust, "amount": amount,
            "paid": paid, "status": status, "date": today - timedelta(days=30-i*3), "desc": desc})

    # ── Purchase Orders ──
    pos = [
        ("PO-2026-001", 1, "أسمنت - حديد تسليح", 450000, "pending"),
        ("PO-2026-002", 2, "سبائك حديد", 1200000, "approved"),
        ("PO-2026-003", 3, "طوب أحمر", 320000, "delivered"),
        ("PO-2026-004", 4, "أسلاك كهربائية", 95000, "pending"),
        ("PO-2026-005", 5, "نقل مواد", 180000, "approved"),
    ]
    for i, (num, sup, desc, total, status) in enumerate(pos, 1):
        conn.execute(text(
            "INSERT INTO purchase_orders (id, po_number, supplier_id, items_description, total, status, order_date, financial_year_id) "
            "VALUES (:id, :num, :sup, :desc, :total, :status, :date, 1) "
            "ON CONFLICT (id) DO NOTHING"
        ), {"id": i, "num": num, "sup": sup, "desc": desc, "total": total,
            "status": status, "date": today - timedelta(days=i*5)})

    # ── Rental Contracts ──
    rentals = [
        (1, 3, 12000, "active", "2026-01-15", "2026-12-31"),
        (6, 5, 15000, "active", "2026-02-01", "2027-01-31"),
        (11, 9, 11000, "active", "2026-03-01", "2027-02-28"),
        (15, 4, 18000, "active", "2026-01-01", "2026-12-31"),
    ]
    for i, (unit, cust, rent, status, start, end) in enumerate(rentals, 1):
        conn.execute(text(
            "INSERT INTO rental_contracts (id, contract_number, unit_id, customer_id, monthly_rent, status, start_date, end_date, financial_year_id) "
            "VALUES (:id, :num, :unit, :cust, :rent, :status, CAST(:start AS date), CAST(:end AS date), 1) "
            "ON CONFLICT (id) DO NOTHING"
        ), {"id": i, "num": f"RC-2026-{i:03d}", "unit": unit, "cust": cust,
            "rent": rent, "status": status, "start": start, "end": end})

    conn.commit()
    log.info("Demo data seeded successfully")


def factory_reset(seed_demo=True, keep_users=True):
    """Execute factory reset.

    Args:
        seed_demo: If True, seed demo data after clearing.
        keep_users: If True, keep admin user (always True for safety).

    Returns:
        dict with results: {success, deleted_tables, total_deleted, seed_result}
    """
    deleted = []
    total_deleted = 0

    try:
        # Rollback any failed transaction before starting
        try:
            db.session.rollback()
        except Exception:
            pass

        with db.engine.connect() as conn:
            # Phase 1: Delete all data in FK-safe order
            for table_name, desc in DELETE_ORDER:
                if table_name in PRESERVE_TABLES:
                    continue
                count = _delete_table(conn, table_name)
                if count > 0:
                    deleted.append({"table": table_name, "description": desc, "count": count})
                    total_deleted += count
                    log.info("Deleted %d rows from %s", count, table_name)

            # Phase 2: Delete users except admin
            if keep_users:
                try:
                    result = conn.execute(text(
                        "DELETE FROM users WHERE username != 'admin'"
                    ))
                    if result.rowcount > 0:
                        deleted.append({"table": "users", "description": "المستخدمون (ماعدا admin)", "count": result.rowcount})
                        total_deleted += result.rowcount
                except Exception as e:
                    log.warning("Failed to clean users: %s", e)

            conn.commit()

            # Phase 3: Seed demo data if requested
            if seed_demo:
                _seed_demo_data(conn, company_id=1, fy_id=1)

        return {
            "success": True,
            "deleted": deleted,
            "total_deleted": total_deleted,
            "seeded_demo": seed_demo,
        }

    except Exception as e:
        log.error("Factory reset failed: %s", e)
        db.session.rollback()
        return {"success": False, "error": str(e)}
