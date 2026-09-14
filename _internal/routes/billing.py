# -*- coding: utf-8 -*-
"""Company Billing Portal routes.

Self-service page where company admins can view their subscription,
invoices, and manage billing.
"""
from flask import Blueprint, request, jsonify, session, render_template
from datetime import date, timedelta
from decimal import Decimal
from database import db
from licensing.models import LicCompany, LicSubscription, LicPlan, LicPayment, LicCompanyUser
from licensing.auth import is_company_user_logged_in, get_company_session_data
from security.billing import create_payment, payment_history
from security.audit import record as audit_record
import logging

log = logging.getLogger(__name__)

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


def require_company_auth():
    """Decorator to require company user authentication."""
    def decorator(f):
        def wrapped(*args, **kwargs):
            if not is_company_user_logged_in():
                return jsonify({"success": False, "message": "Unauthorized"}), 401
            return f(*args, **kwargs)
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator


def get_current_company() -> LicCompany | None:
    """Get the current company from session."""
    data = get_company_session_data()
    if not data:
        return None
    return db.session.get(LicCompany, data["company_id"])


def require_admin_role():
    """Decorator to require admin role within company."""
    def decorator(f):
        def wrapped(*args, **kwargs):
            data = get_company_session_data()
            if not data or data.get("role") not in ("admin", "owner"):
                return jsonify({"success": False, "message": "Admin access required"}), 403
            return f(*args, **kwargs)
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator


# ── Page Routes ────────────────────────────────────────────────

@billing_bp.route("/")
@require_company_auth()
def billing_portal() -> str:
    """Serve the billing portal page."""
    return render_template("billing_portal.html")


# ── API: Subscription ──────────────────────────────────────────

@billing_bp.route("/api/subscription", methods=["GET"])
@require_company_auth()
def get_subscription() -> tuple:
    """Get current subscription info (plan, status, end date, user count)."""
    company = get_current_company()
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    sub = company.active_subscription
    if not sub:
        return jsonify({"success": False, "message": "No active subscription"}), 404

    # Get current user count for this company
    user_count = LicCompanyUser.query.filter_by(company_id=company.id, is_active=True).count()

    # Get plan details
    plan = sub.plan
    plan_data = None
    if plan:
        plan_data = {
            "id": plan.id,
            "code": plan.code,
            "name": plan.name,
            "name_ar": plan.name_ar,
            "max_users": plan.max_users,
            "max_projects": plan.max_projects,
            "max_storage_mb": plan.max_storage_mb,
            "modules": plan.modules or {},
            "price_monthly": float(plan.price_monthly) if plan.price_monthly else None,
            "price_yearly": float(plan.price_yearly) if plan.price_yearly else None,
            "badge": plan.badge,
            "badge_color": plan.badge_color,
            "badge_bg": plan.badge_bg,
            "icon": plan.icon,
            "gradient": plan.gradient,
        }

    # Compute days remaining
    days_remaining = (sub.end_date - date.today()).days
    computed_status = sub.check_status()

    return jsonify({
        "success": True,
        "subscription": {
            "id": sub.id,
            "plan_id": sub.plan_id,
            "plan": plan_data,
            "start_date": sub.start_date.isoformat() if sub.start_date else None,
            "end_date": sub.end_date.isoformat() if sub.end_date else None,
            "status": sub.status,
            "computed_status": computed_status,
            "auto_renew": sub.auto_renew,
            "days_remaining": days_remaining,
            "is_usable": sub.is_usable,
        },
        "user_count": user_count,
        "can_upgrade": computed_status in ("trial", "active", "grace"),
        "can_cancel": computed_status in ("trial", "active", "grace"),
    })


# ── API: Invoices ──────────────────────────────────────────────

@billing_bp.route("/api/invoices", methods=["GET"])
@require_company_auth()
def list_invoices() -> tuple:
    """List invoices (payments) with pagination."""
    company = get_current_company()
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 20))))
    status_filter = request.args.get("status")

    query = LicPayment.query.filter_by(company_id=company.id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    total = query.count()
    payments = query.order_by(LicPayment.id.desc()).offset((page - 1) * per_page).limit(per_page).all()

    invoices = []
    for p in payments:
        d = p.to_dict()
        # Add invoice-specific fields
        d["invoice_number"] = f"INV-{p.id:06d}"
        d["due_date"] = p.paid_at.isoformat() if p.paid_at else None
        invoices.append(d)

    return jsonify({
        "success": True,
        "invoices": invoices,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        }
    })


