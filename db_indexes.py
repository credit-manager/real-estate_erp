"""فهارس قاعدة البيانات لتحسين أداء الاستعلامات.

تُنشئ فهارس على الأعمدة الأكثر استخداماً في الاستعلامات (الأعمدة الأجنبية،
حالة المستند، والتواريخ) للجداول عالية الحجم. الدالة idempotent: تُشغَّل عند
كل إقلاع وتتخطى الفهارس الموجودة، ولا يلزم التدخل يدوياً لقواعد البيانات
القديمة أو الجديدة.
"""
from sqlalchemy import inspect, text
import hashlib

# {اسم الجدول: [الأعمدة]} - أعمدة فقط موجودة في الموديلات
INDEXES = {
    # فواتير - مشتريات
    "invoices": ["customer_id", "supplier_id", "project_id", "financial_year_id", "status", "issue_date", "created_at"],
    "invoice_items": ["invoice_id", "item_id", "warehouse_id"],
    "purchase_orders": ["supplier_id", "project_id", "financial_year_id", "status", "order_date", "created_at"],
    "purchase_order_items": ["purchase_order_id"],
    "purchase_requests": ["project_id", "status"],
    "purchase_request_items": ["purchase_request_id"],
    "purchase_receivings": ["po_id", "status"],
    "purchase_receiving_items": ["receiving_id"],
    "purchase_returns": ["po_id", "supplier_id", "status"],
    "purchase_return_items": ["return_id"],
    "rfqs": ["project_id", "status"],
    "rfq_items": ["rfq_id"],
    "rfq_quotes": ["rfq_id", "supplier_id"],
    "rfq_quote_items": ["quote_id", "rfq_item_id"],
    # مبيعات
    "sales_orders": ["customer_id", "salesperson_id", "financial_year_id", "status", "order_date", "created_at"],
    "sales_order_items": ["sales_order_id"],
    "sales_returns": ["invoice_id", "customer_id", "financial_year_id", "status"],
    "sales_return_items": ["sales_return_id"],
    "sales_commissions": ["salesperson_id", "order_id", "invoice_id", "status"],
    # محاسبة
    "journal_entries": ["financial_year_id", "created_by", "status", "date"],
    "journal_entry_lines": ["entry_id", "account_id", "cost_center_id"],
    "budget_lines": ["financial_year_id", "account_id"],
    "fixed_assets": ["status", "account_id", "expense_account_id"],
    "depreciation_records": ["asset_id", "entry_id", "date"],
    # مخزون
    "items": ["category_id", "unit_id"],
    "item_stocks": ["item_id", "warehouse_id"],
    "stock_batches": ["item_id", "warehouse_id"],
    "stock_serials": ["item_id", "warehouse_id", "status"],
    "stock_movements": ["item_id", "warehouse_id", "batch_id", "created_at"],
    "stock_transfers": ["from_warehouse_id", "to_warehouse_id", "status"],
    "stock_transfer_items": ["transfer_id", "item_id"],
    "stock_takes": ["warehouse_id", "status"],
    "stock_take_items": ["take_id", "item_id"],
    "raw_materials": ["item_id", "supplier_id"],
    # عقارات
    "real_estate_units": ["project_id", "building_id", "floor_id", "unit_type_id", "status"],
    "real_estate_buildings": ["project_id"],
    "real_estate_floors": ["building_id"],
    "payment_plans": ["unit_id", "customer_id", "financial_year_id", "status"],
    "installments": ["plan_id", "status", "due_date"],
    "sales_contracts": ["unit_id", "customer_id", "payment_plan_id", "status"],
    "rental_contracts": ["unit_id", "customer_id", "financial_year_id", "status"],
    "rental_payments": ["contract_id", "financial_year_id"],
    "rental_renewals": ["contract_id", "financial_year_id"],
    "unit_reservations": ["unit_id", "customer_id", "status"],
    "unit_allocations": ["unit_id", "customer_id", "status"],
    "unit_deliveries": ["unit_id", "customer_id", "status"],
    "unit_price_history": ["unit_id"],
    "unit_shares": ["unit_id", "owner_id"],
    "maintenance_requests": ["unit_id", "customer_id", "status", "assigned_to"],
    "commissions": ["contract_id", "unit_id", "employee_id", "customer_id", "status"],
    # موظفون - رواتب
    "employees": ["department_id", "position_id", "manager_id", "user_id", "status"],
    "hr_attendance": ["employee_id", "date", "status"],
    "hr_leaves": ["employee_id", "status"],
    "hr_advances": ["employee_id", "status"],
    "hr_loans": ["employee_id", "status"],
    "hr_contracts": ["employee_id", "status"],
    "hr_penalties": ["employee_id"],
    "hr_reviews": ["employee_id", "status"],
    "hr_recruitments": ["position_id", "department_id", "status"],
    "hr_training_enrollments": ["training_id", "employee_id"],
    "payroll_runs": ["status", "created_by"],
    "payroll_lines": ["run_id", "employee_id", "status"],
    "payroll_salaries": ["employee_id"],
    "payroll_allowances": ["employee_id"],
    "payroll_bonuses": ["employee_id"],
    "payroll_deductions": ["employee_id"],
    "payroll_end_of_service": ["employee_id", "status"],
    # الموافقات - السجل
    "approval_requests": ["template_id", "status", "submitted_by", "decided_by"],
    "approval_step_records": ["request_id", "step_id", "approver_id", "status"],
    "audit_logs": ["user_id", "created_at"],
    # موبايل
    "mobile_field_visits": ["user_id", "customer_id", "unit_id", "status", "scheduled_date"],
    "mobile_gps_locations": ["user_id", "employee_id", "recorded_at"],
    "mobile_device_tokens": ["user_id"],
    "mobile_app_notifications": ["user_id", "created_at"],
    # أصول
    "asset_items": ["category_id", "location_id", "supplier_id", "status", "assigned_employee_id", "account_id"],
    "asset_movements": ["asset_id", "movement_date", "from_location_id", "to_location_id"],
    "asset_maintenance": ["asset_id", "status"],
    "asset_custodies": ["asset_id", "employee_id", "status"],
    # تصنيع
    "production_orders": ["product_item_id", "warehouse_id", "status", "due_date"],
    "production_operations": ["order_id", "work_center_id", "status"],
    "quality_inspections": ["order_id", "item_id", "status"],
    "boms": ["product_item_id"],
    "bom_lines": ["bom_id", "item_id"],
    # مشاريع
    "projects": ["status", "manager_id"],
    "project_contracts": ["project_id", "subcontractor_id", "status"],
    "project_costs": ["project_id"],
    "project_execution_logs": ["project_id"],
    "project_site_logs": ["project_id"],
    "project_progress": ["project_id", "boq_id"],
    "project_boq_items": ["project_id", "wbs_id", "status"],
    "project_wbs_items": ["project_id"],
    "project_quality": ["project_id", "status"],
    "project_risks": ["project_id", "status"],
    "project_phases": ["project_id", "status"],
    "progress_statements": ["contract_id", "status"],
    "project_change_orders": ["project_id", "contract_id", "status"],
    "labor_assignments": ["project_id", "employee_id", "status"],
    "equipment": ["project_id", "status"],
    # CRM
    "crm_leads": ["owner_id", "status"],
    "crm_opportunities": ["lead_id", "customer_id", "owner_id", "status"],
    "crm_quotes": ["customer_id", "lead_id", "opportunity_id", "status"],
    "crm_quote_items": ["quote_id"],
    "crm_contracts": ["customer_id", "quote_id", "status"],
    "crm_tasks": ["customer_id", "lead_id", "opportunity_id", "employee_id", "status"],
    "crm_calls": ["customer_id", "lead_id", "employee_id"],
    "crm_follow_ups": ["customer_id", "lead_id", "opportunity_id", "employee_id"],
    "crm_meetings": ["customer_id", "lead_id", "employee_id"],
    "crm_complaints": ["customer_id", "status", "assigned_to"],
    "crm_tickets": ["customer_id", "status", "assigned_to"],
    "crm_campaigns": ["owner_id", "status"],
    "crm_campaign_leads": ["campaign_id", "lead_id"],
}


