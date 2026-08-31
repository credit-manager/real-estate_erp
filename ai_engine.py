"""Multi-provider AI engine for natural-language ERP queries.

Supports 5 providers with automatic fallback:
  1. Google Gemini  (google.genai SDK)
  2. Groq           (OpenAI-compatible REST)
  3. OpenRouter     (OpenAI-compatible REST)
  4. Cerebras       (OpenAI-compatible REST)
  5. Mistral        (OpenAI-compatible REST)

Usage:
    from ai_engine import ask_ai
    answer = ask_ai("كم عدد الموظفين النشطين؟")
"""
import json
import os
import re
import textwrap
import logging

import requests

log = logging.getLogger(__name__)

# ── Config helpers ──────────────────────────────────────────────

def _get_config():
    try:
        from server_config import load_config
        return load_config()
    except Exception:
        return {}


def _get_providers():
    """Return the ai_providers dict from config (legacy fallback)."""
    cfg = _get_config()
    providers = cfg.get("ai_providers") or {}
    # Legacy: if only gemini_api_key is set, build a single-provider dict
    if not providers:
        gemini_key = cfg.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
        if gemini_key:
            providers = {
                "gemini": {
                    "enabled": True,
                    "api_key": gemini_key,
                    "model": cfg.get("gemini_model") or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
                    "priority": 1,
                }
            }
    return providers


# ── System prompt ───────────────────────────────────────────────

_SYSTEM_PROMPT = textwrap.dedent("""\
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

_DB_SCHEMA = textwrap.dedent("""\
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


# ── Provider classes ────────────────────────────────────────────

class ProviderBase:
    """Base class for AI providers."""
    name = "base"
    requires_sdk = False

    def __init__(self, config: dict):
        self.api_key = (config.get("api_key") or "").strip()
        self.model = (config.get("model") or "").strip()
        self.priority = config.get("priority", 99)

    @property
    def is_configured(self):
        return bool(self.api_key and self.model)

    def ask(self, question: str, history: list | None = None) -> dict:
        raise NotImplementedError


class GeminiProvider(ProviderBase):
    """Google Gemini via google.genai SDK."""
    name = "gemini"
    requires_sdk = True
    default_model = "gemini-3.6-flash"

    def ask(self, question, history=None):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return {"success": False, "error": "google-genai not installed"}

        client = genai.Client(api_key=self.api_key)
        system_text = _SYSTEM_PROMPT + "\n\n" + _DB_SCHEMA

        contents = []
        for turn in (history or []):
            if not isinstance(turn, dict):
                continue
            q = (turn.get("q") or "").strip()
            a = (turn.get("a") or "").strip()
            if not q or not a:
                continue
            contents.append({"role": "user", "parts": [{"text": q}]})
            contents.append({"role": "model", "parts": [{"text": a}]})
        contents.append({"role": "user", "parts": [{"text": question}]})

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_text,
                temperature=0.1,
                max_output_tokens=1024,
            ),
        )
        text = response.text
        if not text:
            # Try candidates
            if response.candidates:
                parts = response.candidates[0].content.parts
                text = "".join(p.text for p in parts if p.text)
        return {"raw": (text or "").strip()}


class OpenAICompatProvider(ProviderBase):
    """Base for OpenAI-compatible REST API providers."""
    base_url = ""
    default_model = ""

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_messages(self, question, history):
        system_text = _SYSTEM_PROMPT + "\n\n" + _DB_SCHEMA
        messages = [{"role": "system", "content": system_text}]
        for turn in (history or []):
            if not isinstance(turn, dict):
                continue
            q = (turn.get("q") or "").strip()
            a = (turn.get("a") or "").strip()
            if not q or not a:
                continue
            messages.append({"role": "user", "content": q})
            messages.append({"role": "assistant", "content": a})
        messages.append({"role": "user", "content": question})
        return messages

    def ask(self, question, history=None):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model or self.default_model,
            "messages": self._build_messages(question, history),
            "temperature": 0.1,
            "max_tokens": 1024,
        }
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
        return {"raw": raw}


