# -*- coding: utf-8 -*-
"""Module management functions (Phase 5).

Provides module catalog CRUD, company module enable/disable,
and feature flag management with audit logging.
"""
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# Default module catalog — seeded on first run
DEFAULT_MODULES = [
    {"code": "accounting", "name": "Accounting", "name_ar": "المحاسبة", "is_core": True, "sort_order": 1},
    {"code": "projects", "name": "Projects", "name_ar": "المشاريع", "is_core": True, "sort_order": 2},
    {"code": "procurement", "name": "Procurement", "name_ar": "المشتريات", "is_core": True, "sort_order": 3},
    {"code": "inventory", "name": "Inventory", "name_ar": "المخزون", "is_core": True, "sort_order": 4},
    {"code": "hr", "name": "HR", "name_ar": "الموارد البشرية", "is_core": False, "sort_order": 5},
    {"code": "payroll", "name": "Payroll", "name_ar": "الرواتب", "is_core": False, "sort_order": 6},
    {"code": "crm", "name": "CRM", "name_ar": "إدارة العملاء", "is_core": False, "sort_order": 7},
    {"code": "sales", "name": "Sales", "name_ar": "المبيعات", "is_core": False, "sort_order": 8},
    {"code": "equipment", "name": "Equipment", "name_ar": "الأصول", "is_core": False, "sort_order": 9},
    {"code": "advanced_reports", "name": "Advanced Reports", "name_ar": "التقارير المتقدمة", "is_core": False, "sort_order": 10},
    {"code": "multi_branch", "name": "Multi-Branch", "name_ar": "الفروع المتعددة", "is_core": False, "sort_order": 11},
    {"code": "api_access", "name": "API Access", "name_ar": "الوصول للـ API", "is_core": False, "sort_order": 12},
    {"code": "ai", "name": "AI", "name_ar": "الذكاء الاصطناعي", "is_core": False, "sort_order": 13},
    {"code": "priority_support", "name": "Priority Support", "name_ar": "الدعم الفني المميز", "is_core": False, "sort_order": 14},
]


def seed_module_catalog():
    """Idempotently seed the module catalog."""
    from database import db
    from security.models import ModuleCatalog

    existing = {m.code for m in ModuleCatalog.query.all()}
    for m in DEFAULT_MODULES:
        if m["code"] not in existing:
            db.session.add(ModuleCatalog(**m))
    db.session.commit()
    log.info("Seeded module catalog (%d modules)", len(DEFAULT_MODULES))


def list_modules():
    """List all modules in the catalog."""
    from database import db
    from security.models import ModuleCatalog

    modules = ModuleCatalog.query.filter_by(is_active=True).order_by(ModuleCatalog.sort_order).all()
    return {"success": True, "modules": [m.to_dict() for m in modules]}


def get_module(code):
    """Get a single module by code."""
    from database import db
    from security.models import ModuleCatalog

    module = ModuleCatalog.query.filter_by(code=code).first()
    if not module:
        return {"success": False, "message": f"الوحدة '{code}' غير موجودة"}
    return {"success": True, "module": module}


def create_module(code, name, name_ar, description="", version="1.0.0",
                  is_core=False, actor_email=None, actor_id=None, ip=None):
    """Create a new module in the catalog."""
    from database import db
    from security.models import ModuleCatalog
    from security.audit import record as audit_record

    if ModuleCatalog.query.filter_by(code=code).first():
        return {"success": False, "message": f"الوحدة '{code}' موجودة مسبقاً"}

    module = ModuleCatalog(
        code=code, name=name, name_ar=name_ar,
        description=description, version=version, is_core=is_core,
    )
    db.session.add(module)
    db.session.commit()

    audit_record(action="MODULE_CATALOG_CREATED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="module",
                 resource_id=module.id, ip=ip, new_value=code, result="SUCCESS")
    log.info("Created module %s (id=%d)", code, module.id)
    return {"success": True, "module": module.to_dict(), "message": f"تم إنشاء الوحدة '{name}'"}


def update_module(code, updates, actor_email=None, actor_id=None, ip=None):
    """Update a module in the catalog."""
    from database import db
    from security.models import ModuleCatalog
    from security.audit import record as audit_record

    module = ModuleCatalog.query.filter_by(code=code).first()
    if not module:
        return {"success": False, "message": f"الوحدة '{code}' غير موجودة"}

    old_values = {}
    for field in ["name", "name_ar", "description", "version", "is_active", "sort_order"]:
        if field in updates:
            old_values[field] = str(getattr(module, field))
            setattr(module, field, updates[field])

    db.session.commit()
    audit_record(action="MODULE_CATALOG_UPDATED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="module",
                 resource_id=module.id, ip=ip,
                 old_value=str(old_values), new_value=str(updates), result="SUCCESS")
    log.info("Updated module %s: %s", code, list(updates.keys()))
    return {"success": True, "module": module.to_dict(), "message": "تم تحديث الوحدة"}