# ── API: Upgrade/Downgrade Plan ────────────────────────────────

@billing_bp.route("/api/upgrade", methods=["POST"])
@require_company_auth()
@require_admin_role()
def upgrade_plan() -> tuple:
    """Upgrade or downgrade subscription plan."""
    company = get_current_company()
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    data = request.get_json(silent=True) or {}
    new_plan_code = data.get("plan_code")
    billing_cycle = data.get("billing_cycle", "monthly")  # monthly or yearly

    if not new_plan_code:
        return jsonify({"success": False, "message": "Plan code required"}), 400

    new_plan = LicPlan.query.filter_by(code=new_plan_code, is_active=True).first()
    if not new_plan:
        return jsonify({"success": False, "message": "Invalid plan"}), 400

    current_sub = company.active_subscription
    if not current_sub:
        return jsonify({"success": False, "message": "No active subscription to upgrade"}), 400

    # Check if trying to upgrade to same plan
    if current_sub.plan_id == new_plan.id:
        return jsonify({"success": False, "message": "Already on this plan"}), 400

    # Calculate new end date based on billing cycle
    if billing_cycle == "yearly":
        new_end_date = current_sub.end_date + timedelta(days=365)
        amount = float(new_plan.price_yearly) if new_plan.price_yearly else 0
    else:
        new_end_date = current_sub.end_date + timedelta(days=30)
        amount = float(new_plan.price_monthly) if new_plan.price_monthly else 0

    # Create payment record for the plan change
    payment_result = create_payment(
        company_id=company.id,
        amount=amount,
        currency="EGP",
        payment_method="plan_change",
        reference_no=f"PLAN-CHANGE-{new_plan_code}",
        subscription_id=current_sub.id,
        actor_email=session.get("lic_company_user_email"),
        actor_id=session.get("lic_company_user_id"),
        ip=request.remote_addr,
    )

    if not payment_result.get("success"):
        return jsonify(payment_result), 400

    # Update subscription
    old_plan_code = current_sub.plan.code if current_sub.plan else None
    current_sub.plan_id = new_plan.id
    current_sub.end_date = new_end_date
    current_sub.auto_renew = True
    db.session.commit()

    audit_record(
        action="SUBSCRIPTION_PLAN_CHANGED",
        master_user_id=session.get("lic_company_user_id"),
        master_user_email=session.get("lic_company_user_email"),
        resource_type="subscription",
        resource_id=current_sub.id,
        company_id=company.id,
        ip=request.remote_addr,
        old_value=old_plan_code,
        new_value=new_plan_code,
        result="SUCCESS",
    )

    return jsonify({
        "success": True,
        "message": f"Plan changed to {new_plan.name}",
        "subscription": {
            "id": current_sub.id,
            "plan_id": new_plan.id,
            "plan_code": new_plan.code,
            "end_date": current_sub.end_date.isoformat(),
            "auto_renew": current_sub.auto_renew,
        },
        "payment": payment_result.get("payment"),
    })


# ── API: Cancel Subscription ───────────────────────────────────

@billing_bp.route("/api/cancel", methods=["POST"])
@require_company_auth()
@require_admin_role()
def cancel_subscription() -> tuple:
    """Cancel current subscription."""
    company = get_current_company()
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    current_sub = company.active_subscription
    if not current_sub:
        return jsonify({"success": False, "message": "No active subscription"}), 400

    if current_sub.status == "cancelled":
        return jsonify({"success": False, "message": "Subscription already cancelled"}), 400

    data = request.get_json(silent=True) or {}
    immediate = data.get("immediate", False)

    old_status = current_sub.status
    if immediate:
        current_sub.status = "cancelled"
        current_sub.end_date = date.today()
    else:
        current_sub.auto_renew = False
        # Keep access until end_date
        current_sub.status = "cancelled"

    db.session.commit()

    audit_record(
        action="SUBSCRIPTION_CANCELLED",
        master_user_id=session.get("lic_company_user_id"),
        master_user_email=session.get("lic_company_user_email"),
        resource_type="subscription",
        resource_id=current_sub.id,
        company_id=company.id,
        ip=request.remote_addr,
        old_value=old_status,
        new_value="cancelled",
        result="SUCCESS",
    )

    return jsonify({
        "success": True,
        "message": "Subscription cancelled" + (" immediately" if immediate else " (will not renew)"),
        "subscription": {
            "id": current_sub.id,
            "status": current_sub.status,
            "end_date": current_sub.end_date.isoformat(),
            "auto_renew": current_sub.auto_renew,
        },
    })