class GroqProvider(OpenAICompatProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"
    default_model = "llama-3.3-70b-versatile"


class OpenRouterProvider(OpenAICompatProvider):
    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"
    default_model = "meta-llama/llama-3.3-70b-instruct:free"

    def _headers(self):
        headers = super()._headers()
        headers["HTTP-Referer"] = "https://dynamicpro-erp.local"
        headers["X-Title"] = "DynamicPro ERP"
        return headers


class CerebrasProvider(OpenAICompatProvider):
    name = "cerebras"
    base_url = "https://api.cerebras.ai/v1"
    default_model = "gpt-oss-120b"


class MistralProvider(OpenAICompatProvider):
    name = "mistral"
    base_url = "https://api.mistral.ai/v1"
    default_model = "mistral-small-latest"


class QwenProvider(OpenAICompatProvider):
    """Qwen via Alibaba Cloud DashScope (OpenAI-compatible)."""
    name = "qwen"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    default_model = "qwen-plus"


# ── Provider registry ───────────────────────────────────────────

_PROVIDERS = {
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "cerebras": CerebrasProvider,
    "mistral": MistralProvider,
    "qwen": QwenProvider,
}


def _parse_llm_json(raw: str) -> dict:
    """Extract JSON from LLM response text."""
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)
    else:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)
    return json.loads(raw)


# ── Main entry point ────────────────────────────────────────────

def ask_ai(question: str, history=None) -> dict:
    """Send a natural-language question to the best available AI provider.

    Tries providers in priority order. Returns:
      {"success": True, "data": {...}}  on success
      {"success": False, "error": ..., "answer": ...}  on failure
    """
    providers_cfg = _get_providers()
    if not providers_cfg:
        return {
            "success": False,
            "error": "no_providers_configured",
            "answer": "لم يتم إعداد أي مزود ذكاء اصطناعي. يرجى الإعداد من صفحة إعدادات الخادم.",
        }

    # Sort by priority
    sorted_providers = sorted(
        providers_cfg.items(),
        key=lambda x: (x[1].get("priority") or 99),
    )

    last_error = None
    for name, pcfg in sorted_providers:
        if not pcfg.get("enabled"):
            continue
        provider_cls = _PROVIDERS.get(name)
        if not provider_cls:
            continue
        provider = provider_cls(pcfg)
        if not provider.is_configured:
            continue

        try:
            result = provider.ask(question, history)
            raw = result.get("raw", "")
            if not raw:
                continue

            parsed = _parse_llm_json(raw)
            return {"success": True, "data": parsed}

        except json.JSONDecodeError:
            # Model returned non-JSON text — treat as TEXT answer
            return {
                "success": True,
                "data": {
                    "action": "TEXT",
                    "params": {},
                    "answer": raw,
                },
            }
        except Exception as e:
            last_error = f"{name}: {e}"
            log.warning("AI provider %s failed: %s", name, e)
            continue

    return {
        "success": False,
        "error": last_error or "all_providers_failed",
        "answer": "حدث خطأ أثناء الاتصال بخدمة الذكاء الصناعي. يرجى المحاولة مرة أخرى.",
    }


def test_provider(name: str, api_key: str, model: str) -> dict:
    """Test a single provider with a simple question."""
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        return {"success": False, "error": f"unknown provider: {name}"}
    provider = provider_cls({"api_key": api_key, "model": model})
    if not provider.is_configured:
        return {"success": False, "error": "api_key and model are required"}
    try:
        # Use a short, simple test message (no full system prompt)
        if isinstance(provider, GeminiProvider):
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=[{"role": "user", "parts": [{"text": "Say hi in 3 words."}]}],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=20),
            )
            text = response.text
            if not text and response.candidates:
                parts = response.candidates[0].content.parts
                text = "".join(p.text for p in parts if p.text)
            raw = (text or "").strip()
        else:
            # OpenAI-compatible providers
            url = f"{provider.base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Say hi in 3 words."}],
                "temperature": 0.1,
                "max_tokens": 20,
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
        return {"success": True, "response": raw[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}
