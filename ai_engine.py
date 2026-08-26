"""Gemini AI engine for natural-language ERP queries.

Usage:
    from ai_engine import ask_ai
    answer = ask_ai("كم عدد الموظفين النشطين؟")
"""
import json
import os
import re
import textwrap

from google import genai
from google.genai import types


def _get_config():
    try:
        from server_config import load_config
        return load_config()
    except Exception:
        return {}


def _get_api_key():
    cfg = _get_config()
    return cfg.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")


def _get_model():
    cfg = _get_config()
    return cfg.get("gemini_model") or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


_system_prompt = textwrap.dedent("""\
أنت مساعد ذكي مدمج في نظام DynamicPro ERP لإدارة المبيعات والمشتريات والموارد البشرية والمحاسبة والمخزون والعقارات.

مهمتك فهم أسئلة المستخدم بالعربية أو الإنجليزية وإرجاع إجابة مختصرة ودقيقة بناءً على البيانات المتاحة في قاعدة البيانات.

قواعد مهمة:
1. أرجع الإجابة كـ JSON فقط بدون أي نص إضافي.
2. الصيغة: {"action": "<نوع الإجراء>", "params": {<المعلمات>}, "answer_hint": "<إجابة مختصرة بالعربية>"}
3. أنواع الإجراءات المتاحة:

   a) SQL_QUERY:
      استعلام SQL مباشر (SELECT فقط).
      params: {"sql": "SELECT ..."}
      مثال: {"action": "SQL_QUERY", "params": {"sql": "SELECT COUNT(*) as count FROM employees WHERE status='active'"}, "answer_hint": "عدد الموظفين النشطين"}

   b) COUNT:
      عدّ سجلات.
      params: {"table": "<اسم الجدول>", "filters": {"<عمود>": "<قيمة>"}}
      جداول متاحة: employees, customers, suppliers, projects, invoices, rental_contracts, items, warehouses, accounts, journal_entries, installments, hr_departments
      مثال: {"action": "COUNT", "params": {"table": "employees", "filters": {"status": "active"}}, "answer_hint": "عدد الموظفين النشطين"}

   c) SUM:
      مجموع مالي.
      params: {"table": "<جدول>", "column": "<عمود>", "filters": {"<عمود>": "<قيمة>"}}
      مثال: {"action": "SUM", "params": {"table": "invoices", "column": "amount", "filters": {"status": "paid"}}, "answer_hint": "إجمالي المبالغ المحصلة"}

   d) SEARCH:
      بحث في جدول معين.
      params: {"table": "<جدول>", "columns": ["<أعمدة>"], "query": "<نص البحث>", "limit": 10}
      مثال: {"action": "SEARCH", "params": {"table": "employees", "columns": ["full_name"], "query": "أحمد"}, "answer_hint": "نتائج بحث"}

   e) DASHBOARD:
      إحصائيات عامة للوحة التحكم.
      params: {}
      مثال: {"action": "DASHBOARD", "params": {}, "answer_hint": "إحصائيات لوحة التحكم"}

4. للأسئلة المالية مثل "مبلغ الخزنة" أو "المبالغ المتاخرة":
   - الخزنة: ابحث في حسابات الجدول accounts حيث is_cash = true
   - المتاخرة: ابحث في الأقساط installments حيث status = 'overdue'
   - الرواتب: ابحث في جدول_hr_payroll أو hr_salaries

5. لا تُنشئ جداول جديدة ولا تعدل البيانات - فقط SELECT.
6. إذا السؤال غير واضح، أرجع: {"action": "CLARIFY", "params": {}, "answer_hint": "يرجى توضيح السؤال"}
""")

_db_schema = textwrap.dedent("""\
أعمدة الجداول الرئيسية:

employees: id, full_name, national_id, phone, email, department, position, department_id, position_id, hire_date, salary, status(active/on_leave/terminated), employment_type, gender
hr_departments: id, name, code, manager_id, is_active
hr_positions: id, name, code, is_active
hr_attendance: id, employee_id, date, check_in, check_out, status(present/absent/late/on_leave)
hr_leaves: id, employee_id, leave_type, start_date, end_date, days, status
hr_advances: id, employee_id, amount, advance_date, paid_amount, status

customers: id, full_name, phone, email, type, company, is_active
suppliers: id, company_name, contact_name, phone, email, category
invoices: id, invoice_number, invoice_type(sales/purchase/expense), customer_id, supplier_id, amount, paid_amount, status, approval_status, financial_year_id
purchase_orders: id, order_number, supplier_id, amount, status

accounts: id, code, name, type(asset/liability/equity/revenue/expense), parent_id, is_cash, is_bank, opening_balance
journal_entries: id, entry_number, date, description, source, status
journal_entry_lines: id, entry_id, account_id, debit, credit

items: id, code, name, category_id, unit_id, cost_price, sale_price, reorder_level
item_stocks: id, item_id, warehouse_id, quantity, avg_cost
warehouses: id, code, name, location

real_estate_units: id, unit_code, unit_type, area, price, status
rental_contracts: id, contract_number, unit_id, customer_id, monthly_rent, start_date, end_date, status
rental_payments: id, contract_id, amount, payment_date, method
installments: id, plan_id, installment_number, amount, paid_amount, due_date, status(pending/paid/partial/overdue)
payment_plans: id, unit_id, total_amount, monthly_amount, months, status

projects: id, name, location, status
fixed_assets: id, asset_code, name, cost, accumulated_depreciation, status
cost_centers: id, code, name
budget_lines: id, financial_year_id, account_id, amount
""")


def ask_ai(question: str) -> dict:
    """Send a natural-language question to Gemini and return parsed JSON."""
    api_key = _get_api_key()
    model_name = _get_model()
    if not api_key:
        return {
            "success": False,
            "error": "GEMINI_API_KEY not configured",
            "answer": "يرجى إعداد مفتاح API للذكاء الصناعي من صفحة الإعدادات العامة.",
        }

    client = genai.Client(api_key=api_key)
    system_text = _system_prompt + "\n\n" + _db_schema

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=system_text,
                temperature=0.1,
                max_output_tokens=1024,
            ),
        )
        raw = response.text.strip()

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)

        parsed = json.loads(raw)
        return {"success": True, "data": parsed}

    except json.JSONDecodeError:
        return {
            "success": True,
            "data": {
                "action": "TEXT",
                "params": {},
                "answer": response.text if response else raw,
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "answer": "حدث خطأ أثناء الاتصال بخدمة الذكاء الصناعي. يرجى المحاولة مرة أخرى.",
        }
