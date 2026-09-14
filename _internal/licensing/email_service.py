# -*- coding: utf-8 -*-
"""Email notification service for 2TO ERP SaaS platform.

Sends transactional emails via SMTP with SSL/TLS support.
All emails are HTML formatted with RTL Arabic support.
"""
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


def _smtp_config() -> Dict[str, Any]:
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", "465")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASS", ""),
        "from_name": os.environ.get("SMTP_FROM_NAME", "2TO ERP"),
        "from_email": os.environ.get("SMTP_FROM", "noreply@2to-erp.com"),
    }


# ── Base Template ─────────────────────────────────────────────

_BASE_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${title}</title>
</head>
<body style="margin:0;padding:0;background-color:#0a0a14;font-family:'Segoe UI','Tahoma','Arial',sans-serif;direction:rtl;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0a0a14;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <!-- Header -->
  <tr><td style="padding:0 16px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#14b8a6,#0d9488);border-radius:16px 16px 0 0;padding:32px 40px;">
      <tr><td style="padding:32px 40px;">
        <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;letter-spacing:-0.5px;">${title}</h1>
        <p style="margin:6px 0 0;color:rgba(255,255,255,.85);font-size:14px;">2TO ERP</p>
      </td></tr>
    </table>
  </td></tr>

  <!-- Body -->
  <tr><td style="padding:0 16px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#111120;border-radius:0 0 16px 16px;padding:36px 40px;">
      <tr><td style="padding:36px 40px;color:#e4e4e7;font-size:15px;line-height:1.8;">
${content}
      </td></tr>
    </table>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:0 16px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="padding:20px 40px;">
      <tr><td style="color:#52525b;font-size:12px;line-height:1.7;text-align:center;padding:20px 40px;">
        <p style="margin:0 0 8px;">${footer}</p>
        <p style="margin:0;color:#3f3f46;font-size:11px;">&copy; ${year} 2TO ERP. جميع الحقوق محفوظة.</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</td></tr>
</table>
</body>
</html>
""")


def _build_html(title: str, content: str, footer: str = "") -> str:
    from datetime import datetime
    year = datetime.now().year
    if not footer:
        footer = "هذه رسالة تلقائية من نظام 2TO ERP — لا حاجة بالرد عليها."
    return _BASE_TEMPLATE.substitute(title=title, content=content, footer=footer, year=year)


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    cfg = _smtp_config()
    if not cfg["user"] or not cfg["password"]:
        log.warning("SMTP credentials not configured — skipping email to %s", to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{cfg['from_name']} <{cfg['from_email']}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        port = cfg["port"]
        if port == 465:
            with smtplib.SMTP_SSL(cfg["host"], port, context=ctx, timeout=15) as server:
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_email"], to_email, msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_email"], to_email, msg.as_string())
        log.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as e:
        log.error("Failed to send email to %s: %s", to_email, e)
        return False


# ── Welcome Email ─────────────────────────────────────────────

def send_welcome_email(
    to_email: str,
    company_name: str,
    admin_name: str,
    is_trial: bool = True,
    trial_days: int = 14,
    plan_name: str = "Basic",
) -> bool:
    trial_block = ""
    if is_trial:
        trial_block = f"""
<div style="background:rgba(20,184,166,.1);border:1px solid rgba(20,184,166,.25);border-radius:10px;padding:20px;margin:20px 0;">
  <p style="margin:0 0 6px;color:#14b8a6;font-weight:600;font-size:14px;">  فترة التجربة المجانية</p>
  <p style="margin:0;color:#a1a1aa;font-size:14px;">مدة التجربة: <strong style="color:#e4e4e7;">{trial_days} يوم</strong></p>
  <p style="margin:6px 0 0;color:#a1a1aa;font-size:14px;">الخطة الحالية: <strong style="color:#e4e4e7;">{plan_name}</strong></p>
</div>"""

    content = f"""
