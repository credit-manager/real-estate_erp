from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from database import db
from models import (
    Employee, Department, Position, EmploymentContract, Recruitment,
    AttendanceRecord, LeaveRequest, Penalty, EmployeeAdvance,
    EmployeeLoan, PerformanceReview, TrainingProgram, TrainingEnrollment,
)
from permissions import require_api, require_page
from auditlog import log_action
from utils.pagination import paged_or_cap

hr_bp = Blueprint("hr", __name__, url_prefix="/api/hr")
hr_pages_bp = Blueprint("hr_pages", __name__)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _log(action, entity, entity_id, description):
    log_action(action, entity, entity_id, description)


# ============ صفحات (Pages) ============

@hr_pages_bp.route("/hr/departments")
@require_page("hr")
def hr_departments():
    return render_template("hr_departments.html")


@hr_pages_bp.route("/hr/positions")
@require_page("hr")
def hr_positions():
    return render_template("hr_positions.html")


@hr_pages_bp.route("/hr/employees")
@require_page("hr")
def hr_employees():
    return render_template("hr_employees.html")


@hr_pages_bp.route("/hr/org-chart")
@require_page("hr")
def hr_org_chart():
    return render_template("hr_org.html")


@hr_pages_bp.route("/hr/contracts")
@require_page("hr")
def hr_contracts():
    return render_template("hr_contracts.html")


@hr_pages_bp.route("/hr/recruitment")
@require_page("hr")
def hr_recruitment():
    return render_template("hr_recruitment.html")


@hr_pages_bp.route("/hr/attendance")
@require_page("hr")
def hr_attendance():
    return render_template("hr_attendance.html")


@hr_pages_bp.route("/hr/leaves")
@require_page("hr")
def hr_leaves():
    return render_template("hr_leaves.html")


@hr_pages_bp.route("/hr/penalties")
@require_page("hr")
def hr_penalties():
    return render_template("hr_penalties.html")


@hr_pages_bp.route("/hr/advances")
@require_page("hr")
def hr_advances():
    return render_template("hr_advances.html")


@hr_pages_bp.route("/hr/loans")
@require_page("hr")
def hr_loans():
    return render_template("hr_loans.html")


@hr_pages_bp.route("/hr/reviews")
@require_page("hr")
def hr_reviews():
    return render_template("hr_reviews.html")


@hr_pages_bp.route("/hr/training")
@require_page("hr")
def hr_training():
    return render_template("hr_training.html")


# ============ الأقسام ============

@hr_bp.route("/departments", methods=["GET"])
@require_api("hr", "view")
def list_departments():
    return jsonify([d.to_dict() for d in Department.query.order_by(Department.name).all()])


@hr_bp.route("/departments", methods=["POST"])
@require_api("hr", "create")
def create_department():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم القسم مطلوب"}), 400
    dept = Department(
        name=data["name"].strip(),
        code=(data.get("code") or "").strip(),
        manager_id=data.get("manager_id"),
        description=data.get("description"),
        is_active=data.get("is_active", True),
    )
    db.session.add(dept)
    db.session.commit()
    _log("create", "hr_department", dept.id, f"قسم: {dept.name}")
    return jsonify(dept.to_dict()), 201


@hr_bp.route("/departments/<int:dept_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        dept.name = data["name"].strip()
    if "code" in data:
        dept.code = data["code"].strip()
    if "manager_id" in data:
        dept.manager_id = data["manager_id"]
    if "description" in data:
        dept.description = data["description"]
    if "is_active" in data:
        dept.is_active = bool(data["is_active"])
    db.session.commit()
    _log("edit", "hr_department", dept.id, f"قسم: {dept.name}")
    return jsonify(dept.to_dict())


@hr_bp.route("/departments/<int:dept_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    name = dept.name
    db.session.delete(dept)
    db.session.commit()
    _log("delete", "hr_department", dept_id, f"قسم: {name}")
    return jsonify({"success": True})


# ============ المسميات الوظيفية ============

@hr_bp.route("/positions", methods=["GET"])
@require_api("hr", "view")
def list_positions():
    return jsonify([p.to_dict() for p in Position.query.order_by(Position.name).all()])


@hr_bp.route("/positions", methods=["POST"])
@require_api("hr", "create")
def create_position():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"message": "اسم المسمى الوظيفي مطلوب"}), 400
    pos = Position(
        name=data["name"].strip(),
        code=(data.get("code") or "").strip(),
        description=data.get("description"),
        is_active=data.get("is_active", True),
    )
    db.session.add(pos)
    db.session.commit()
    _log("create", "hr_position", pos.id, f"مسمى: {pos.name}")
    return jsonify(pos.to_dict()), 201


