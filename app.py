import json
import os
import sys
import logging
from datetime import datetime
from flask import Flask, redirect, url_for, request, session, jsonify, current_app
from flask_cors import CORS
from database import db
import config
import server_config
import permissions
from i18n import TRANSLATIONS, DEFAULT_LANG, LANG_CODES, get_lang, make_t


def _run_migrations_and_seeds(app, db):
    """Run all migrations and seed data. Only for master (non-company) instances."""
    from models import User, Role
    from werkzeug.security import generate_password_hash
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    cols = [c["name"] for c in insp.get_columns("users")]
    if "must_change_password" not in cols:
        db.session.execute(text(
            "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE"
        ))
        db.session.commit()

    for table in ["invoices", "purchase_orders", "rental_contracts", "payment_plans"]:
        cols = [c["name"] for c in insp.get_columns(table)]
        if "financial_year_id" not in cols:
            db.session.execute(text(
                f"ALTER TABLE {table} ADD COLUMN financial_year_id INTEGER"
            ))
    db.session.commit()

    fk_plan = {
        "invoices": "fk_invoices_financial_year",
        "purchase_orders": "fk_purchase_orders_financial_year",
        "rental_contracts": "fk_rental_contracts_financial_year",
        "payment_plans": "fk_payment_plans_financial_year",
    }
    existing_tables = set(insp.get_table_names())
    if "financial_years" in existing_tables:
        fkinsp = inspect(db.engine)
        existing_fk_names = {
            fk["name"]
            for table in existing_tables
            for fk in fkinsp.get_foreign_keys(table)
            if fk.get("name")
        }
        for table, con_name in fk_plan.items():
            if table not in existing_tables or con_name in existing_fk_names:
                continue
            if "financial_year_id" not in [c["name"] for c in fkinsp.get_columns(table)]:
                continue
            db.session.execute(text(
                f"DELETE FROM {table} WHERE financial_year_id IS NOT NULL "
                f"AND NOT EXISTS (SELECT 1 FROM financial_years "
                f"WHERE id = {table}.financial_year_id)"
            ))
            db.session.execute(text(
                f"ALTER TABLE {table} ADD CONSTRAINT {con_name} "
                f"FOREIGN KEY (financial_year_id) REFERENCES financial_years(id) "
                f"ON DELETE SET NULL"
            ))
        db.session.commit()

    if "sales_contracts" in insp.get_table_names():
        sc_cols = [c["name"] for c in insp.get_columns("sales_contracts")]
        if "vat_rate" not in sc_cols:
            db.session.execute(text("ALTER TABLE sales_contracts ADD COLUMN vat_rate FLOAT DEFAULT 0"))
        if "vat_amount" not in sc_cols:
            db.session.execute(text("ALTER TABLE sales_contracts ADD COLUMN vat_amount NUMERIC(15,2) DEFAULT 0"))
    if "commissions" in insp.get_table_names():
        cm_cols = [c["name"] for c in insp.get_columns("commissions")]
        if "broker_id" not in cm_cols:
            db.session.execute(text("ALTER TABLE commissions ADD COLUMN broker_id INTEGER"))
    for _tbl in ("sales_orders", "journal_entries"):
        if _tbl in insp.get_table_names():
            _cols = [c["name"] for c in insp.get_columns(_tbl)]
            if "deleted_at" not in _cols:
                db.session.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN deleted_at TIMESTAMP"))
                db.session.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{_tbl}_deleted_at ON {_tbl} (deleted_at)"))
    if "workflow_templates" in insp.get_table_names():
        wt_cols = [c["name"] for c in insp.get_columns("workflow_templates")]
        if "min_amount" not in wt_cols:
            db.session.execute(text("ALTER TABLE workflow_templates ADD COLUMN min_amount NUMERIC(15, 2)"))
    if "invoices" in insp.get_table_names():
        inv_cols = [c["name"] for c in insp.get_columns("invoices")]
        _einv_cols = {
            "einv_status": "VARCHAR(20)",
            "einv_reference": "VARCHAR(120)",
            "einv_qr": "TEXT",
            "einv_submitted_at": "TIMESTAMP",
            "einv_message": "TEXT",
        }
        for _c, _t in _einv_cols.items():
            if _c not in inv_cols:
                db.session.execute(text(f"ALTER TABLE invoices ADD COLUMN {_c} {_t}"))
    db.session.commit()

    from models import TaxType
    if TaxType.query.count() == 0:
        db.session.add(TaxType(name="ضريبة القيمة المضافة", rate=15, is_active=True, is_default=True))
        db.session.add(TaxType(name="معفاة من الضريبة", rate=0, is_active=True, is_default=False))
        db.session.commit()

    unit_cols = [c["name"] for c in insp.get_columns("real_estate_units")]
    for col in ["building_id", "floor_id", "unit_type_id", "owner_id"]:
        if col not in unit_cols:
            db.session.execute(text(f"ALTER TABLE real_estate_units ADD COLUMN {col} INTEGER"))
    db.session.commit()

    from models import UnitType
    if UnitType.query.count() == 0:
        for ut in ["شقة", "فيلا", "بنتهاوس", "محل", "مكتب", "أرض", "مستودع"]:
            db.session.add(UnitType(name=ut, is_active=True))
        db.session.commit()

    if "employees" in insp.get_table_names():
        emp_cols = [c["name"] for c in insp.get_columns("employees")]
        emp_add = {
            "department_id": "INTEGER",
            "position_id": "INTEGER",
            "manager_id": "INTEGER",
            "gender": "VARCHAR(10)",
            "birth_date": "DATE",
            "end_date": "DATE",
            "employment_type": "VARCHAR(30) DEFAULT 'full_time'",
        }
        for col_name, ddl in emp_add.items():
            if col_name not in emp_cols:
                db.session.execute(text(f"ALTER TABLE employees ADD COLUMN {col_name} {ddl}"))
        db.session.commit()

    if "customers" in insp.get_table_names():
        cust_cols = [c["name"] for c in insp.get_columns("customers")]
        for col in ["company", "notes"]:
            if col not in cust_cols:
                db.session.execute(text(f"ALTER TABLE customers ADD COLUMN {col} VARCHAR(255)"))
        if "is_active" not in cust_cols:
            db.session.execute(text("ALTER TABLE customers ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
        db.session.commit()

    from models import CrmPipelineStage
    if CrmPipelineStage.query.count() == 0:
        for i, (name, prob) in enumerate(
            [("جديد", 10), ("مؤهل", 30), ("عرض", 50), ("تفاوض", 70), ("مقبول", 100)],
            start=1,
        ):
            db.session.add(CrmPipelineStage(name=name, position=i, probability=prob, is_active=True))
        db.session.commit()

    from models import SystemSetting
    import utils.settings as settings_module
    existing = {s.key for s in SystemSetting.query.all()}
    for key, default in settings_module.DEFAULTS.items():
        if key not in existing:
            db.session.add(SystemSetting(key=key, value=default))
    db.session.commit()

    for table in ["invoices", "purchase_orders", "rental_contracts"]:
        cols = [c["name"] for c in insp.get_columns(table)]
        if "approval_status" not in cols:
            db.session.execute(text(
                f"ALTER TABLE {table} ADD COLUMN approval_status VARCHAR(20) DEFAULT 'not_required'"
            ))
    db.session.commit()

    from models import WorkflowTemplate, WorkflowStep
    default_templates = {
        "invoice": "اعتماد الفواتير",
        "po": "اعتماد أوامر الشراء",
        "rental_contract": "اعتماد عقود الإيجار",
    }
    for dt, tpl_name in default_templates.items():
        if not WorkflowTemplate.query.filter_by(doc_type=dt).first():
            tpl = WorkflowTemplate(doc_type=dt, name=tpl_name, is_active=True)
            tpl.steps.append(WorkflowStep(position=1, role="admin"))
            db.session.add(tpl)
    db.session.commit()

    import utils.accounting as accounting
    accounting.seed_default_coa()

    tables = insp.get_table_names()
    if "journal_entry_lines" in tables:
        cols = [c["name"] for c in insp.get_columns("journal_entry_lines")]
        if "reconciled" not in cols:
            db.session.execute(text("ALTER TABLE journal_entry_lines ADD COLUMN reconciled BOOLEAN DEFAULT FALSE"))
        if "reconciled_at" not in cols:
            db.session.execute(text("ALTER TABLE journal_entry_lines ADD COLUMN reconciled_at TIMESTAMP"))
        db.session.commit()

    if "invoice_items" in insp.get_table_names():
        ii_cols = [c["name"] for c in insp.get_columns("invoice_items")]
        if "item_id" not in ii_cols:
            db.session.execute(text("ALTER TABLE invoice_items ADD COLUMN item_id INTEGER"))
        if "warehouse_id" not in ii_cols:
            db.session.execute(text("ALTER TABLE invoice_items ADD COLUMN warehouse_id INTEGER"))
        if "expiry_date" not in ii_cols:
            db.session.execute(text("ALTER TABLE invoice_items ADD COLUMN expiry_date DATE"))
        db.session.commit()

    if "hr_attendance" in insp.get_table_names():
        att_cols = [c["name"] for c in insp.get_columns("hr_attendance")]
        for col in ["check_in_lat", "check_in_lng", "check_out_lat", "check_out_lng"]:
            if col not in att_cols:
                db.session.execute(text(f"ALTER TABLE hr_attendance ADD COLUMN {col} FLOAT"))
        db.session.commit()

    if "employees" in insp.get_table_names():
        emp_cols = [c["name"] for c in insp.get_columns("employees")]
        if "user_id" not in emp_cols:
            db.session.execute(text("ALTER TABLE employees ADD COLUMN user_id INTEGER"))
        db.session.commit()

    if Role.query.count() == 0:
        db.session.add(Role(name="admin", description="مدير النظام", is_system=True, permissions=permissions.all_true()))
        db.session.add(Role(name="employee", description="موظف", is_system=True, permissions=permissions.view_only()))
        db.session.commit()

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin", email="admin@mokawlat.com", full_name="مدير النظام",
            role="admin", password_hash=generate_password_hash("admin123"), must_change_password=True,
        )
        db.session.add(admin)
        db.session.commit()

    for _tbl in ["real_estate_units", "unit_reservations", "sales_contracts", "invoices"]:
        if _tbl in insp.get_table_names():
            _cols = [c["name"] for c in insp.get_columns(_tbl)]
            if "deleted_at" not in _cols:
                db.session.execute(text(f"ALTER TABLE {_tbl} ADD COLUMN deleted_at TIMESTAMP"))
                db.session.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{_tbl}_deleted_at ON {_tbl} (deleted_at)"))
                db.session.commit()

    try:
        db.session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_reservation_unit "
            "ON unit_reservations (unit_id) WHERE status = 'active' AND deleted_at IS NULL"
        ))
        db.session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_sales_contract_unit "
            "ON sales_contracts (unit_id) WHERE status IN ('active','draft') AND deleted_at IS NULL"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

    from db_indexes import ensure_indexes
    ensure_indexes(db.engine, db.session)

    # Phase 1 — seed Master Cloud RBAC (roles + permission catalog). Idempotent.
    from security.rbac import seed_roles_and_permissions
    seed_roles_and_permissions()

    # Phase 5 — seed module catalog. Idempotent.
    from security.modules import seed_module_catalog
    seed_module_catalog()