<p style="margin:0 0 12px;color:#e4e4e7;">مرحباً <strong style="color:#14b8a6;">{admin_name}</strong>،</p>
<p style="margin:0 0 16px;color:#a1a1aa;">تم إنشاء حسابك بنجاح. مرحباً بك في <strong style="color:#e4e4e7;">2TO ERP</strong>.</p>
<p style="margin:0 0 8px;color:#a1a1aa;">بيانات حسابك:</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.06);padding:16px 20px;margin:0 0 16px;">
  <tr><td style="padding:8px 0;color:#a1a1aa;font-size:13px;">الشركة</td><td style="padding:8px 0;color:#e4e4e7;font-size:13px;text-align:left;">{company_name}</td></tr>
  <tr><td style="padding:8px 0;color:#a1a1aa;font-size:13px;border-top:1px solid rgba(255,255,255,.06);">البريد الإلكتروني</td><td style="padding:8px 0;color:#e4e4e7;font-size:13px;border-top:1px solid rgba(255,255,255,.06);text-align:left;">{to_email}</td></tr>
  <tr><td style="padding:8px 0;color:#a1a1aa;font-size:13px;border-top:1px solid rgba(255,255,255,.06);">الخطة</td><td style="padding:8px 0;color:#e4e4e7;font-size:13px;border-top:1px solid rgba(255,255,255,.06);text-align:left;">{plan_name}</td></tr>
</table>
{trial_block}
<p style="margin:0;color:#a1a1aa;font-size:14px;">يمكنك تسجيل الدخول من خلال لوحة التحكم للبدء.</p>
"""
    return _send_email(to_email, f"مرحباً بك في 2TO ERP — {company_name}", _build_html("مرحباً بك في 2TO ERP", content))


# ── Trial Expiration Reminder ─────────────────────────────────

def send_trial_expiration_email(
    to_email: str,
    company_name: str,
    admin_name: str,
    days_remaining: int,
) -> bool:
    content = f"""
<p style="margin:0 0 12px;color:#e4e4e7;">مرحباً <strong style="color:#14b8a6;">{admin_name}</strong>،</p>
<p style="margin:0 0 16px;color:#a1a1aa;">فترة التجربة المجانية لحسابك على <strong style="color:#e4e4e7;">2TO ERP</strong> تقترب من النهاية.</p>
<div style="background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.25);border-radius:10px;padding:20px;margin:20px 0;text-align:center;">
  <p style="margin:0 0 4px;color:#fbbf24;font-size:28px;font-weight:700;">{days_remaining} يوم</p>
  <p style="margin:0;color:#a1a1aa;font-size:14px;">متبقي من فترة التجربة</p>
</div>
<p style="margin:0 0 8px;color:#a1a1aa;">لتجنب توقف الخدمة، يُرجى ترقية خطتك أو تجديد الاشتراك.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
  <tr><td style="text-align:center;">
    <a href="${{upgrade_url}}" style="display:inline-block;background:linear-gradient(135deg,#14b8a6,#0d9488);color:#ffffff;text-decoration:none;padding:12px 32px;border-radius:8px;font-weight:600;font-size:14px;">ترقية الخطط</a>
  </td></tr>
</table>
<p style="margin:0;color:#a1a1aa;font-size:13px;">الشركة: <strong style="color:#e4e4e7;">{company_name}</strong></p>
"""
    return _send_email(to_email, f"تذكير: اشتراك {company_name} ينتهي خلال {days_remaining} أيام", _build_html("تذكير: انتهاء فترة التجربة", content))


# ── Subscription Activated ────────────────────────────────────

def send_subscription_activated_email(
    to_email: str,
    company_name: str,
    admin_name: str,
    plan_name: str,
    end_date: str,
) -> bool:
    content = f"""
