from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, date
from database import db
from models import (
    Employee, PayrollSettings, EmployeeSalary, Allowance, PayrollDeduction,
    Bonus, TaxBracket, EndOfService, PayrollRun, PayrollLine,
)
from permissions import require_api, require_page
from auditlog import log_action
from utils.pagination import paged_or_cap

payroll_bp = Blueprint("payroll", __name__, url_prefix="/api/payroll")
payroll_pages_bp = Blueprint("payroll_pages", __name__)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _log(action, entity, entity_id, description):
    log_action(action, entity, entity_id, description)


def get_settings():
    st = PayrollSettings.query.first()
    if not st:
        st = PayrollSettings()
        db.session.add(st)
        db.session.commit()
    return st


def get_base_salary(employee, ref_date=None):
    """أساسي الراتب الساري في تاريخ مرجعي (أحدث سجل فعّال قبل التاريخ)."""
    rows = EmployeeSalary.query.filter_by(employee_id=employee.id).all()
    if not rows:
        return float(employee.salary or 0)
    if ref_date is None:
        ref_date = date.max
    candidates = [r for r in rows if r.effective_date is None or r.effective_date <= ref_date]
    if not candidates:
        return float(employee.salary or 0)
    best = max(candidates, key=lambda r: r.effective_date or date.min)
    return float(best.base_salary or 0)


def compute_tax(taxable, brackets):
    """ضريبة تصاعدية على الدخل الخاضع."""
    if taxable <= 0:
        return 0.0
    ordered = sorted(brackets, key=lambda b: float(b.from_amount or 0))
    tax = 0.0
    for b in ordered:
        low = float(b.from_amount or 0)
        high = float(b.to_amount) if b.to_amount is not None else float("inf")
        if taxable <= low:
            continue
        taxable_in_bracket = min(taxable, high) - low
        if taxable_in_bracket <= 0:
            continue
        tax += taxable_in_bracket * float(b.rate or 0) / 100
        if high == float("inf"):
            break
    return round(tax, 2)


def compute_allowances(employee, base):
    items = []
    total = 0.0
    for a in Allowance.query.filter_by(employee_id=employee.id).all():
        if a.is_percentage:
            amount = round(base * float(a.percentage or 0) / 100, 2)
        else:
            amount = round(float(a.amount or 0), 2)
        items.append({"id": a.id, "name": a.name, "amount": amount})
        total += amount
    return items, round(total, 2)


def compute_deductions(employee, base):
    items = []
    total = 0.0
    for d in PayrollDeduction.query.filter_by(employee_id=employee.id).all():
        if d.is_percentage:
            amount = round(base * float(d.percentage or 0) / 100, 2)
        else:
            amount = round(float(d.amount or 0), 2)
        items.append({"id": d.id, "name": d.name, "amount": amount})
        total += amount
    return items, round(total, 2)


