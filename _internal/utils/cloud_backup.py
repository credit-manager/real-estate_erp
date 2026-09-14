"""النسخ الاحتياطي السحابي — WebDAV و S3 (متناسق) بلا أي اعتماد خارجي.

يدفع محتوى النسخة الاحتياطية (المشفّرة أصلاً) إلى تخزين خارجي:
  - WebDAV: PUT مع مصادقة أساسية (Basic Auth).
  - S3 المتناسق (AWS / MinIO / R2 ...): PUT بتوقيع AWS Signature V4 (Path-Style).

يُبنى كل شيء على المكتبة القياسية فقط (urllib + hmac) ليظل البرنامج خفيفاً
وبدون اتصالات إضافية.
"""
import base64
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib import request as urlrequest
from urllib.parse import quote, urlparse

log = logging.getLogger(__name__)


def _basic_auth(username: str, password: str) -> str:
    raw = f"{username or ''}:{password or ''}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


# ============ WebDAV ============

def webdav_put(base_url: str, username: str, password: str,
               filename: str, content: bytes) -> int:
    """PUT محتوى إلى خادم WebDAV. يعيد رمز حالة HTTP."""
    url = base_url.rstrip("/") + "/" + quote(filename.replace("/", "%2F").strip())
    req = urlrequest.Request(url, data=content, method="PUT")
    req.add_header("Content-Type", "application/octet-stream")
    if username or password:
        req.add_header("Authorization", _basic_auth(username, password))
    with urlrequest.urlopen(req, timeout=30) as resp:
        return resp.status


# ============ S3 (AWS Signature V4, Path-Style) ============

def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def s3_put(endpoint: str, bucket: str, region: str,
           access_key: str, secret_key: str,
           filename: str, content: bytes) -> int:
    """PUT محتوى إلى S3 متناسق بتوقيع V4 (Path-Style). يعيد رمز حالة HTTP."""
    endpoint = endpoint.rstrip("/")
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("endpoint_url غير صالح")
    host = parsed.netloc

    bucket_key = quote(bucket, safe="") + "/" + quote(filename, safe="")
    canonical_uri = "/" + bucket_key

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(content).hexdigest()

    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    signed_headers = ";".join(sorted(headers))

    canonical_request = (
        "PUT\n"
        f"{canonical_uri}\n"
        "\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    scope = f"{date_stamp}/{region or 'us-east-1'}/s3/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n"
        f"{scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    k_date = _sign((f"AWS4{secret_key}").encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region or "us-east-1")
    k_service = _sign(k_region, "s3")
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"),
                         hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    req = urlrequest.Request(
        f"{endpoint}{canonical_uri}",
        data=content, method="PUT",
        headers={
            "Authorization": authorization,
            "X-Amz-Date": amz_date,
            "X-Amz-Content-Sha256": payload_hash,
            "Content-Type": "application/octet-stream",
        },
    )
    with urlrequest.urlopen(req, timeout=30) as resp:
        return resp.status


def _mask(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return value[:3] + "…" + value[-3:]


def push_backup(content: bytes, filename: str, settings) -> Tuple[bool, str]:
    """يدفع محتوى النسخة الاحتياطية وفق الإعدادات.

    `settings` أي كائن يوفّر `get(key, default)` (كود utils.settings أو dict).
    يعيد (نجحت، رسالة/خطأ).
    """
    enabled = str(settings.get("backup_cloud_enabled", "0")) in ("1", "true", "True")
    if not enabled:
        return False, "cloud.disabled"
    ctype = (settings.get("backup_cloud_type", "") or "").strip().lower()
    if not ctype:
        return False, "cloud.not_configured"

    try:
        if ctype == "webdav":
            status = webdav_put(
                settings.get("backup_cloud_url", ""),
                settings.get("backup_cloud_user", ""),
                settings.get("backup_cloud_secret", ""),
                filename, content,
            )
        elif ctype == "s3":
            status = s3_put(
                settings.get("backup_cloud_url", ""),
                settings.get("backup_cloud_bucket", ""),
                settings.get("backup_cloud_region", ""),
                settings.get("backup_cloud_user", ""),
                settings.get("backup_cloud_secret", ""),
                filename, content,
            )
        else:
            return False, "cloud.unknown_type"
    except Exception as exc:  # noqa: BLE001 — تحويل كل أخطاء المنصة لرسالة واضحة
        log.warning("Cloud backup push failed: %s", exc)
        return False, str(exc)

    ok = 200 <= status < 300
    return ok, f"HTTP {status}" if not ok else ""