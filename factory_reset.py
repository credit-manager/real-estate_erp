# -*- coding: utf-8 -*-
"""Factory Reset engine for DynamicPro ERP.

Deletes ALL transactional data while preserving schema, admin user,
system settings, and core reference data. Optionally seeds demo data.
Supports both PostgreSQL (raw psycopg2) and SQLite.
"""
import logging
import config
from datetime import date, timedelta

from database import db

log = logging.getLogger(__name__)

# Tables to KEEP (never delete)
PRESERVE_TABLES = {
    "users",
    "roles",
    "system_settings",
    "master_roles",
    "master_permissions",
    "master_role_permissions",
    "module_catalog",
    "lic_plans",
    "lic_master_users",
}

DELETE_ORDER = [
    # --- Audit / Logs ---
    "audit_logs",
    "security_events",
    "master_audit_logs",
    "master_sessions",
    "master_two_factor",
    "lic_activity_log",
    "license_activity",
    # --- Notifications ---
    "notification_logs",
    "notification_queue",
    "notification_preferences",
    "notification_templates",
    "notification_channels",
    "app_notifications",
    # --- DMS ---
    "document_shares",
    "document_annotations",
    "documents",
    "document_folders",
    # --- BI ---
    "bi_filter_templates",
    "bi_dashboards",
    "bi_providers",
    # --- E-Signature ---
    "signature_audit_logs",
    "signature_requests",
    "signature_providers",
    # --- Payment Gateway ---
    "payment_refunds",
    "payment_transactions",
    "payment_method_tokens",
    "payment_gateways",
    "payment_plan_installments",
    # --- Workflow / Approvals ---
    "approval_step_records",
    "approval_requests",
    "workflow_steps",
    "workflow_templates",
    # --- PropTech / Escrow / OffPlan ---
    "escrow_transactions",
    "title_deeds",
    "dsp_plans",
    "service_charges",
    "unit_documents",
    "delivery_checklist_items",
    "tenant_screenings",
    "unit_mortgages",
    "escrow_accounts",
    "construction_milestones",
    "owner_associations",
    "real_estate_brokers",
    # --- CRM ---
    "crm_quote_items",
    "crm_contracts",
    "crm_complaints",
    "crm_tickets",
    "crm_campaign_leads",
    "crm_follow_ups",
    "crm_quotes",
    "crm_tasks",
    "crm_meetings",
    "crm_calls",
    "crm_opportunities",
    "crm_leads",
    "crm_campaigns",
    # --- Real Estate Invest ---
    "commissions",
    "sales_contracts",
    "unit_reservations",
    "unit_allocations",
    "unit_deliveries",
    "maintenance_requests",
    "unit_shares",
    "unit_price_history",
    # --- Rental ---
    "rental_payments",
    "rental_renewals",
    "rental_contracts",
    # --- Payment Plans ---
    "installments",
    "payment_plans",
    # --- Real Estate Core ---
    "real_estate_units",
    "real_estate_floors",
    "real_estate_buildings",
    "real_estate_owners",
    # --- Sales ---
    "sales_return_items",
    "sales_returns",
    "sales_commissions",
    "sales_order_items",
    "sales_orders",
    # --- Procurement ---
    "purchase_return_items",
    "purchase_returns",
    "purchase_receiving_items",
    "purchase_receivings",
    "rfq_quote_items",
    "rfq_quotes",
    "rfq_items",
    "rfqs",
    "purchase_request_items",
    "purchase_requests",
    "purchase_order_items",
    "purchase_orders",
    # --- Invoices ---
    "invoice_items",
    "invoices",
    # --- Project Management ---
    "project_quality",
    "project_site_logs",
    "project_execution_logs",
    "project_risks",
    "project_cost_items",
    "project_costs",
    "project_change_orders",
    "progress_statements",
    "project_contracts",
    "project_boq_items",
    "project_wbs_items",
    "project_price_analysis",
    "project_phases",
    "subcontractors",
    "labor_assignments",
    "equipment",
    "project_milestones",
    "project_budgets",
    "project_progress",
    "projects",
    # --- Inventory ---
    "stock_movements",
    "stock_take_items",
    "stock_takes",
    "stock_transfer_items",
    "stock_transfers",
    "stock_serials",
    "stock_batches",
    "item_stocks",
    "items",
    "item_categories",
    "units_of_measure",
    "warehouses",
    # --- Manufacturing ---
    "quality_inspections",
    "production_operations",
    "production_orders",
    "bom_lines",
    "boms",
    "raw_materials",
    "work_centers",
    # --- Assets ---
    "asset_custodies",
    "asset_movements",
    "asset_maintenance",
    "asset_items",
    "asset_categories",
    # --- Accounting ---
    "budget_lines",
    "depreciation_records",
    "fixed_assets",
    "journal_entry_lines",
    "journal_entries",
    "company_expenses",
    "cost_centers",
    "accounts",
    # --- HR / Payroll ---
    "payroll_lines",
    "payroll_runs",
    "payroll_salaries",
    "payroll_tax_brackets",
    "payroll_end_of_service",
    "payroll_bonuses",
    "payroll_deductions",
    "payroll_allowances",
    "payroll_settings",
    "hr_training_enrollments",
    "hr_trainings",
    "hr_reviews",
    "hr_loans",
    "hr_advances",
    "hr_penalties",
    "hr_leaves",
    "hr_attendance",
    "hr_contracts",
    "hr_recruitments",
    "employees",
    "departments",
    # --- Licensing ---
    "companies",
    "company_modules",
    "lic_company_users",
    "lic_database_registry",
    "lic_payments",
    "lic_subscriptions",
    "lic_licenses",
    "lic_companies",
    # --- Core Reference (will be re-seeded) ---
    "customers",
    "suppliers",
    "financial_years",
    "tax_types",
    "currencies",
    "exchange_rate_history",
    "hr_departments",
    "hr_positions",
    "unit_types",
    "crm_pipeline_stages",
    "crm_pipelines",
]