def compute_line(employee, settings, from_date, to_date):
    """حساب سطر راتب كامل لموظف ضمن فترة."""
    base = get_base_salary(employee, to_date)

    allowances, allowance_total = compute_allowances(employee, base)
    deductions, deduction_total = compute_deductions(employee, base)

    bonus_items = []
    bonus_total = 0.0
    q = Bonus.query.filter_by(employee_id=employee.id)
    if from_date:
        q = q.filter(db.func.coalesce(Bonus.bonus_date, Bonus.created_at.cast(db.Date)) >= from_date)
    if to_date:
        q = q.filter(db.func.coalesce(Bonus.bonus_date, Bonus.created_at.cast(db.Date)) <= to_date)
    for b in q.all():
        amt = round(float(b.amount or 0), 2)
        bonus_items.append({"id": b.id, "name": b.name, "amount": amt})
        bonus_total += amt

    penalties_total = 0.0
    if from_date and to_date:
        from models.hr import Penalty
        for p in Penalty.query.filter(
            Penalty.employee_id == employee.id,
            Penalty.penalty_date >= from_date,
            Penalty.penalty_date <= to_date,
        ).all():
            penalties_total += float(p.amount or 0)
    penalties_total = round(penalties_total, 2)

    loan_installment = 0.0
    from models.hr import EmployeeLoan
    for ln in EmployeeLoan.query.filter(
        EmployeeLoan.employee_id == employee.id,
        EmployeeLoan.status.in_(["open", "partial"]),
    ).all():
        loan_installment += float(ln.installment_amount or 0)
    loan_installment = round(loan_installment, 2)

    gross = round(base + allowance_total + bonus_total, 2)

    ceiling = float(settings.insurance_ceiling or 0)
    insurance_base = min(base, ceiling) if ceiling > 0 else base
    insurance = round(insurance_base * float(settings.insurance_employee_rate or 0) / 100, 2)

    taxable = max(0.0, gross - float(settings.tax_exempt or 0))
    tax = compute_tax(taxable, TaxBracket.query.all())

    total_deductions = round(
        deduction_total + penalties_total + loan_installment + insurance + tax, 2
    )
    net = round(gross - total_deductions, 2)

    return {
        "employee_id": employee.id,
        "base_salary": round(base, 2),
        "allowances": allowances,
        "allowance_total": allowance_total,
        "bonuses": bonus_items,
        "bonus_total": round(bonus_total, 2),
        "deductions": deductions,
        "deduction_total": deduction_total,
        "penalties_total": penalties_total,
        "loan_installment": loan_installment,
        "insurance": insurance,
        "tax": tax,
        "gross": gross,
        "total_deductions": total_deductions,
        "net": net,
    }


def _run_totals(run):
    lines = PayrollLine.query.filter_by(run_id=run.id).all()
    run.total_gross = sum(float(l.gross or 0) for l in lines)
    run.total_deductions = sum(float(l.total_deductions or 0) for l in lines)
    run.total_net = sum(float(l.net or 0) for l in lines)
    run.employees_count = len(lines)
    db.session.commit()


# ============ صفحات (Pages) ============

@payroll_pages_bp.route("/hr/payroll")
@require_page("payroll")
def page_payroll():
    return render_template("hr_payroll.html")


@payroll_pages_bp.route("/hr/salaries")
@require_page("payroll")
def page_salaries():
    return render_template("hr_salaries.html")


@payroll_pages_bp.route("/hr/allowances")
@require_page("payroll")
def page_allowances():
    return render_template("hr_allowances.html")


@payroll_pages_bp.route("/hr/deductions")
@require_page("payroll")
def page_deductions():
    return render_template("hr_deductions.html")


@payroll_pages_bp.route("/hr/bonuses")
@require_page("payroll")
def page_bonuses():
    return render_template("hr_bonuses.html")


@payroll_pages_bp.route("/hr/taxes")
@require_page("payroll")
def page_taxes():
    return render_template("hr_taxes.html")


@payroll_pages_bp.route("/hr/insurance")
@require_page("payroll")
def page_insurance():
    return render_template("hr_insurance.html")


@payroll_pages_bp.route("/hr/end-of-service")
@require_page("payroll")
def page_end_of_service():
    return render_template("hr_eos.html")


# ============ الإعدادات (تأمينات + ضرائب عامة) ============

@payroll_bp.route("/settings", methods=["GET"])
@require_api("payroll", "view")
def get_settings_api():
    return jsonify(get_settings().to_dict())


@payroll_bp.route("/settings", methods=["PUT"])
@require_api("payroll", "edit")
def update_settings():
    data = request.get_json(silent=True) or {}
    st = get_settings()
    for field in [
        "insurance_employee_rate", "insurance_employer_rate", "insurance_ceiling",
        "tax_exempt", "gratuity_per_year_days", "gratuity_after_five_days",
    ]:
        if field in data:
            try:
                setattr(st, field, float(data.get(field) or 0))
            except (ValueError, TypeError):
                pass
    db.session.commit()
    _log("update", "payroll_settings", st.id, "settings updated")
    return jsonify(st.to_dict())


# ============ هيكل الرواتب ============

@payroll_bp.route("/salaries", methods=["GET"])
@require_api("payroll", "view")
def list_salaries():
    q = EmployeeSalary.query.order_by(EmployeeSalary.id)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@payroll_bp.route("/salaries", methods=["POST"])