@hr_bp.route("/positions/<int:pos_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_position(pos_id):
    pos = Position.query.get_or_404(pos_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        pos.name = data["name"].strip()
    if "code" in data:
        pos.code = data["code"].strip()
    if "description" in data:
        pos.description = data["description"]
    if "is_active" in data:
        pos.is_active = bool(data["is_active"])
    db.session.commit()
    _log("edit", "hr_position", pos.id, f"مسمى: {pos.name}")
    return jsonify(pos.to_dict())


@hr_bp.route("/positions/<int:pos_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_position(pos_id):
    pos = Position.query.get_or_404(pos_id)
    name = pos.name
    db.session.delete(pos)
    db.session.commit()
    _log("delete", "hr_position", pos_id, f"مسمى: {name}")
    return jsonify({"success": True})


# ============ الموظفون (موسّع) ============

@hr_bp.route("/employees", methods=["GET"])
@require_api("hr", "view")
def list_employees():
    status = request.args.get("status")
    q = Employee.query
    if status:
        q = q.filter(Employee.status == status)
    q = q.order_by(Employee.full_name)
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/employees", methods=["POST"])
@require_api("hr", "create")
def create_employee():
    data = request.get_json(silent=True) or {}
    if not (data.get("full_name") or "").strip():
        return jsonify({"message": "اسم الموظف مطلوب"}), 400
    emp = Employee(
        full_name=data["full_name"].strip(),
        national_id=(data.get("national_id") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        email=(data.get("email") or "").strip(),
        address=(data.get("address") or "").strip(),
        department=(data.get("department") or "").strip(),
        position=(data.get("position") or "").strip(),
        department_id=data.get("department_id"),
        position_id=data.get("position_id"),
        manager_id=data.get("manager_id"),
        user_id=data.get("user_id"),
        gender=data.get("gender"),
        birth_date=parse_date(data.get("birth_date")),
        hire_date=parse_date(data.get("hire_date")),
        end_date=parse_date(data.get("end_date")),
        employment_type=data.get("employment_type", "full_time"),
        salary=data.get("salary", 0),
        status=data.get("status", "active"),
    )
    db.session.add(emp)
    db.session.commit()
    _log("create", "employee", emp.id, f"موظف: {emp.full_name}")
    return jsonify(emp.to_dict()), 201


@hr_bp.route("/employees/<int:employee_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_employee(employee_id):
    emp = Employee.query.get_or_404(employee_id)
    data = request.get_json(silent=True) or {}
    for field in ["full_name", "national_id", "phone", "email", "address",
                  "department", "position", "gender", "employment_type", "status"]:
        if field in data:
            setattr(emp, field, data[field])
    for field in ["department_id", "position_id", "manager_id", "salary"]:
        if field in data:
            setattr(emp, field, data[field])
    if "user_id" in data:
        setattr(emp, "user_id", data["user_id"] or None)
    for field, col in [("birth_date", "birth_date"), ("hire_date", "hire_date"), ("end_date", "end_date")]:
        if field in data:
            setattr(emp, col, parse_date(data[field]))
    db.session.commit()
    _log("edit", "employee", emp.id, f"موظف: {emp.full_name}")
    return jsonify(emp.to_dict())


@hr_bp.route("/employees/<int:employee_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_employee(employee_id):
    emp = Employee.query.get_or_404(employee_id)
    name = emp.full_name
    try:
        db.session.delete(emp)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "message": "لا يمكن حذف موظف لديه سجلات مرتبطة (رواتب، بدلات، خصومات، مكافآت، نهاية خدمة، قروض، إجازات...). احذف هذه السجلات أولاً.",
            "error_key": "hr.deleteEmployeeLinked"
        }), 400
    _log("delete", "employee", employee_id, f"موظف: {name}")
    return jsonify({"success": True})


# ============ الهيكل التنظيمي ============

@hr_bp.route("/users", methods=["GET"])
@require_api("hr", "view")
def list_linked_users():
    from models import User
    users = User.query.order_by(User.username).all()
    return jsonify([
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": bool(u.is_active),
        }
        for u in users
    ])


@hr_bp.route("/org-chart", methods=["GET"])
@require_api("hr", "view")
def org_chart():
    depts = Department.query.order_by(Department.name).all()
    employees = Employee.query.order_by(Employee.full_name).all()
    return jsonify({
        "departments": [d.to_dict() for d in depts],
        "employees": [
            {
                "id": e.id,
                "full_name": e.full_name,
                "position_name": e.hr_position.name if e.hr_position else None,
                "department_id": e.department_id,
                "manager_id": e.manager_id,
                "status": e.status,
            }
            for e in employees
        ],
    })


# ============ العقود ============

@hr_bp.route("/contracts", methods=["GET"])
@require_api("hr", "view")
def list_contracts():
    q = EmploymentContract.query.order_by(EmploymentContract.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/contracts", methods=["POST"])
@require_api("hr", "create")
def create_contract():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "اختر الموظف"}), 400
    contract = EmploymentContract(
        employee_id=data["employee_id"],
        contract_number=(data.get("contract_number") or "").strip(),
        contract_type=data.get("contract_type", "full_time"),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        salary=data.get("salary", 0),
        working_hours=data.get("working_hours", 8),
        status=data.get("status", "active"),
        notes=data.get("notes"),
    )
    db.session.add(contract)
    db.session.commit()
    _log("create", "hr_contract", contract.id, f"عقد موظف {contract.employee_id}")
    return jsonify(contract.to_dict()), 201


@hr_bp.route("/contracts/<int:contract_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_contract(contract_id):
    contract = EmploymentContract.query.get_or_404(contract_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "contract_number", "contract_type", "salary",
                  "working_hours", "status", "notes"]:
        if field in data:
            setattr(contract, field, data[field])
    for field, col in [("start_date", "start_date"), ("end_date", "end_date")]:
        if field in data:
            setattr(contract, col, parse_date(data[field]))
    db.session.commit()
    _log("edit", "hr_contract", contract.id, f"عقد {contract.contract_number}")
    return jsonify(contract.to_dict())


@hr_bp.route("/contracts/<int:contract_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_contract(contract_id):
    contract = EmploymentContract.query.get_or_404(contract_id)
    db.session.delete(contract)
    db.session.commit()
    _log("delete", "hr_contract", contract_id, "حذف عقد")
    return jsonify({"success": True})


# ============ التعيينات (استقطاب) ============

@hr_bp.route("/recruitments", methods=["GET"])
@require_api("hr", "view")
def list_recruitments():
    q = Recruitment.query.order_by(Recruitment.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/recruitments", methods=["POST"])
@require_api("hr", "create")
def create_recruitment():
    data = request.get_json(silent=True) or {}
    if not (data.get("candidate_name") or "").strip():
        return jsonify({"message": "اسم المرشح مطلوب"}), 400
    rec = Recruitment(
        candidate_name=data["candidate_name"].strip(),
        position_id=data.get("position_id"),
        department_id=data.get("department_id"),
        employee_id=data.get("employee_id"),
        phone=(data.get("phone") or "").strip(),
        email=(data.get("email") or "").strip(),
        application_date=parse_date(data.get("application_date")),
        hire_date=parse_date(data.get("hire_date")),
        salary=data.get("salary", 0),
        source=(data.get("source") or "").strip(),
        status=data.get("status", "applied"),
        notes=data.get("notes"),
    )
    db.session.add(rec)
    db.session.commit()
    _log("create", "hr_recruitment", rec.id, f"مرشح: {rec.candidate_name}")
    return jsonify(rec.to_dict()), 201


@hr_bp.route("/recruitments/<int:rec_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_recruitment(rec_id):
    rec = Recruitment.query.get_or_404(rec_id)
    data = request.get_json(silent=True) or {}
    for field in ["candidate_name", "position_id", "department_id", "employee_id",
                  "phone", "email", "salary", "source", "status", "notes"]:
        if field in data:
            setattr(rec, field, data[field])
    for field, col in [("application_date", "application_date"), ("hire_date", "hire_date")]:
        if field in data:
            setattr(rec, col, parse_date(data[field]))
    db.session.commit()
    _log("edit", "hr_recruitment", rec.id, f"مرشح: {rec.candidate_name}")
    return jsonify(rec.to_dict())


@hr_bp.route("/recruitments/<int:rec_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_recruitment(rec_id):
    rec = Recruitment.query.get_or_404(rec_id)
    db.session.delete(rec)
    db.session.commit()
    _log("delete", "hr_recruitment", rec_id, "حذف مرشح")
    return jsonify({"success": True})


# ============ الحضور والانصراف ============

@hr_bp.route("/attendance", methods=["GET"])
@require_api("hr", "view")
def list_attendance():
    date_str = request.args.get("date")
    q = AttendanceRecord.query
    if date_str:
        q = q.filter(AttendanceRecord.date == parse_date(date_str))
    q = q.order_by(AttendanceRecord.date.desc(), AttendanceRecord.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/attendance", methods=["POST"])
@require_api("hr", "create")
def create_attendance():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "اختر الموظف"}), 400
    date = parse_date(data.get("date")) or datetime.now().date()
    existing = AttendanceRecord.query.filter_by(employee_id=data["employee_id"], date=date).first()
    if existing:
        return jsonify({"message": "سجل الحضور لهذا اليوم موجود مسبقاً"}), 400
    record = AttendanceRecord(
        employee_id=data["employee_id"],
        date=date,
        check_in=(data.get("check_in") or "").strip(),
        check_out=(data.get("check_out") or "").strip(),
        status=data.get("status", "present"),
        working_hours=data.get("working_hours", 0),
        notes=data.get("notes"),
    )
    db.session.add(record)
    db.session.commit()
    _log("create", "hr_attendance", record.id, f"حضور موظف {record.employee_id}")
    return jsonify(record.to_dict()), 201


@hr_bp.route("/attendance/<int:att_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_attendance(att_id):
    record = AttendanceRecord.query.get_or_404(att_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "check_in", "check_out", "status", "working_hours", "notes"]:
        if field in data:
            setattr(record, field, data[field])
    if "date" in data:
        record.date = parse_date(data["date"]) or record.date
    db.session.commit()
    _log("edit", "hr_attendance", record.id, "تعديل حضور")
    return jsonify(record.to_dict())


@hr_bp.route("/attendance/<int:att_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_attendance(att_id):
    record = AttendanceRecord.query.get_or_404(att_id)
    db.session.delete(record)
    db.session.commit()
    _log("delete", "hr_attendance", att_id, "حذف سجل حضور")
    return jsonify({"success": True})


# ============ الإجازات ============

@hr_bp.route("/leaves", methods=["GET"])
@require_api("hr", "view")
def list_leaves():
    q = LeaveRequest.query.order_by(LeaveRequest.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/leaves", methods=["POST"])
@require_api("hr", "create")
def create_leave():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "اختر الموظف"}), 400
    start = parse_date(data.get("start_date"))
    end = parse_date(data.get("end_date"))
    leave = LeaveRequest(
        employee_id=data["employee_id"],
        leave_type=data.get("leave_type", "annual"),
        start_date=start,
        end_date=end,
        days=data.get("days") or (0 if not (start and end) else (end - start).days + 1),
        reason=data.get("reason"),
        status=data.get("status", "pending"),
    )
    db.session.add(leave)
    db.session.commit()
    _log("create", "hr_leave", leave.id, f"إجازة موظف {leave.employee_id}")
    return jsonify(leave.to_dict()), 201


@hr_bp.route("/leaves/<int:leave_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_leave(leave_id):
    leave = LeaveRequest.query.get_or_404(leave_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "leave_type", "days", "reason", "status"]:
        if field in data:
            setattr(leave, field, data[field])
    for field, col in [("start_date", "start_date"), ("end_date", "end_date")]:
        if field in data:
            setattr(leave, col, parse_date(data[field]))
    db.session.commit()
    _log("edit", "hr_leave", leave.id, f"إجازة موظف {leave.employee_id}")
    return jsonify(leave.to_dict())


@hr_bp.route("/leaves/<int:leave_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_leave(leave_id):
    leave = LeaveRequest.query.get_or_404(leave_id)
    db.session.delete(leave)
    db.session.commit()
    _log("delete", "hr_leave", leave_id, "حذف إجازة")
    return jsonify({"success": True})


# ============ الجزاءات ============

@hr_bp.route("/penalties", methods=["GET"])
@require_api("hr", "view")
def list_penalties():
    q = Penalty.query.order_by(Penalty.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/penalties", methods=["POST"])
@require_api("hr", "create")
def create_penalty():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "اختر الموظف"}), 400
    penalty = Penalty(
        employee_id=data["employee_id"],
        penalty_type=(data.get("penalty_type") or "").strip(),
        amount=data.get("amount", 0),
        penalty_date=parse_date(data.get("penalty_date")),
        reason=data.get("reason"),
    )
    db.session.add(penalty)
    db.session.commit()
    _log("create", "hr_penalty", penalty.id, f"جزاء موظف {penalty.employee_id}")
    return jsonify(penalty.to_dict()), 201


@hr_bp.route("/penalties/<int:penalty_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_penalty(penalty_id):
    penalty = Penalty.query.get_or_404(penalty_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "penalty_type", "amount", "reason"]:
        if field in data:
            setattr(penalty, field, data[field])
    if "penalty_date" in data:
        penalty.penalty_date = parse_date(data["penalty_date"])
    db.session.commit()
    _log("edit", "hr_penalty", penalty.id, f"جزاء موظف {penalty.employee_id}")
    return jsonify(penalty.to_dict())


@hr_bp.route("/penalties/<int:penalty_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_penalty(penalty_id):
    penalty = Penalty.query.get_or_404(penalty_id)
    db.session.delete(penalty)
    db.session.commit()
    _log("delete", "hr_penalty", penalty_id, "حذف جزاء")
    return jsonify({"success": True})


# ============ السلف ============

@hr_bp.route("/advances", methods=["GET"])
@require_api("hr", "view")
def list_advances():
    q = EmployeeAdvance.query.order_by(EmployeeAdvance.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/advances", methods=["POST"])
@require_api("hr", "create")
def create_advance():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "اختر الموظف"}), 400
    advance = EmployeeAdvance(
        employee_id=data["employee_id"],
        amount=data.get("amount", 0),
        advance_date=parse_date(data.get("advance_date")),
        installments=data.get("installments", 1),
        paid_amount=data.get("paid_amount", 0),
        status=data.get("status", "open"),
        reason=data.get("reason"),
    )
    db.session.add(advance)
    db.session.commit()
    _log("create", "hr_advance", advance.id, f"سلفة موظف {advance.employee_id}")
    return jsonify(advance.to_dict()), 201


@hr_bp.route("/advances/<int:advance_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_advance(advance_id):
    advance = EmployeeAdvance.query.get_or_404(advance_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "amount", "installments", "paid_amount", "status", "reason"]:
        if field in data:
            setattr(advance, field, data[field])
    if "advance_date" in data:
        advance.advance_date = parse_date(data["advance_date"])
    db.session.commit()
    _log("edit", "hr_advance", advance.id, f"سلفة موظف {advance.employee_id}")
    return jsonify(advance.to_dict())


@hr_bp.route("/advances/<int:advance_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_advance(advance_id):
    advance = EmployeeAdvance.query.get_or_404(advance_id)
    db.session.delete(advance)
    db.session.commit()
    _log("delete", "hr_advance", advance_id, "حذف سلفة")
    return jsonify({"success": True})


# ============ القروض ============

@hr_bp.route("/loans", methods=["GET"])
@require_api("hr", "view")
def list_loans():
    q = EmployeeLoan.query.order_by(EmployeeLoan.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/loans", methods=["POST"])
@require_api("hr", "create")
def create_loan():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "اختر الموظف"}), 400
    loan = EmployeeLoan(
        employee_id=data["employee_id"],
        amount=data.get("amount", 0),
        interest_rate=data.get("interest_rate", 0),
        loan_date=parse_date(data.get("loan_date")),
        installments=data.get("installments", 1),
        installment_amount=data.get("installment_amount", 0),
        paid_amount=data.get("paid_amount", 0),
        status=data.get("status", "open"),
        reason=data.get("reason"),
    )
    db.session.add(loan)
    db.session.commit()
    _log("create", "hr_loan", loan.id, f"قرض موظف {loan.employee_id}")
    return jsonify(loan.to_dict()), 201


@hr_bp.route("/loans/<int:loan_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_loan(loan_id):
    loan = EmployeeLoan.query.get_or_404(loan_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "amount", "interest_rate", "installments",
                  "installment_amount", "paid_amount", "status", "reason"]:
        if field in data:
            setattr(loan, field, data[field])
    if "loan_date" in data:
        loan.loan_date = parse_date(data["loan_date"])
    db.session.commit()
    _log("edit", "hr_loan", loan.id, f"قرض موظف {loan.employee_id}")
    return jsonify(loan.to_dict())


@hr_bp.route("/loans/<int:loan_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_loan(loan_id):
    loan = EmployeeLoan.query.get_or_404(loan_id)
    db.session.delete(loan)
    db.session.commit()
    _log("delete", "hr_loan", loan_id, "حذف قرض")
    return jsonify({"success": True})


# ============ تقييم الأداء ============

@hr_bp.route("/reviews", methods=["GET"])
@require_api("hr", "view")
def list_reviews():
    q = PerformanceReview.query.order_by(PerformanceReview.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/reviews", methods=["POST"])
@require_api("hr", "create")
def create_review():
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "اختر الموظف"}), 400
    review = PerformanceReview(
        employee_id=data["employee_id"],
        review_date=parse_date(data.get("review_date")),
        period=(data.get("period") or "").strip(),
        rating=data.get("rating", 0),
        reviewer=(data.get("reviewer") or "").strip(),
        strengths=data.get("strengths"),
        weaknesses=data.get("weaknesses"),
        goals=data.get("goals"),
        status=data.get("status", "completed"),
    )
    db.session.add(review)
    db.session.commit()
    _log("create", "hr_review", review.id, f"تقييم موظف {review.employee_id}")
    return jsonify(review.to_dict()), 201


@hr_bp.route("/reviews/<int:review_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_review(review_id):
    review = PerformanceReview.query.get_or_404(review_id)
    data = request.get_json(silent=True) or {}
    for field in ["employee_id", "period", "rating", "reviewer", "strengths",
                  "weaknesses", "goals", "status"]:
        if field in data:
            setattr(review, field, data[field])
    if "review_date" in data:
        review.review_date = parse_date(data["review_date"])
    db.session.commit()
    _log("edit", "hr_review", review.id, f"تقييم موظف {review.employee_id}")
    return jsonify(review.to_dict())


@hr_bp.route("/reviews/<int:review_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_review(review_id):
    review = PerformanceReview.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    _log("delete", "hr_review", review_id, "حذف تقييم")
    return jsonify({"success": True})


# ============ التدريب ============

@hr_bp.route("/trainings", methods=["GET"])
@require_api("hr", "view")
def list_trainings():
    q = TrainingProgram.query.order_by(TrainingProgram.id.desc())
    items, envelope = paged_or_cap(q)
    return jsonify(envelope if envelope else items)


@hr_bp.route("/trainings", methods=["POST"])
@require_api("hr", "create")
def create_training():
    data = request.get_json(silent=True) or {}
    if not (data.get("title") or "").strip():
        return jsonify({"message": "عنوان البرنامج التدريبي مطلوب"}), 400
    training = TrainingProgram(
        title=data["title"].strip(),
        provider=(data.get("provider") or "").strip(),
        start_date=parse_date(data.get("start_date")),
        end_date=parse_date(data.get("end_date")),
        cost=data.get("cost", 0),
        status=data.get("status", "planned"),
        notes=data.get("notes"),
    )
    db.session.add(training)
    db.session.commit()
    _log("create", "hr_training", training.id, f"تدريب: {training.title}")
    return jsonify(training.to_dict()), 201


@hr_bp.route("/trainings/<int:training_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_training(training_id):
    training = TrainingProgram.query.get_or_404(training_id)
    data = request.get_json(silent=True) or {}
    for field in ["title", "provider", "cost", "status", "notes"]:
        if field in data:
            setattr(training, field, data[field])
    for field, col in [("start_date", "start_date"), ("end_date", "end_date")]:
        if field in data:
            setattr(training, col, parse_date(data[field]))
    db.session.commit()
    _log("edit", "hr_training", training.id, f"تدريب: {training.title}")
    return jsonify(training.to_dict())


@hr_bp.route("/trainings/<int:training_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_training(training_id):
    training = TrainingProgram.query.get_or_404(training_id)
    db.session.delete(training)
    db.session.commit()
    _log("delete", "hr_training", training_id, "حذف برنامج تدريبي")
    return jsonify({"success": True})


@hr_bp.route("/trainings/<int:training_id>/enrollments", methods=["GET"])
@require_api("hr", "view")
def list_enrollments(training_id):
    rows = TrainingEnrollment.query.filter_by(training_id=training_id).all()
    return jsonify([e.to_dict() for e in rows])


@hr_bp.route("/trainings/<int:training_id>/enrollments", methods=["POST"])
@require_api("hr", "create")
def add_enrollment(training_id):
    data = request.get_json(silent=True) or {}
    if not data.get("employee_id"):
        return jsonify({"message": "اختر الموظف"}), 400
    existing = TrainingEnrollment.query.filter_by(
        training_id=training_id, employee_id=data["employee_id"]).first()
    if existing:
        return jsonify({"message": "الموظف مسجل بالفعل"}), 400
    enrollment = TrainingEnrollment(
        training_id=training_id,
        employee_id=data["employee_id"],
        status=data.get("status", "enrolled"),
        completed_at=parse_date(data.get("completed_at")),
        score=data.get("score"),
        notes=data.get("notes"),
    )
    db.session.add(enrollment)
    db.session.commit()
    _log("create", "hr_training_enrollment", enrollment.id, "تسجيل تدريب")
    return jsonify(enrollment.to_dict()), 201


@hr_bp.route("/enrollments/<int:enrollment_id>", methods=["PUT"])
@require_api("hr", "edit")
def update_enrollment(enrollment_id):
    enrollment = TrainingEnrollment.query.get_or_404(enrollment_id)
    data = request.get_json(silent=True) or {}
    for field in ["status", "score", "notes"]:
        if field in data:
            setattr(enrollment, field, data[field])
    if "completed_at" in data:
        enrollment.completed_at = parse_date(data["completed_at"])
    db.session.commit()
    _log("edit", "hr_training_enrollment", enrollment.id, "تعديل تسجيل تدريب")
    return jsonify(enrollment.to_dict())


@hr_bp.route("/enrollments/<int:enrollment_id>", methods=["DELETE"])
@require_api("hr", "delete")
def delete_enrollment(enrollment_id):
    enrollment = TrainingEnrollment.query.get_or_404(enrollment_id)
    db.session.delete(enrollment)
    db.session.commit()
    _log("delete", "hr_training_enrollment", enrollment_id, "حذف تسجيل تدريب")
    return jsonify({"success": True})