def enable_module_for_company(company_id, module_code, actor_email=None, actor_id=None, ip=None):
    """Enable a module for a specific company."""
    from database import db
    from licensing.models import LicCompany
    from security.models import ModuleCatalog, CompanyModule
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    module = ModuleCatalog.query.filter_by(code=module_code, is_active=True).first()
    if not module:
        return {"success": False, "message": f"الوحدة '{module_code}' غير موجودة أو غير نشطة"}

    cm = CompanyModule.query.filter_by(company_id=company_id, module_code=module_code).first()
    if cm and cm.enabled:
        return {"success": False, "message": f"الوحدة '{module_code}' مفعلة مسبقاً"}

    if cm:
        cm.enabled = True
        cm.enabled_at = datetime.utcnow()
        cm.enabled_by = actor_email
        cm.disabled_at = None
        cm.disabled_by = None
    else:
        cm = CompanyModule(
            company_id=company_id, module_code=module_code,
            enabled=True, enabled_by=actor_email,
        )
        db.session.add(cm)

    db.session.commit()
    audit_record(action="MODULE_ENABLED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="module",
                 company_id=company_id, ip=ip, new_value=module_code, result="SUCCESS")
    log.info("Enabled module %s for company %d", module_code, company_id)
    return {"success": True, "module": cm.to_dict(), "message": f"تم تفعيل الوحدة '{module_code}'"}


def disable_module_for_company(company_id, module_code, actor_email=None, actor_id=None, ip=None):
    """Disable a module for a specific company."""
    from database import db
    from licensing.models import LicCompany
    from security.models import ModuleCatalog, CompanyModule
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    module = ModuleCatalog.query.filter_by(code=module_code).first()
    if module and module.is_core:
        return {"success": False, "message": "لا يمكن تعطيل الوحدات الأساسية"}

    cm = CompanyModule.query.filter_by(company_id=company_id, module_code=module_code).first()
    if not cm or not cm.enabled:
        return {"success": False, "message": f"الوحدة '{module_code}' غير مفعلة"}

    cm.enabled = False
    cm.disabled_at = datetime.utcnow()
    cm.disabled_by = actor_email
    db.session.commit()

    audit_record(action="MODULE_DISABLED", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="module",
                 company_id=company_id, ip=ip, new_value=module_code, result="SUCCESS")
    log.info("Disabled module %s for company %d", module_code, company_id)
    return {"success": True, "module": cm.to_dict(), "message": f"تم تعطيل الوحدة '{module_code}'"}


def get_company_modules(company_id):
    """List all modules for a company with their enabled status."""
    from database import db
    from licensing.models import LicCompany
    from security.models import ModuleCatalog, CompanyModule

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    all_modules = ModuleCatalog.query.filter_by(is_active=True).order_by(ModuleCatalog.sort_order).all()
    company_modules = {cm.module_code: cm for cm in
                       CompanyModule.query.filter_by(company_id=company_id).all()}

    result = []
    for m in all_modules:
        cm = company_modules.get(m.code)
        d = m.to_dict()
        d["enabled"] = cm.enabled if cm else False
        d["feature_flags"] = cm.feature_flags if cm else {}
        d["enabled_at"] = cm.enabled_at.isoformat() if cm and cm.enabled_at else None
        result.append(d)

    return {"success": True, "modules": result}


def set_feature_flag(company_id, module_code, flag_name, flag_value,
                     actor_email=None, actor_id=None, ip=None):
    """Set a feature flag for a company module."""
    from database import db
    from licensing.models import LicCompany
    from security.models import CompanyModule
    from security.audit import record as audit_record

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "الشركة غير موجودة"}

    cm = CompanyModule.query.filter_by(company_id=company_id, module_code=module_code).first()
    if not cm or not cm.enabled:
        return {"success": False, "message": f"الوحدة '{module_code}' غير مفعلة"}

    old_flags = dict(cm.feature_flags or {})
    flags = dict(cm.feature_flags or {})
    flags[flag_name] = flag_value
    cm.feature_flags = flags
    db.session.commit()

    audit_record(action="FEATURE_FLAG_SET", master_user_id=actor_id,
                 master_user_email=actor_email, resource_type="module",
                 company_id=company_id, ip=ip,
                 old_value=f"{flag_name}={old_flags.get(flag_name)}",
                 new_value=f"{flag_name}={flag_value}", result="SUCCESS")
    log.info("Set feature flag %s=%s for company %d module %s", flag_name, flag_value, company_id, module_code)
    return {"success": True, "feature_flags": flags, "message": f"تم تعيين العلامة '{flag_name}'"}


def check_company_module_access(company_id, module_code):
    """Check if a company has access to a specific module (combined plan + enable check)."""
    from database import db
    from licensing.models import LicCompany
    from security.models import CompanyModule
    from licensing.engine import can_access

    access = can_access(company_id)
    if not access["allowed"]:
        return {"success": True, "allowed": False, "reason": "subscription_invalid"}

    cm = CompanyModule.query.filter_by(company_id=company_id, module_code=module_code).first()
    if cm and cm.enabled:
        return {"success": True, "allowed": True, "feature_flags": cm.feature_flags or {}}

    return {"success": True, "allowed": False, "reason": "module_not_enabled"}