@require_api("payroll", "create")
def create_salary():
    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    if not employee_id:
        return jsonify({"message": "الموظف مطلوب", "error_key": "payroll.employeeRequired"}), 400
    eff = parse_date(data.get("effective_date"))
    base_salary = float(data.get("base_salary") or 0)
    notes = data.get("notes") or ""
    # تحديث سجل بنفس تاريخ السريان، وإلا إنشاء سجل تاريخي جديد
    existing = None
    for r in EmployeeSalary.query.filter_by(employee_id=employee_id).all():
        if (r.effective_date is None and eff is None) or (r.effective_date == eff):
            existing = r
            break
    if existing:
        existing.base_salary = base_salary
        existing.effective_date = eff
        existing.notes = notes
        db.session.commit()
        _log("update", "payroll_salary", existing.id, "salary updated")
        return jsonify(existing.to_dict())
    rec = EmployeeSalary(
        employee_id=employee_id,
        base_salary=base_salary,
        effective_date=eff,
        notes=notes,
    )
    db.session.add(rec)
    db.session.commit()
    _log("create", "payroll_salary", rec.id, "salary created")
    return jsonify(rec.to_dict()), 201


@payroll_bp.route("/salaries/<int:salary_id>", methods=["PUT"])
@require_api("payroll", "edit")
def update_salary(salary_id):
    rec = EmployeeSalary.query.get_or_404(salary_id)
    data = request.get_json(silent=True) or {}
    if "base_salary" in data:
        rec.base_salary = float(data.get("base_salary") or 0)
    if "effective_date" in data:
        rec.effective_date = parse_date(data.get("effective_date"))
    if "notes" in data:
        rec.notes = data.get("notes") or ""
    db.session.commit()
    _log("update", "payroll_salary", rec.id, "salary updated")
    return jsonify(rec.to_dict())


@payroll_bp.route("/salaries/<int:salary_id>", methods=["DELETE"])
@require_api("payroll", "delete")
def delete_salary(salary_id):
    rec = EmployeeSalary.query.get_or_404(salary_id)
    db.session.delete(rec)
    db.session.commit()
    _log("delete", "payroll_salary", salary_id, "salary deleted")
    return jsonify({"success": True})


# ============ البدلات ============

@payroll_bp.route("/allowances", methods=["GET"])
@require_api("payroll", "view")
def list_allowances():
    q = Allowance.query.order_by(Allowance.employee_id)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@payroll_bp.route("/allowances", methods=["POST"])
@require_api("payroll", "create")
def create_allowance():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "الموظف مطلوب", "error_key": "payroll.employeeRequired"}), 400
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم البدل مطلوب", "error_key": "payroll.nameRequired"}), 400
    a = Allowance(
        employee_id=data.get("employee_id"),
        name=data.get("name").strip(),
        amount=float(data.get("amount") or 0),
        is_percentage=bool(data.get("is_percentage")),
        percentage=float(data.get("percentage") or 0),
        notes=data.get("notes") or "",
    )
    db.session.add(a)
    db.session.commit()
    _log("create", "payroll_allowance", a.id, "allowance created")
    return jsonify(a.to_dict()), 201


@payroll_bp.route("/allowances/<int:allowance_id>", methods=["PUT"])
@require_api("payroll", "edit")
def update_allowance(allowance_id):
    a = Allowance.query.get_or_404(allowance_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "name", "amount", "is_percentage", "percentage", "notes"]:
        if field in data:
            if field == "is_percentage":
                a.is_percentage = bool(data[field])
            elif field in ("amount", "percentage"):
                setattr(a, field, float(data[field] or 0))
            else:
                setattr(a, field, data[field])
    db.session.commit()
    _log("update", "payroll_allowance", a.id, "allowance updated")
    return jsonify(a.to_dict())


@payroll_bp.route("/allowances/<int:allowance_id>", methods=["DELETE"])
@require_api("payroll", "delete")
def delete_allowance(allowance_id):
    a = Allowance.query.get_or_404(allowance_id)
    db.session.delete(a)
    db.session.commit()
    _log("delete", "payroll_allowance", allowance_id, "allowance deleted")
    return jsonify({"success": True})


# ============ الخصومات ============

