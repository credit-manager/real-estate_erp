# -*- coding: utf-8 -*-
"""Automated company onboarding for DynamicPro ERP."""
import logging
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

from database import db
from licensing.models import LicCompany, LicSubscription, LicLicense, LicPlan, LicCompanyUser
from licensing.db_manager import create_company_db, generate_db_name
from licensing.engine import generate_license_key
from licensing.plans_data import TRIAL_DAYS, GRACE_PERIOD_DAYS

log = logging.getLogger(__name__)

DEFAULT_TEMP_PASSWORD = "Admin@123"


def create_company(name, name_ar=None, email=None, phone=None, tax_number=None, address=None, is_trial=True, plan_code="basic", subscription_days=None, admin_password=None, admin_full_name=None):
    try:
        # Auto-assign next available port (2222+)
        last = LicCompany.query.order_by(LicCompany.port.desc()).first()
        next_port = max(2222, (last.port + 1) if last and last.port else 2222)

        company = LicCompany(
            name=name, name_ar=name_ar or name, email=email, phone=phone,
            tax_number=tax_number, address=address, status="active", is_trial=is_trial,
            db_name="pending", port=next_port,
            trial_ends_at=date.today() + timedelta(days=TRIAL_DAYS) if is_trial else None,
        )
        db.session.add(company)
        db.session.flush()
        company.db_name = generate_db_name(company.id, name)
        db.session.commit()
        log.info("Created company: %s (id=%d)", name, company.id)

        db_ok = create_company_db(company)
        if not db_ok:
            log.warning("DB creation failed for company %d, continuing without separate DB", company.id)

        plan = LicPlan.query.filter_by(code=plan_code, is_active=True).first()
        if not plan:
            plan = LicPlan.query.filter_by(code="basic").first()

        today = date.today()
        if subscription_days and subscription_days > 0:
            days = subscription_days
        else:
            days = TRIAL_DAYS if is_trial else 365

        subscription = LicSubscription(
            company_id=company.id, plan_id=plan.id,
            start_date=today, end_date=today + timedelta(days=days),
            status="trial" if is_trial else "active",
        )
        db.session.add(subscription)
        db.session.flush()

        license = LicLicense(
            company_id=company.id, subscription_id=subscription.id,
            license_key=generate_license_key(), status="active",
            issued_at=today, expires_at=today + timedelta(days=days),
        )
        db.session.add(license)
        db.session.commit()

        admin = None
        if email:
            admin = create_company_admin(
                company.id, email,
                password=admin_password or DEFAULT_TEMP_PASSWORD,
                full_name=admin_full_name,
            )

        log.info("Onboarding complete for %s: sub=%d, lic=%s", name, subscription.id, license.license_key)
        return {"success": True, "company": company, "subscription": subscription, "license": license, "admin": admin, "message": f"Company '{name}' created"}

    except Exception as e:
        log.error("Onboarding failed for '%s': %s", name, e)
        db.session.rollback()
        return {"success": False, "company": None, "message": str(e)}


def create_company_admin(company_id, email, password, full_name=None):
    """Create an admin user for a company.

    Steps:
    1. Insert user into the company's separate DB (users table)
    2. Insert LicCompanyUser into master DB (maps email → company)
    """
    from licensing.db_manager import get_company_engine
    from sqlalchemy import text

    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "Company not found"}

    password_hash = generate_password_hash(password)
    username = email.split("@")[0]

    # Step 1: Insert into company DB
    try:
        engine = get_company_engine(company)
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM users WHERE email = :email"), {"email": email}
            ).scalar()
            if not existing:
                conn.execute(text(
                    "INSERT INTO users (username, email, password_hash, full_name, role, is_active) "
                    "VALUES (:username, :email, :password_hash, :full_name, 'admin', true)"
                ), {
                    "username": username, "email": email,
                    "password_hash": password_hash,
                    "full_name": full_name or username,
                })
                conn.commit()
    except Exception as e:
        log.warning("Could not insert user into company DB %s: %s", company.db_name, e)

    # Step 2: Insert into master DB (LicCompanyUser)
    existing_master = LicCompanyUser.query.filter_by(
        company_id=company_id, email=email
    ).first()
    if not existing_master:
        cu = LicCompanyUser(
            company_id=company_id, email=email,
            password_hash=password_hash, full_name=full_name or username,
            role="admin", is_active=True,
        )
        db.session.add(cu)
        db.session.commit()
        log.info("Created LicCompanyUser %s for company %d", email, company_id)

    log.info("Created admin user %s for company %d", email, company_id)
    return {"success": True, "message": f"Admin user '{email}' created"}


def suspend_company(company_id):
    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "Company not found"}
    company.status = "suspended"
    db.session.commit()
    log.info("Suspended company %d (%s)", company_id, company.name)
    return {"success": True, "message": f"Company '{company.name}' suspended"}


def reactivate_company(company_id):
    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "Company not found"}
    company.status = "active"
    db.session.commit()
    log.info("Reactivated company %d (%s)", company_id, company.name)
    return {"success": True, "message": f"Company '{company.name}' reactivated"}


def upgrade_plan(company_id, new_plan_code):
    company = db.session.get(LicCompany, company_id)
    if not company:
        return {"success": False, "message": "Company not found"}

    new_plan = LicPlan.query.filter_by(code=new_plan_code, is_active=True).first()
    if not new_plan:
        return {"success": False, "message": f"Plan '{new_plan_code}' not found"}

    sub = LicSubscription.query.filter(
        LicSubscription.company_id == company_id,
        LicSubscription.status.in_(["trial", "active", "grace"]),
    ).order_by(LicSubscription.id.desc()).first()

    if sub:
        sub.plan_id = new_plan.id
        db.session.commit()
        log.info("Upgraded company %d to plan %s", company_id, new_plan_code)
        return {"success": True, "message": f"Upgraded to {new_plan.name}"}

    return {"success": False, "message": "No active subscription found"}
