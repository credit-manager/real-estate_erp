"""OpenAPI/Swagger Specification for DynamicPro ERP API."""
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields, validate

# API Instance - سيتم تهيئته في app.py
api = Api(
    spec_kwargs={
        "title": "DynamicPro ERP API",
        "version": "2.0.0",
        "openapi_version": "3.0.3",
        "info": {
            "description": "DynamicPro ERP - Real Estate Management System API\n\n"
                           "## Authentication\n"
                           "All API endpoints require session-based authentication via Flask session cookie.\n"
                           "CSRF token required for state-changing requests (POST/PUT/PATCH/DELETE).\n\n"
                           "## Rate Limiting\n"
                           "API endpoints are rate-limited: 100 requests/minute per IP for authenticated users.\n\n"
                           "## Error Format\n"
                           "```json\n"
                           "{\n"
                           "  \"success\": false,\n"
                           "  \"message\": \"Human readable error\",\n"
                           "  \"error_key\": \"translation.key\"\n"
                           "}\n"
                           "```",
            "contact": {"name": "DynamicPro Team", "email": "support@dynamicpro.com"},
            "license": {"name": "Proprietary"}
        },
        "servers": [{"url": "http://localhost:1111", "description": "Development server"}],
        "components": {
            "securitySchemes": {
                "sessionAuth": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "session",
                    "description": "Flask session cookie"
                },
                "csrfToken": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-CSRF-Token",
                    "description": "CSRF token for state-changing requests"
                }
            }
        },
        "security": [{"sessionAuth": [], "csrfToken": []}],
        "tags": [
            {"name": "Authentication", "description": "Login, logout, session management"},
            {"name": "Real Estate", "description": "Units, buildings, reservations, contracts, escrow, off-plan"},
            {"name": "Rentals", "description": "Rental contracts, payments, renewals, tenants"},
            {"name": "Accounting", "description": "Chart of accounts, journal entries, financial reports"},
            {"name": "CRM", "description": "Leads, opportunities, quotes, contracts, activities"},
            {"name": "HR & Payroll", "description": "Employees, attendance, payroll, contracts"},
            {"name": "Inventory", "description": "Items, warehouses, stock, transfers"},
            {"name": "Projects", "description": "WBS, BOQ, contracts, progress, costs"},
            {"name": "Mobile", "description": "Mobile app endpoints (GPS, visits, collections)"},
            {"name": "Portal", "description": "Client portal (no auth required for lookup)"},
            {"name": "Escrow", "description": "Escrow accounts and transactions (Wafi/Oqood)"},
            {"name": "Off-plan", "description": "Construction milestones, DSP plans, title deeds"},
            {"name": "Addons", "description": "DMS, HOA, AVM, mortgage calculator"},
            {"name": "System", "description": "Settings, users, roles, backup, audit"}
        ]
    }
)


# ==================== Marshmallow Schemas ====================

class ErrorSchema(Schema):
    success = fields.Bool(metadata={"example": False})
    message = fields.Str(metadata={"example": "رسالة الخطأ"})
    error_key = fields.Str(metadata={"example": "translation.key"})


class SuccessSchema(Schema):
    success = fields.Bool(metadata={"example": True})
    message = fields.Str(metadata={"example": "تم بنجاح"})


class PaginationSchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=25, validate=validate.Range(min=1, max=200))
    total = fields.Int(dump_only=True)
    pages = fields.Int(dump_only=True)


class LoginSchema(Schema):
    username = fields.Str(required=True, metadata={"example": "admin"})
    password = fields.Str(required=True, load_only=True, metadata={"example": "admin123"})
    access_password = fields.Str(load_only=True, metadata={"example": "optional_server_password"})


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(required=True, metadata={"example": "john_doe"})
    email = fields.Email(required=True, metadata={"example": "john@company.com"})
    full_name = fields.Str(required=True, metadata={"example": "جون دو"})
    role = fields.Str(validate=validate.OneOf(["admin", "employee"]), load_default="employee")
    is_active = fields.Bool(load_default=True)
    must_change_password = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class UnitSchema(Schema):
    id = fields.Int(dump_only=True)
    unit_code = fields.Str(required=True, metadata={"example": "A-101"})
    project_id = fields.Int(required=True)
    building_id = fields.Int()
    floor_id = fields.Int()
    unit_type_id = fields.Int()
    owner_id = fields.Int()
    unit_type = fields.Str(validate=validate.OneOf(["شقة", "فيلا", "بنتهاوس", "محل", "مكتب", "أرض", "مستودع"]))
    area = fields.Decimal(as_string=True, metadata={"example": "150.50"})
    floor = fields.Str()
    price = fields.Decimal(as_string=True, metadata={"example": "750000.00"})
    status = fields.Str(validate=validate.OneOf(["available", "reserved", "sold", "rented"]), load_default="available")
    created_at = fields.DateTime(dump_only=True)