@payroll_bp.route("/deductions", methods=["GET"])
@require_api("payroll", "view")
def list_deductions():
    q = PayrollDeduction.query.order_by(PayrollDeduction.employee_id)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@payroll_bp.route("/deductions", methods=["POST"])
@require_api("payroll", "create")
def create_deduction():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "الموظف مطلوب", "error_key": "payroll.employeeRequired"}), 400
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم الخصم مطلوب", "error_key": "payroll.nameRequired"}), 400
    d = PayrollDeduction(
        employee_id=data.get("employee_id"),
        name=data.get("name").strip(),
        amount=float(data.get("amount") or 0),
        is_percentage=bool(data.get("is_percentage")),
        percentage=float(data.get("percentage") or 0),
        notes=data.get("notes") or "",
    )
    db.session.add(d)
    db.session.commit()
    _log("create", "payroll_deduction", d.id, "deduction created")
    return jsonify(d.to_dict()), 201


@payroll_bp.route("/deductions/<int:deduction_id>", methods=["PUT"])
@require_api("payroll", "edit")
def update_deduction(deduction_id):
    d = PayrollDeduction.query.get_or_404(deduction_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "name", "amount", "is_percentage", "percentage", "notes"]:
        if field in data:
            if field == "is_percentage":
                d.is_percentage = bool(data[field])
            elif field in ("amount", "percentage"):
                setattr(d, field, float(data[field] or 0))
            else:
                setattr(d, field, data[field])
    db.session.commit()
    _log("update", "payroll_deduction", d.id, "deduction updated")
    return jsonify(d.to_dict())


@payroll_bp.route("/deductions/<int:deduction_id>", methods=["DELETE"])
@require_api("payroll", "delete")
def delete_deduction(deduction_id):
    d = PayrollDeduction.query.get_or_404(deduction_id)
    db.session.delete(d)
    db.session.commit()
    _log("delete", "payroll_deduction", deduction_id, "deduction deleted")
    return jsonify({"success": True})


# ============ المكافآت ============

@payroll_bp.route("/bonuses", methods=["GET"])
@require_api("payroll", "view")
def list_bonuses():
    q = Bonus.query.order_by(Bonus.bonus_date.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@payroll_bp.route("/bonuses", methods=["POST"])
@require_api("payroll", "create")
def create_bonus():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "الموظف مطلوب", "error_key": "payroll.employeeRequired"}), 400
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم المكافأة مطلوب", "error_key": "payroll.nameRequired"}), 400
    b = Bonus(
        employee_id=data.get("employee_id"),
        name=data.get("name").strip(),
        amount=float(data.get("amount") or 0),
        bonus_date=parse_date(data.get("bonus_date")),
        notes=data.get("notes") or "",
    )
    db.session.add(b)
    db.session.commit()
    _log("create", "payroll_bonus", b.id, "bonus created")
    return jsonify(b.to_dict()), 201


@payroll_bp.route("/bonuses/<int:bonus_id>", methods=["PUT"])
@require_api("payroll", "edit")
def update_bonus(bonus_id):
    b = Bonus.query.get_or_404(bonus_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "name", "amount", "bonus_date", "notes"]:
        if field in data:
            if field == "bonus_date":
                b.bonus_date = parse_date(data[field])
            elif field == "amount":
                b.amount = float(data[field] or 0)
            else:
                setattr(b, field, data[field])
    db.session.commit()
    _log("update", "payroll_bonus", b.id, "bonus updated")
    return jsonify(b.to_dict())


@payroll_bp.route("/bonuses/<int:bonus_id>", methods=["DELETE"])
@require_api("payroll", "delete")
def delete_bonus(bonus_id):
    b = Bonus.query.get_or_404(bonus_id)
    db.session.delete(b)
    db.session.commit()
    _log("delete", "payroll_bonus", bonus_id, "bonus deleted")
    return jsonify({"success": True})


# ============ شرائح الضرائب ============