def _get_raw_conn():
    return db.engine.raw_connection()


def _table_exists(raw_conn, table_name):
    is_sqlite = config.IS_FROZEN
    try:
        cur = raw_conn.cursor()
        if is_sqlite:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name=?)",
                (table_name,),
            )
        else:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = %s)",
                (table_name,),
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
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
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
        cur.execute(f'DELETE FROM "{table_name}"')
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
        for table_name in DELETE_ORDER:
            count = _count_table(raw_conn, table_name)
            if count > 0:
                preview.append({"table": table_name, "count": count})
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
    is_sqlite = config.IS_FROZEN

    def _exec(sql, params=None):
        try:
            if is_sqlite and params:
                # SQLite uses ? for parameters
                sql = sql.replace("%s", "?")
            cur.execute(sql, params or ())
        except Exception:
            try:
                raw_conn.rollback()
            except Exception:
                pass

    # Currency
    _exec(
        "INSERT INTO currencies (id, company_id, code, name, symbol, rate, is_base, is_active) "
        "VALUES (1, 1, 'EGP', %s, 'ج.م', 1.0, true, true) "
        "ON CONFLICT (id) DO NOTHING",
        ("جنيه مصري",),
    )

    # Financial Year
    _exec(
        "INSERT INTO financial_years (id, company_id, name, start_date, end_date, is_active, is_closed) "
        "VALUES (1, 1, '2026', '2026-01-01', '2026-12-31', true, false) "
        "ON CONFLICT (id) DO NOTHING",
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
            (i, name, ctype, phone, email, addr),
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
            (i, name, contact, phone, cat),
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
            (i, name, dept, pos, "055%07d" % i, salary),
        )

    cur.close()
    raw_conn.commit()
    log.info("Demo data seeded successfully")


def factory_reset(seed_demo=True):
    deleted = []
    total_deleted = 0
    is_sqlite = config.IS_FROZEN

    try:
        db.session.rollback()
    except Exception:
        pass

    raw_conn = _get_raw_conn()
    try:
        cur = raw_conn.cursor()

        if is_sqlite:
            # ── SQLite: get all tables from sqlite_master ──
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            all_tables = [r[0] for r in cur.fetchall()]
        else:
            # ── PostgreSQL: get all public tables ──
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
            all_tables = [r[0] for r in cur.fetchall()]

        # Delete from all tables
        for table_name in all_tables:
            if table_name in PRESERVE_TABLES:
                continue
            count_before = _count_table(raw_conn, table_name)
            if count_before == 0:
                continue
            try:
                cur2 = raw_conn.cursor()
                if is_sqlite:
                    # SQLite: disable foreign keys temporarily, then DELETE
                    cur2.execute("PRAGMA foreign_keys = OFF")
                    cur2.execute(f'DELETE FROM "{table_name}"')
                    cur2.execute("PRAGMA foreign_keys = ON")
                else:
                    # PostgreSQL: TRUNCATE CASCADE
                    cur2.execute(f'TRUNCATE TABLE "{table_name}" CASCADE')
                cur2.close()
                deleted.append({"table": table_name, "count": count_before})
                total_deleted += count_before
                log.info("Cleared %s (%d rows)", table_name, count_before)
            except Exception:
                raw_conn.rollback()
                # Fallback to DELETE
                count = _delete_table(raw_conn, table_name)
                if count > 0:
                    deleted.append({"table": table_name, "count": count})
                    total_deleted += count

        cur.close()
        raw_conn.commit()

        if not is_sqlite:
            # Reset sequences for key tables (PostgreSQL only)
            for seq_table in ["customers", "suppliers", "employees", "invoices",
                              "purchase_orders", "rental_contracts", "projects",
                              "real_estate_units", "journal_entries", "accounts"]:
                try:
                    cur = raw_conn.cursor()
                    cur.execute(f"SELECT setval(pg_get_serial_sequence('{seq_table}', 'id'), 1, false)")
                    cur.close()
                except Exception:
                    try:
                        raw_conn.rollback()
                    except Exception:
                        pass
        else:
            # SQLite: reset autoincrement counters
            try:
                cur = raw_conn.cursor()
                cur.execute("DELETE FROM sqlite_sequence")
                cur.close()
                raw_conn.commit()
            except Exception:
                pass

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