<p style="margin:0 0 12px;color:#e4e4e7;">مرحباً <strong style="color:#14b8a6;">{admin_name}</strong>،</p>
<p style="margin:0 0 16px;color:#a1a1aa;">تم تفعيل اشتراكك بنجاح على <strong style="color:#e4e4e7;">2TO ERP</strong>.</p>
<div style="background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.25);border-radius:10px;padding:20px;margin:20px 0;">
  <p style="margin:0 0 6px;color:#34d399;font-weight:600;font-size:14px;">  اشتراك مفعّل</p>
  <p style="margin:0;color:#a1a1aa;font-size:14px;">الخطة: <strong style="color:#e4e4e7;">{plan_name}</strong></p>
  <p style="margin:6px 0 0;color:#a1a1aa;font-size:14px;">تاريخ الانتهاء: <strong style="color:#e4e4e7;">{end_date}</strong></p>
</div>
<p style="margin:0;color:#a1a1aa;font-size:14px;">يمكنك الآن الاستمتاع بجميع ميزات خطتك.</p>
"""
    return _send_email(to_email, f"تم تفعيل اشتراكك — {company_name}", _build_html("تم تفعيل الاشتراك بنجاح", content))


# ── Subscription Expired ──────────────────────────────────────

def send_subscription_expired_email(
    to_email: str,
    company_name: str,
    admin_name: str,
) -> bool:
    content = f"""
<p style="margin:0 0 12px;color:#e4e4e7;">مرحباً <strong style="color:#14b8a6;">{admin_name}</strong>،</p>
<p style="margin:0 0 16px;color:#a1a1aa;">اشتراكك على <strong style="color:#e4e4e7;">2TO ERP</strong> قد انتهى.</p>
<div style="background:rgba(248,113,113,.1);border:1px solid rgba(248,113,113,.25);border-radius:10px;padding:20px;margin:20px 0;">
  <p style="margin:0 0 6px;color:#f87171;font-weight:600;font-size:14px;">  اشتراك منتهي</p>
  <p style="margin:0;color:#a1a1aa;font-size:14px;">جميع البيانات محفوظة وستبقى متاحة عند التجديد خلال فترة السماح.</p>
</div>
<p style="margin:0 0 8px;color:#a1a1aa;">يُرجى تجديد اشتراكك للحفاظ على وصولك للنظام.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
  <tr><td style="text-align:center;">
    <a href="${{renew_url}}" style="display:inline-block;background:linear-gradient(135deg,#14b8a6,#0d9488);color:#ffffff;text-decoration:none;padding:12px 32px;border-radius:8px;font-weight:600;font-size:14px;">تجديد الاشتراك</a>
  </td></tr>
</table>
<p style="margin:0;color:#a1a1aa;font-size:13px;">الشركة: <strong style="color:#e4e4e7;">{company_name}</strong></p>
"""
    return _send_email(to_email, f"انتهاء الاشتراك — {company_name}", _build_html("انتهاء الاشتراك", content))


# ── Payment Received ──────────────────────────────────────────

def send_payment_received_email(
    to_email: str,
    company_name: str,
    admin_name: str,
    amount: float,
    currency: str = "EGP",
    payment_method: str = "cash",
    reference_no: str = "",
) -> bool:
    ref_block = ""
    if reference_no:
        ref_block = f"""
  <tr><td style="padding:8px 0;color:#a1a1aa;font-size:13px;border-top:1px solid rgba(255,255,255,.06);">رقم المرجع</td>
      <td style="padding:8px 0;color:#e4e4e7;font-size:13px;border-top:1px solid rgba(255,255,255,.06);text-align:left;">{reference_no}</td></tr>"""

    content = f"""
<p style="margin:0 0 12px;color:#e4e4e7;">مرحباً <strong style="color:#14b8a6;">{admin_name}</strong>،</p>
<p style="margin:0 0 16px;color:#a1a1aa;">تم استلام دفعتك على <strong style="color:#e4e4e7;">2TO ERP</strong> وتسجيلها بنجاح.</p>
<div style="background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.25);border-radius:10px;padding:20px;margin:20px 0;">
  <p style="margin:0 0 6px;color:#34d399;font-weight:600;font-size:14px;">  تم استلام الدفعة</p>