def _validate_tax_bracket(from_amount, to_amount, rate, exclude_id=None):
    """تحقق من صحة الشريحة وعدم تداخلها مع الشرائح الأخرى."""
    if from_amount is None or from_amount < 0:
        return "بداية الشريحة يجب أن تكون رقماً غير سالب", "payroll.bracketFromInvalid"
    if to_amount is not None and to_amount <= from_amount:
        return "نهاية الشريحة يجب أن تكون أكبر من بدايتها", "payroll.bracketRangeInvalid"
    if rate is None or rate < 0 or rate > 100:
        return "نسبة الضريبة يجب أن تكون بين 0 و 100", "payroll.bracketRateInvalid"
    for b in TaxBracket.query.all():
        if exclude_id and b.id == exclude_id:
            continue
        other_from = float(b.from_amount or 0)
        other_to = float(b.to_amount) if b.to_amount is not None else None
        # تداخل نطاقين [from, to) مع to=None = لانهاية
        hi1 = to_amount if to_amount is not None else float("inf")
        hi2 = other_to if other_to is not None else float("inf")
        if from_amount < hi2 and other_from < hi1:
            return "هذه الشريحة تتداخل مع شريحة موجودة (من {} إلى {})".format(
                other_from, "∞" if other_to is None else other_to), "payroll.bracketOverlap"
    return None, None


@payroll_bp.route("/tax-brackets", methods=["GET"])
@require_api("payroll", "view")
def list_tax_brackets():
    return jsonify([t.to_dict() for t in TaxBracket.query.order_by(TaxBracket.from_amount).all()])


@payroll_bp.route("/tax-brackets", methods=["POST"])
@require_api("payroll", "create")
def create_tax_bracket():
    data = request.get_json(silent=True) or {}
    from_amount = float(data.get("from_amount") or 0)
    to_amount = float(data["to_amount"]) if data.get("to_amount") not in (None, "") else None
    rate = float(data.get("rate") or 0)
    msg, key = _validate_tax_bracket(from_amount, to_amount, rate)
    if msg:
        return jsonify({"message": msg, "error_key": key}), 400
    t = TaxBracket(
        from_amount=from_amount,
        to_amount=to_amount,
        rate=rate,
    )
    db.session.add(t)
    db.session.commit()
    _log("create", "payroll_tax_bracket", t.id, "tax bracket created")
    return jsonify(t.to_dict()), 201


@payroll_bp.route("/tax-brackets/<int:bracket_id>", methods=["PUT"])
@require_api("payroll", "edit")
def update_tax_bracket(bracket_id):
    t = TaxBracket.query.get_or_404(bracket_id)
    data = request.get_json(silent=True) or {}
    if "from_amount" in data:
        t.from_amount = float(data.get("from_amount") or 0)
    if "to_amount" in data:
        t.to_amount = float(data["to_amount"]) if data.get("to_amount") not in (None, "") else None
    if "rate" in data:
        t.rate = float(data.get("rate") or 0)
    from_amount = float(t.from_amount or 0)
    to_amount = float(t.to_amount) if t.to_amount is not None else None
    rate = float(t.rate or 0)
    msg, key = _validate_tax_bracket(from_amount, to_amount, rate, exclude_id=t.id)
    if msg:
        return jsonify({"message": msg, "error_key": key}), 400
    db.session.commit()
    _log("update", "payroll_tax_bracket", t.id, "tax bracket updated")
    return jsonify(t.to_dict())


@payroll_bp.route("/tax-brackets/<int:bracket_id>", methods=["DELETE"])
@require_api("payroll", "delete")
def delete_tax_bracket(bracket_id):
    t = TaxBracket.query.get_or_404(bracket_id)
    db.session.delete(t)
    db.session.commit()
    _log("delete", "payroll_tax_bracket", bracket_id, "tax bracket deleted")
    return jsonify({"success": True})


# ============ نهاية الخدمة ============