def _source_dir():
    """مجلد المصدر الذي يُقرأ منه القوالب والملفات الثابتة.

    عند تشغيل النسخة المجمعة (frozen) يبحث بجانب الـ exe عن مجلد المصدر
    حتى تظهر أي تعديلات فوراً دون إعادة بناء، مع الاحتفاظ بخيار التجميع.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        marker = os.path.join(exe_dir, "_source_dir.txt")
        if os.path.isfile(marker):
            try:
                with open(marker, encoding="utf-8") as fh:
                    path = fh.read().strip()
                if path and os.path.isdir(path):
                    return path
            except OSError:
                pass
        parent = os.path.abspath(os.path.join(exe_dir, os.pardir))
        if os.path.isfile(os.path.join(parent, "app.py")) and os.path.isdir(os.path.join(parent, "templates")):
            return parent
        return None
    return os.path.abspath(os.path.dirname(__file__))


def _get_csrf_token():
    """Returns the CSRF token for the current session (generates one if absent)."""
    token = session.get("_csrf_token")
    if not token:
        import secrets as _secrets
        token = _secrets.token_hex(32)
        session["_csrf_token"] = token
    return token


def _csrf_valid():
    """Validates the CSRF token on state-changing requests."""
    supplied = request.headers.get("X-CSRF-Token")
    if not supplied:
        data = request.get_json(silent=True)
        if data and isinstance(data, dict):
            supplied = data.get("csrf_token")
    expected = session.get("_csrf_token")
    if not expected or not supplied:
        return False
    import hmac
    return hmac.compare_digest(str(expected), str(supplied))


def create_app():
    root = _source_dir()
    if root:
        app = Flask(
            __name__,
            root_path=root,
            template_folder=os.path.join(root, "templates"),
            static_folder=os.path.join(root, "static"),
        )
    else:
        app = Flask(__name__)
    app.config.from_object(config)
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # أساس التسجيل المركزي (Logging Foundation) — كونسول + ملف دوّار
    from utils.logging_setup import configure_logging
    configure_logging()
    logging.getLogger("dynamicpro.app").info("Applying app configuration")

    # حد أقصى لحجم الطلبات المرفوعة (110MB للسماح بـ 100MB نسخ احتياطي + هامش)
    app.config["MAX_CONTENT_LENGTH"] = 110 * 1024 * 1024

    # إعدادات الخادم المحلي (منفذ + كلمة مرور الوصول)
    _server_cfg = server_config.load_config()
    app.config["SERVER_PORT"] = _server_cfg.get("port", 5000)
    app.config["SERVER_ACCESS_PASSWORD"] = _server_cfg.get("access_password", "")

    # في وضع الإنتاج مع HTTPS مفعّل: الكوكي يُرسل عبر HTTPS فقط
    if (os.environ.get("DYNAMICPRO_MODE") == "production"
            and bool(server_config.get_cert_paths()[0])):
        app.config["SESSION_COOKIE_SECURE"] = True

    db.init_app(app)

    # CORS — allow Control Center frontend on localhost:3000
    CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"],
         supports_credentials=True, expose_headers=["Content-Type"])

    # تهيئة OpenAPI/Swagger (flask-smorest)
    from api_spec import api as api_spec
    api_spec.init_app(app)

    # تهيئة Rate Limiting
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per minute", "50 per second"],
        storage_uri="memory://",
        strategy="fixed-window",
        key_prefix="rl:"
    )
    # متاح للوحدات التي تحتاج حدود مخصصة (مثل /api/ai/query)
    app.config["RATELIMITER"] = limiter

    # لا CORS مفتوح: الواجهة والموبايل يعملان من نفس الأصل،
    # فلا حاجة لسماح cross-origin (المتصفح يرفض الطلبات الخارجية تلقائياً).

    # تسجيل الـ Blueprints
    from routes.auth import auth_bp
    from routes.projects import projects_bp
    from routes.api import api_bp
    from routes.pages import pages_bp
    from routes.users import users_bp
    from routes.backup import backup_bp
    from routes.server import server_bp
    from routes.roles import roles_bp
    from routes.companies import companies_bp
    from routes.financial_years import financial_years_bp
    from routes.currencies import currencies_bp
    from routes.taxes import taxes_bp
    from routes.settings import settings_bp
    from routes.workflow import workflow_bp
    from routes.accounting import accounting_bp
    from routes.real_estate_invest import re_bp
    from routes.escrow import escrow_bp
    from routes.offplan import offplan_bp
    from routes.addons import addons_bp
    from routes.esignature import esign_bp
    from routes.bi import bi_bp
    from routes.dms import dms_bp
    from routes.notifications import notif_bp
    from routes.payments import payments_bp
    from routes.portal import portal_bp, portal_api_bp
    from routes.crm import crm_bp
    from routes.sales import sales_bp
    from routes.procurement import procurement_bp
    from routes.inventory import inventory_bp, pages_bp as inventory_pages_bp
    from routes.hr import hr_bp, hr_pages_bp
    from routes.payroll import payroll_bp, payroll_pages_bp
    from routes.manufacturing import mf_bp, mf_pages_bp
    from routes.rentals import rental_bp, rental_pages_bp
    from routes.assets import assets_bp
    from routes.mobile import mobile_bp, mobile_api
    from routes.license import license_bp, validate_license
    from licensing.routes import admin_lic_bp, company_auth_bp
    from api_spec import doc_bp
    # Phase 1 — ensure security/RBAC models are registered before db.create_all()
    import security.models  # noqa: F401
    from security.routes import security_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(server_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(financial_years_bp)
    app.register_blueprint(currencies_bp)
    app.register_blueprint(taxes_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(workflow_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(re_bp)
    app.register_blueprint(escrow_bp)
    app.register_blueprint(offplan_bp)
    app.register_blueprint(addons_bp)
    app.register_blueprint(esign_bp)
    app.register_blueprint(bi_bp)
    app.register_blueprint(dms_bp)
    app.register_blueprint(notif_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(portal_api_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(inventory_pages_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(hr_pages_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(payroll_pages_bp)
    app.register_blueprint(mf_bp)
    app.register_blueprint(mf_pages_bp)
    app.register_blueprint(rental_bp)
    app.register_blueprint(rental_pages_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(mobile_bp)
    app.register_blueprint(mobile_api)
    app.register_blueprint(license_bp)
    app.register_blueprint(company_auth_bp)
    app.register_blueprint(doc_bp)

    # CRITICAL #3: Admin routes فقط على الوضع الرئيسي (master port)
    if not config.COMPANY_ID:
        app.register_blueprint(admin_lic_bp)
        app.register_blueprint(security_bp)

    def get_lang():
        lang = request.cookies.get("lang", DEFAULT_LANG)
        if lang not in LANG_CODES:
            lang = DEFAULT_LANG
        return lang

    @app.context_processor
    def inject_i18n():
        lang = get_lang()
        import utils.settings as settings_module
        _settings = settings_module.get_all()

        def t(key):
            return make_t(lang)(key)

        return {
            "t": t,
            "lang": lang,
            "full_name": session.get("full_name", ""),
            "role": session.get("role", ""),
            "csrf_token": _get_csrf_token(),
            "translations_json": json.dumps(TRANSLATIONS[lang], ensure_ascii=False),
            "permissions_json": json.dumps(permissions.current_perms(), ensure_ascii=False),
            "can": permissions.can,
            "perms": permissions.current_perms,
            "is_dark": request.cookies.get("theme", "light") == "dark",
            "is_server_local": request.remote_addr in ("127.0.0.1", "::1"),
            "system_name": _settings.get("system_name") or "Dynamic Pro ERP",
            "system_logo": _settings.get("system_logo") or "",
            "owner_name": server_config.load_config().get("owner_name") or "Dynamic Pro",
            "owner_logo": server_config.load_config().get("owner_logo") or "",
            "default_theme": _settings.get("default_theme") or "light",
            "default_lang": _settings.get("default_lang") or "ar",
            "doc_footer_text": _settings.get("doc_footer_text") or "",
            "number_decimals": settings_module.get_int("number_decimals", 2),
            "app_settings_json": json.dumps(settings_module.get_all(), ensure_ascii=False),
            "year": datetime.now().year,
        }

    @app.route("/api/language/<lang>", methods=["POST"])
    def set_language(lang):
        if lang not in LANG_CODES:
            lang = DEFAULT_LANG
        resp = jsonify({"success": True, "lang": lang})
        resp.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
        return resp

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/health")
    def health():
        """Health check endpoint for Docker / Nginx."""
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({
            "status": "healthy" if db_ok else "degraded",
            "database": "connected" if db_ok else "disconnected",
        }), 200 if db_ok else 503

    # إنشاء الجداول + مستخدم وادوار افتراضية
    # HIGH #9: company instances لا تُشغّل الترحيلات العامة
    _is_company = bool(config.COMPANY_ID)
    with app.app_context():
        db.create_all()
        if not _is_company:
            _run_migrations_and_seeds(app, db)

    # بدء النسخ الاحتياطي التلقائي (خيط خلفي)
    from routes.backup import schedule_auto_backup
    schedule_auto_backup(app)

    # منع الكاش تماماً للملفات الثابتة (JS/CSS/Images) لضمان ظهور أي تحديث فوراً
    @app.after_request
    def no_cache_static(response):
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # هيدرات أمان على كل الاستجابات
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # CSP أساسي: اسمح بـ self + CDN المحددة فقط (Chart.js + Google Fonts)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'self'",
        )
        # HSTS عند تفعيل HTTPS
        if (server_config.is_https_enabled() and server_config.get_cert_paths()[0]):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response

    def _is_api_path():
        p = request.path
        return p.startswith("/api/") or "/api/" in p

    # معالج أخطاء مركزي — يمنع تسريب تفاصيل الأخطاء للمستخدم
    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        current_app.logger.error(f"Unhandled exception: {e}", exc_info=True)
        if _is_api_path():
            return jsonify({"success": False, "message": "خطأ داخلي في الخادم"}), 500
        return "<h1>خطأ داخلي</h1><p>حدث خطأ غير متوقع. يرجى المحاولة لاحقاً.</p>", 500

    @app.errorhandler(404)
    def not_found(e):
        if _is_api_path():
            return jsonify({"success": False, "message": "غير موجود"}), 404
        return "<h1>غير موجود</h1>", 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        if _is_api_path():
            return jsonify({"success": False, "message": "الطريقة غير مسموحة"}), 405
        return "<h1>غير مسموح</h1>", 405

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({"success": False, "message": "تم تجاوز حد الطلبات. يرجى الانتظار."}), 429

    # حماية CSRF: طلبات التغيير (POST/PUT/DELETE) من الجلسات الحية تتطلب رمزاً صالحاً
    @app.before_request
    def protect_csrf():
        if current_app.config.get("TESTING"):
            return
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        if request.path.startswith("/static"):
            return
        if request.path.startswith("/admin/"):
            return
        if not session.get("user_id"):
            return
        if request.path in ("/login", "/logout"):
            return
        if not _csrf_valid():
            return jsonify({"success": False, "message": "invalid-csrf-token"}), 403

    # التحقق من صلاحية الترخيص
    @app.before_request
    def enforce_license():
        if request.path.startswith("/static"):
            return
        if request.path in ("/login", "/logout"):
            return
        if request.path.startswith("/license/"):
            return
        if request.path.startswith("/admin/"):
            return
        # HIGH #12: Company instances use LicLicense from licensing engine
        if config.COMPANY_ID:
            try:
                from licensing.engine import can_access
                access = can_access(int(config.COMPANY_ID))
                if not access["allowed"]:
                    if _is_api_path():
                        return jsonify({"success": False, "message": "Subscription expired"}), 403
                    return redirect(url_for("auth.login"))
            except Exception:
                pass
            return
        try:
            is_valid, err = validate_license()
            if not is_valid:
                if _is_api_path():
                    return jsonify({"success": False, "message": "License expired"}), 403
                return redirect(url_for("pages.change_password", error="license_expired"))
        except Exception:
            from utils.errlog import log_exc
            log_exc("app.enforce-license")

    # (تم تعطيل إجبار تغيير كلمة المرور)
    @app.before_request
    def enforce_password_change():
        pass

    return app


app = create_app()

if __name__ == "__main__":
    import threading
    from werkzeug.serving import make_server

    # وضع الإنتاج (يُفعل عند التشغيل عبر desktop.py أو الخدمة):
    #  - debug معطل تماماً في الإنتاج (لا يعرض الكود أو تتبع الأخطاء)
    #  - في وضع التطوير: debug يُفعَّل فقط عبر DYNAMICPRO_MODE=dev
    production = os.environ.get("DYNAMICPRO_MODE", "dev") == "production"
    debug = os.environ.get("FLASK_DEBUG", "0") == "1" and not production

    def _start_https():
        cert, key = server_config.get_cert_paths()
        if not cert or not key:
            return
        https_port = server_config.get_https_port()
        srv = make_server("0.0.0.0", https_port, app,
                          ssl_context=(cert, key), threaded=True)
        print(f"[HTTPS] https://0.0.0.0:{https_port} (geolocation available)")
        srv.serve_forever()

    # مع debug=True يعمل werkzeug reloader في عمليتين (رئيسية + تبعية).
    # نبدأ خادم HTTPS فقط في العملية التبعية الفعلية حتى لا يتعارض على المنفذ.
    if (server_config.is_https_enabled()
            and server_config.get_cert_paths()[0]
            and (os.environ.get("WERKZEUG_RUN_MAIN") == "true" or production)):
        threading.Thread(target=_start_https, daemon=True).start()

    import signal, atexit
    def _shutdown():
        try:
            with app.app_context():
                from database import db as _db
                _db.session.close()
        except Exception:
            pass
    atexit.register(_shutdown)
    def _sig_handler(signum, frame):
        _shutdown()
        import sys
        sys.exit(0)
    try:
        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)
    except (OSError, AttributeError):
        pass

    app.run(host="127.0.0.1", port=server_config.get_port(),
            debug=debug, use_reloader=debug, threaded=True)