class ReservationSchema(Schema):
    id = fields.Int(dump_only=True)
    unit_id = fields.Int(required=True)
    customer_id = fields.Int(required=True)
    reserved_date = fields.Date()
    expiry_date = fields.Date()
    deposit = fields.Decimal(as_string=True, metadata={"example": "50000.00"})
    status = fields.Str(validate=validate.OneOf(["active", "converted", "cancelled", "expired"]), load_default="active")
    notes = fields.Str()


class SalesContractSchema(Schema):
    id = fields.Int(dump_only=True)
    contract_number = fields.Str(required=True, metadata={"example": "SC-2026-0001"})
    unit_id = fields.Int(required=True)
    customer_id = fields.Int(required=True)
    payment_plan_id = fields.Int()
    total_amount = fields.Decimal(as_string=True, metadata={"example": "500000.00"})
    discount = fields.Decimal(as_string=True, metadata={"example": "0.00"})
    net_amount = fields.Decimal(as_string=True, metadata={"example": "500000.00"})
    vat_rate = fields.Float(metadata={"example": 15.0})
    vat_amount = fields.Decimal(as_string=True, metadata={"example": "75000.00"})
    contract_date = fields.Date()
    status = fields.Str(validate=validate.OneOf(["draft", "active", "completed", "cancelled"]), load_default="active")
    approval_status = fields.Str(validate=validate.OneOf(["not_required", "pending", "approved", "rejected"]))
    notes = fields.Str()


class InvoiceSchema(Schema):
    id = fields.Int(dump_only=True)
    invoice_number = fields.Str(required=True, metadata={"example": "INV-2026-0001"})
    invoice_type = fields.Str(validate=validate.OneOf(["sales", "purchase", "expense"]))
    customer_id = fields.Int()
    supplier_id = fields.Int()
    project_id = fields.Int()
    financial_year_id = fields.Int()
    amount = fields.Decimal(as_string=True, metadata={"example": "10000.00"})
    paid_amount = fields.Decimal(as_string=True, metadata={"example": "0.00"})
    status = fields.Str(validate=validate.OneOf(["pending", "paid", "partial", "overdue"]))
    approval_status = fields.Str(validate=validate.OneOf(["not_required", "pending", "approved", "rejected"]))
    issue_date = fields.Date()
    due_date = fields.Date()
    description = fields.Str()


class PaymentPlanSchema(Schema):
    id = fields.Int(dump_only=True)
    unit_id = fields.Int(required=True)
    customer_id = fields.Int(required=True)
    financial_year_id = fields.Int()
    total_amount = fields.Decimal(as_string=True)
    down_payment = fields.Decimal(as_string=True)
    monthly_amount = fields.Decimal(as_string=True)
    start_date = fields.Date()
    months = fields.Int(validate=validate.Range(min=1), load_default=12)
    status = fields.Str(validate=validate.OneOf(["active", "completed", "overdue"]))


class InstallmentSchema(Schema):
    id = fields.Int(dump_only=True)
    plan_id = fields.Int(required=True)
    installment_number = fields.Int(load_default=1)
    amount = fields.Decimal(as_string=True)
    paid_amount = fields.Decimal(as_string=True)
    due_date = fields.Date()
    paid_date = fields.Date()
    status = fields.Str(validate=validate.OneOf(["pending", "paid", "partial", "overdue"]))


# ==================== New Features Schemas ====================

class EscrowAccountSchema(Schema):
    id = fields.Int(dump_only=True)
    project_id = fields.Int(required=True)
    escrow_number = fields.Str(dump_only=True, metadata={"example": "ESC-2026-0001"})
    bank_name = fields.Str(required=True, metadata={"example": "بنك الراجحي"})
    iban = fields.Str()
    balance = fields.Decimal(as_string=True, dump_only=True)
    status = fields.Str(validate=validate.OneOf(["active", "frozen", "closed"]), load_default="active")
    notes = fields.Str()


class EscrowTransactionSchema(Schema):
    id = fields.Int(dump_only=True)
    account_id = fields.Int(required=True)
    contract_id = fields.Int()
    installment_id = fields.Int()
    amount = fields.Decimal(as_string=True, required=True)
    type = fields.Str(validate=validate.OneOf(["deposit", "release", "hold", "refund"]), required=True)
    status = fields.Str(validate=validate.OneOf(["pending", "completed", "cancelled"]), dump_only=True)
    description = fields.Str()


class ConstructionMilestoneSchema(Schema):
    id = fields.Int(dump_only=True)
    project_id = fields.Int(required=True)
    name = fields.Str(required=True, metadata={"example": "أعمال الحفر"})
    description = fields.Str()
    target_date = fields.Date()
    completion_pct = fields.Float(validate=validate.Range(min=0, max=100), load_default=0)
    status = fields.Str(validate=validate.OneOf(["pending", "in_progress", "completed", "delayed"]), load_default="pending")
    weight = fields.Float(validate=validate.Range(min=0, max=100))