def _compute_eos(employee_id, end_date, hire_date=None):
    """حساب مكافأة نهاية الخدمة."""
    employee = Employee.query.get_or_404(employee_id)
    settings = get_settings()
    hire = hire_date or employee.hire_date
    if not hire:
        return {"error": "تاريخ التعيين غير محدد", "error_key": "payroll.hireDateRequired"}
    end = end_date or datetime.today().date()
    total_days = (end - hire).days
    years = total_days / 365.25
    per_year = float(settings.gratuity_per_year_days or 0)
    after_five = float(settings.gratuity_after_five_days or 0)
    if years <= 5:
        days = years * per_year
    else:
        days = 5 * per_year + (years - 5) * after_five
    base = get_base_salary(employee, end)
    daily = base / 30.0
    amount = round(daily * days, 2)
    return {
        "hire_date": hire.isoformat(),
        "end_date": end.isoformat(),
        "service_years": round(years, 2),
        "gratuity_days": round(days, 1),
        "base_salary": round(base, 2),
        "gratuity_amount": amount,
    }


@payroll_bp.route("/end-of-service/calculate", methods=["POST"])
@require_api("payroll", "view")
def calculate_eos():
    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    if not employee_id:
        return jsonify({"message": "الموظف مطلوب", "error_key": "payroll.employeeRequired"}), 400
    res = _compute_eos(employee_id, parse_date(data.get("end_date")), parse_date(data.get("hire_date")))
    if "error" in res:
        return jsonify(res), 400
    return jsonify(res)