def _index_name(table, cols):
    """اسم فهرس فريد لا يتجاوز حد PostgreSQL البالغ 63 حرفاً."""
    base = "ix_{}_{}".format(table, "_".join(cols))
    if len(base) <= 63:
        return base
    digest = hashlib.md5(base.encode("utf-8")).hexdigest()[:8]
    prefix = "ix_{}".format(table)[:54]
    return "{}_{}".format(prefix, digest)


def ensure_indexes(engine, session, log=print):
    """إنشاء الفهارس الناقصة للجداول المذكورة. تعمل في كل إقلاع دون تكرار."""
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    # الفهارس الموجودة حالياً (بما فيها فهارس القيود الفريدة) لكل جدول
    existing = {}
    for t in existing_tables:
        cols_set = set()
        for i in insp.get_indexes(t):
            cols_set.add(tuple(i["column_names"]))
        for u in insp.get_unique_constraints(t):
            cols_set.add(tuple(u["column_names"]))
        existing[t] = cols_set

    created, skipped, errors = 0, 0, 0
    for table, cols in INDEXES.items():
        if table not in existing_tables:
            skipped += 1
            continue
        # تخطَّى إن كان أي عمود غير موجود (حماية من انجراف الأسماء)
        table_cols = {c["name"] for c in insp.get_columns(table)}
        if not all(c in table_cols for c in cols):
            skipped += 1
            continue
        name = _index_name(table, cols)
        if tuple(cols) in existing[table]:
            skipped += 1
            continue
        try:
            ddl = "CREATE INDEX IF NOT EXISTS {} ON {} ({})".format(
                name, table, ", ".join(cols)
            )
            session.execute(text(ddl))
            created += 1
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            errors += 1
            log(f"  ! فشل إنشاء الفهرس {name}: {exc}")
    try:
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
    # log(f"\u0627\u0644\u0641\u0647\u0627\u0631\u0633: {created} \u064e\u064a\u062f\u064a\u062f {skipped} \u0645\u0648\u062c\u0648\u062f/\u0645\u062a\u062e\u0637\u0649\u060c {errors} \u0641\u0634\u0644.")  # Skipped due to Unicode encoding issue
    return created, skipped, errors