</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,.04);border-radius:10px;border:1px solid rgba(255,255,255,.06);padding:16px 20px;margin:0 0 16px;">
  <tr><td style="padding:8px 0;color:#a1a1aa;font-size:13px;">المبلغ</td>
      <td style="padding:8px 0;color:#e4e4e7;font-size:15px;font-weight:600;text-align:left;">{amount:,.2f} {currency}</td></tr>
  <tr><td style="padding:8px 0;color:#a1a1aa;font-size:13px;border-top:1px solid rgba(255,255,255,.06);">طريقة الدفع</td>
      <td style="padding:8px 0;color:#e4e4e7;font-size:13px;border-top:1px solid rgba(255,255,255,.06);text-align:left;">{payment_method}</td></tr>
  {ref_block}
</table>
<p style="margin:0;color:#a1a1aa;font-size:13px;">الشركة: <strong style="color:#e4e4e7;">{company_name}</strong></p>
"""
    return _send_email(to_email, f"تأكيد استلام الدفعة — {company_name}", _build_html("تم استلام الدفعة بنجاح", content))


# ── Password Reset ────────────────────────────────────────────

def send_password_reset_email(
    to_email: str,
    admin_name: str,
    reset_token: str,
    base_url: str = "",
) -> bool:
    reset_link = f"{base_url}/reset-password?token={reset_token}" if base_url else "#"
    content = f"""
<p style="margin:0 0 12px;color:#e4e4e7;">مرحباً <strong style="color:#14b8a6;">{admin_name}</strong>،</p>
<p style="margin:0 0 16px;color:#a1a1aa;">تم طلب إعادة تعيين كلمة المرور لحسابك على <strong style="color:#e4e4e7;">2TO ERP</strong>.</p>
<p style="margin:0 0 16px;color:#a1a1aa;">اضغط على الزر أدناه لإعادة تعيين كلمة المرور:</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
  <tr><td style="text-align:center;">
    <a href="{reset_link}" style="display:inline-block;background:linear-gradient(135deg,#14b8a6,#0d9488);color:#ffffff;text-decoration:none;padding:12px 32px;border-radius:8px;font-weight:600;font-size:14px;">إعادة تعيين كلمة المرور</a>
  </td></tr>
</table>
<div style="background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.25);border-radius:10px;padding:16px;margin:20px 0;">
  <p style="margin:0;color:#fbbf24;font-size:13px;">  هذا الرابط صالح لمدة ساعة واحدة فقط.</p>
</div>
<p style="margin:0;color:#a1a1aa;font-size:13px;">إذا لم تطلب إعادة تعيين كلمة المرور، يُرجى تجاهل هذه الرسالة.</p>
"""
    return _send_email(to_email, "إعادة تعيين كلمة المرور — 2TO ERP", _build_html("إعادة تعيين كلمة المرور", content))


# ── Test Email ────────────────────────────────────────────────

def send_test_email(to_email: str) -> bool:
    content = f"""
<p style="margin:0 0 12px;color:#e4e4e7;">هذه رسالة اختبار من نظام <strong style="color:#14b8a6;">2TO ERP</strong>.</p>
<p style="margin:0 0 8px;color:#a1a1aa;">تم إعداد خدمة البريد الإلكتروني بنجاح.</p>
<div style="background:rgba(20,184,166,.1);border:1px solid rgba(20,184,166,.25);border-radius:10px;padding:20px;margin:20px 0;">
  <p style="margin:0;color:#14b8a6;font-weight:600;font-size:14px;">  إعداد SMTP يعمل بشكل صحيح</p>
</div>
<p style="margin:0;color:#a1a1aa;font-size:13px;">الوقت: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""
    return _send_email(to_email, "رسالة اختبار — 2TO ERP", _build_html("اختبار إعداد البريد الإلكتروني", content))