@payroll_bp.route("/end-of-service", methods=["GET"])
@require_api("payroll", "view")
def list_end_of_service():
    q = EndOfService.query.order_by(EndOfService.end_date.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@payroll_bp.route("/end-of-service", methods=["POST"])
@require_api("payroll", "create")
def create_end_of_service():
    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    if not employee_id:
        return jsonify({"message": "الموظف مطلوب", "error_key": "payroll.employeeRequired"}), 400
    if data.get("auto_calculate"):
        res = _compute_eos(employee_id, parse_date(data.get("end_date")), parse_date(data.get("hire_date")))
        if "error" in res:
            return jsonify(res), 400
    else:
        res = {
            "hire_date": parse_date(data.get("hire_date")),
            "service_years": float(data.get("service_years") or 0),
            "gratuity_days": float(data.get("gratuity_days") or 0),
            "base_salary": float(data.get("base_salary") or 0),
            "gratuity_amount": float(data.get("gratuity_amount") or 0),
        }
    e = EndOfService(
        employee_id=employee_id,
        hire_date=parse_date(res.get("hire_date")),
        end_date=parse_date(data.get("end_date")) or parse_date(res.get("end_date")),
        service_years=res.get("service_years") or 0,
        gratuity_days=res.get("gratuity_days") or 0,
        base_salary=res.get("base_salary") or 0,
        gratuity_amount=res.get("gratuity_amount") or 0,
        status=data.get("status") or "draft",
        notes=data.get("notes") or "",
    )
    db.session.add(e)
    db.session.commit()
    _log("create", "payroll_eos", e.id, "end of service created")
    return jsonify(e.to_dict()), 201


@payroll_bp.route("/end-of-service/<int:eos_id>", methods=["PUT"])
@require_api("payroll", "edit")
def update_end_of_service(eos_id):
    e = EndOfService.query.get_or_404(eos_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "hire_date", "end_date", "service_years", "gratuity_days",
                  "base_salary", "gratuity_amount", "status", "notes"]:
        if field in data:
            if field in ("hire_date", "end_date"):
                setattr(e, field, parse_date(data[field]))
            elif field in ("service_years", "gratuity_days", "base_salary", "gratuity_amount"):
                setattr(e, field, float(data[field] or 0))
            else:
                setattr(e, field, data[field])
    db.session.commit()
    _log("update", "payroll_eos", e.id, "end of service updated")
    return jsonify(e.to_dict())


@payroll_bp.route("/end-of-service/<int:eos_id>", methods=["DELETE"])
@require_api("payroll", "delete")
def delete_end_of_service(eos_id):
    e = EndOfService.query.get_or_404(eos_id)
    db.session.delete(e)
    db.session.commit()
    _log("delete", "payroll_eos", eos_id, "end of service deleted")
    return jsonify({"success": True})


# ============ كشوف المرتبات ============

@payroll_bp.route("/runs", methods=["GET"])
@require_api("payroll", "view")
def list_runs():
    q = PayrollRun.query.order_by(PayrollRun.created_at.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@payroll_bp.route("/runs", methods=["POST"])
@require_api("payroll", "create")
def create_run():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    month = (data.get("month") or "").strip()
    from_date = parse_date(data.get("from_date"))
    to_date = parse_date(data.get("to_date"))
    if not name:
        return jsonify({"message": "اسم الكشف مطلوب", "error_key": "payroll.nameRequired"}), 400
    if not month and not from_date:
        return jsonify({"message": "الشهر أو الفترة مطلوبة", "error_key": "payroll.monthRequired"}), 400

    run = PayrollRun(
        name=name,
        month=month or None,
        from_date=from_date,
        to_date=to_date,
        status="draft",
    )
    db.session.add(run)
    db.session.flush()

    settings = get_settings()
    employees = Employee.query.filter(Employee.status == "active").all()
    for employee in employees:
        comp = compute_line(employee, settings, from_date, to_date)
        line = PayrollLine(run_id=run.id, **comp)
        db.session.add(line)

    db.session.commit()
    _run_totals(run)
    _log("create", "payroll_run", run.id, "payroll run created")
    return jsonify(run.to_dict()), 201


@payroll_bp.route("/runs/<int:run_id>", methods=["GET"])
@require_api("payroll", "view")
def get_run(run_id):
    run = PayrollRun.query.get_or_404(run_id)
    return jsonify({
        **run.to_dict(),
        "lines": [l.to_dict() for l in PayrollLine.query.filter_by(run_id=run_id).order_by(PayrollLine.id).all()],
    })


@payroll_bp.route("/runs/<int:run_id>", methods=["PUT"])
@require_api("payroll", "edit")
def update_run(run_id):
    run = PayrollRun.query.get_or_404(run_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        run.name = (data.get("name") or "").strip() or run.name
    if "status" in data and data.get("status") in ("draft", "finalized", "paid"):
        run.status = data["status"]
    db.session.commit()
    _log("update", "payroll_run", run.id, "payroll run status changed")
    return jsonify(run.to_dict())


@payroll_bp.route("/runs/<int:run_id>", methods=["DELETE"])
@require_api("payroll", "delete")
def delete_run(run_id):
    run = PayrollRun.query.get_or_404(run_id)
    PayrollLine.query.filter_by(run_id=run_id).delete()
    db.session.delete(run)
    db.session.commit()
    _log("delete", "payroll_run", run_id, "payroll run deleted")
    return jsonify({"success": True})


@payroll_bp.route("/runs/<int:run_id>/lines", methods=["GET"])
@require_api("payroll", "view")
def get_run_lines(run_id):
    return jsonify([l.to_dict() for l in PayrollLine.query.filter_by(run_id=run_id).all()])


@payroll_bp.route("/runs/<int:run_id>/recalculate", methods=["POST"])
@require_api("payroll", "edit")
def recalculate_run(run_id):
    run = PayrollRun.query.get_or_404(run_id)
    settings = get_settings()
    for line in PayrollLine.query.filter_by(run_id=run_id).all():
        employee = line.employee
        if not employee:
            continue
        comp = compute_line(employee, settings, run.from_date, run.to_date)
        for k, v in comp.items():
            setattr(line, k, v)
    db.session.commit()
    _run_totals(run)
    _log("update", "payroll_run", run.id, "payroll run recalculated")
    return jsonify([l.to_dict() for l in PayrollLine.query.filter_by(run_id=run_id).all()])


@payroll_bp.route("/lines/<int:line_id>", methods=["PUT"])
@require_api("payroll", "edit")
def update_line(line_id):
    line = PayrollLine.query.get_or_404(line_id)
    data = request.get_json(silent=True) or {}
    for field in ["base_salary", "allowance_total", "bonus_total", "deduction_total",
                  "penalties_total", "loan_installment", "insurance", "tax",
                  "gross", "total_deductions", "net", "status"]:
        if field == "status":
            if field in data and data[field] in ("pending", "approved"):
                line.status = data[field]
        elif field in data:
            setattr(line, field, float(data[field] or 0))
    db.session.commit()
    run = db.session.get(PayrollRun, line.run_id)
    if run:
        _run_totals(run)
    _log("update", "payroll_line", line.id, "payroll line updated")
    return jsonify(line.to_dict())