# ── API: Payment Methods ───────────────────────────────────────

@billing_bp.route("/api/payment-methods", methods=["GET"])
@require_company_auth()
def get_payment_methods() -> tuple:
    """Get saved payment methods for the company."""
    company = get_current_company()
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    # In a real implementation, this would fetch from a payment_methods table
    # For now, return a placeholder structure
    # TODO: Add LicPaymentMethod model when integrating with payment gateway

    return jsonify({
        "success": True,
        "payment_methods": [],
        "message": "Payment methods storage not yet implemented",
    })


@billing_bp.route("/api/payment-methods", methods=["POST"])
@require_company_auth()
@require_admin_role()
def add_payment_method() -> tuple:
    """Add a new payment method (stub for payment gateway integration)."""
    company = get_current_company()
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    data = request.get_json(silent=True) or {}
    method_type = data.get("type")  # card, bank_transfer, wallet
    token = data.get("token")  # Payment gateway token

    if not method_type or not token:
        return jsonify({"success": False, "message": "Type and token required"}), 400

    # TODO: Integrate with payment gateway (Stripe, PayPal, local provider)
    # For now, return a stub response
    audit_record(
        action="PAYMENT_METHOD_ADDED",
        master_user_id=session.get("lic_company_user_id"),
        master_user_email=session.get("lic_company_user_email"),
        resource_type="payment_method",
        resource_id=0,
        company_id=company.id,
        ip=request.remote_addr,
        new_value=f"type={method_type}",
        result="SUCCESS",
    )

    return jsonify({
        "success": True,
        "message": "Payment method added (stub)",
        "payment_method": {
            "id": 0,
            "type": method_type,
            "last4": "****",
            "is_default": True,
        },
    })


# ── API: Available Plans ───────────────────────────────────────

@billing_bp.route("/api/plans", methods=["GET"])
@require_company_auth()
def list_available_plans() -> tuple:
    """List all available plans for upgrade/downgrade."""
    company = get_current_company()
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    plans = LicPlan.query.filter_by(is_active=True).order_by(LicPlan.sort_order).all()

    current_sub = company.active_subscription
    current_plan_id = current_sub.plan_id if current_sub else None

    result = []
    for plan in plans:
        plan_dict = plan.to_dict()
        plan_dict["is_current"] = (plan.id == current_plan_id)
        plan_dict["is_upgrade"] = False
        plan_dict["is_downgrade"] = False
        if current_sub and current_sub.plan:
            if plan.max_users > current_sub.plan.max_users:
                plan_dict["is_upgrade"] = True
            elif plan.max_users < current_sub.plan.max_users:
                plan_dict["is_downgrade"] = True
        result.append(plan_dict)

    return jsonify({"success": True, "plans": result})


# ── API: Billing Summary ───────────────────────────────────────

@billing_bp.route("/api/summary", methods=["GET"])
@require_company_auth()
def billing_summary() -> tuple:
    """Get billing summary for dashboard."""
    company = get_current_company()
    if not company:
        return jsonify({"success": False, "message": "Company not found"}), 404

    sub = company.active_subscription
    user_count = LicCompanyUser.query.filter_by(company_id=company.id, is_active=True).count()

    # Get payment stats
    payments = LicPayment.query.filter_by(company_id=company.id).all()
    total_paid = sum(float(p.amount) for p in payments if p.status == "confirmed")
    total_pending = sum(float(p.amount) for p in payments if p.status == "pending")

    # Next billing date
    next_billing = None
    if sub and sub.auto_renew and sub.end_date:
        next_billing = sub.end_date.isoformat()

    return jsonify({
        "success": True,
        "summary": {
            "current_plan": sub.plan.to_dict() if sub and sub.plan else None,
            "subscription_status": sub.check_status() if sub else None,
            "subscription_end": sub.end_date.isoformat() if sub else None,
            "next_billing_date": next_billing,
            "auto_renew": sub.auto_renew if sub else False,
            "user_count": user_count,
            "max_users": sub.plan.max_users if sub and sub.plan else 0,
            "total_paid": total_paid,
            "total_pending": total_pending,
            "invoice_count": len(payments),
        },
    })