class DSPPlanSchema(Schema):
    id = fields.Int(dump_only=True)
    project_id = fields.Int(required=True)
    milestone_id = fields.Int()
    name = fields.Str(required=True, metadata={"example": "دفعة الحجز"})
    due_pct = fields.Float(required=True, validate=validate.Range(min=0, max=100))
    amount_formula = fields.Str(validate=validate.OneOf(["pct", "fixed"]), load_default="pct")
    fixed_amount = fields.Decimal(as_string=True)
    due_days_after_milestone = fields.Int(load_default=0)
    is_active = fields.Bool(load_default=True)


class TitleDeedSchema(Schema):
    id = fields.Int(dump_only=True)
    unit_id = fields.Int(required=True)
    deed_number = fields.Str(required=True, metadata={"example": "DEED-2026-0001"})
    owner_name = fields.Str(required=True)
    owner_id_number = fields.Str()
    issue_date = fields.Date()
    area = fields.Decimal(as_string=True)
    deed_type = fields.Str(validate=validate.OneOf(["freehold", "usufruct", "leasehold"]), load_default="freehold")
    status = fields.Str(validate=validate.OneOf(["active", "transferred", "cancelled"]), load_default="active")
    previous_deed_id = fields.Int()
    notes = fields.Str()


class UnitDocumentSchema(Schema):
    id = fields.Int(dump_only=True)
    unit_id = fields.Int(required=True)
    doc_type = fields.Str(validate=validate.OneOf(["title_deed", "contract", "id_copy", "plan", "photo", "other"]))
    title = fields.Str(required=True)
    file_path = fields.Str()
    file_size = fields.Int()
    mime_type = fields.Str()
    version = fields.Int(dump_only=True)
    notes = fields.Str()


class OwnerAssociationSchema(Schema):
    id = fields.Int(dump_only=True)
    project_id = fields.Int(required=True)
    name = fields.Str(required=True)
    annual_fee_per_sqm = fields.Decimal(as_string=True)
    collected_amount = fields.Decimal(as_string=True, dump_only=True)
    balance = fields.Decimal(as_string=True, dump_only=True)
    status = fields.Str(validate=validate.OneOf(["active", "inactive"]), load_default="active")
    notes = fields.Str()


class ServiceChargeSchema(Schema):
    id = fields.Int(dump_only=True)
    association_id = fields.Int(required=True)
    unit_id = fields.Int(required=True)
    period = fields.Str(required=True, metadata={"example": "2026-Q1"})
    amount = fields.Decimal(as_string=True, required=True)
    paid_amount = fields.Decimal(as_string=True, dump_only=True)
    due_date = fields.Date()
    status = fields.Str(validate=validate.OneOf(["pending", "paid", "overdue", "waived"]), load_default="pending")
    notes = fields.Str()


class PortalLookupResponse(Schema):
    contract = fields.Nested(SalesContractSchema)
    unit = fields.Nested(UnitSchema)
    customer = fields.Dict()
    installments = fields.List(fields.Nested(InstallmentSchema))
    maintenance = fields.List(fields.Dict())


class AVMResponse(Schema):
    unit_id = fields.Int()
    unit_code = fields.Str()
    area = fields.Float()
    current_price = fields.Float()
    avg_price_per_sqm = fields.Float()
    estimated_value = fields.Float()
    diff_pct = fields.Float()
    source = fields.Str()
    confidence = fields.Str(validate=validate.OneOf(["high", "medium", "low"]))


class MortgageCalcResponse(Schema):
    price = fields.Float()
    down_payment = fields.Float()
    principal = fields.Float()
    annual_rate = fields.Float()
    years = fields.Int()
    months = fields.Int()
    monthly_payment = fields.Float()
    total_paid = fields.Float()
    total_interest = fields.Float()


class PortalLookupQuery(Schema):
    contract_number = fields.Str(required=True)
    phone = fields.Str()


class MortgageCalcQuery(Schema):
    price = fields.Float(required=True, validate=validate.Range(min=1))
    down = fields.Float(load_default=0, validate=validate.Range(min=0))
    rate = fields.Float(load_default=0, validate=validate.Range(min=0, max=100))
    years = fields.Int(load_default=20, validate=validate.Range(min=1, max=50))


# ==================== Helper to register existing blueprints with API spec ====================

def register_existing_blueprints(api_instance):
    """سجل الـ blueprints الموجودة مع OpenAPI - يتم استدعاؤها من app.py."""
    # سيتم إضافة المسارات هنا تدريجياً
    pass


# ==================== Blueprint for OpenAPI documentation endpoints ====================

doc_bp = Blueprint(
    "docs",
    __name__,
    url_prefix="/api/docs",
    description="API Documentation endpoints"
)

@doc_bp.route("/swagger.json")
def swagger_json():
    return api.spec.to_dict()

@doc_bp.route("/redoc")
def redoc_view():
    from flask import render_template_string
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>DynamicPro ERP API - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>body { margin: 0; padding: 0; }</style>
</head>
<body>
    <redoc spec-url="/api/docs/swagger.json"></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
</body>
</html>
''')