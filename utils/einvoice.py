"""التكامل مع منظومات الفاتورة الإلكترونية في جميع الدول العربية (22 دولة).

البنية: طبقة توحيد (Unified) فوق موصّلات لكل دولة. كل موصّل يترجم الفاتورة
الداخلية إلى صيغة المنظومة المحلية، يرسلها، ويعيد حالة موحدة
(pending / submitted / accepted / rejected) مع مرجع المنظومة.

الدول المدعومة (22 دولة عربية):
  نشط (API): مصر (ETA) | السعودية (ZATCA) | تونس (TTN) | المغرب (DGI)
  عبر مزود: الإمارات (FTA) | عُمان (OTA) | الأردن (JOFOTARA) | البحرين (NBR)
  قيد الإعداد: الجزائر (DGI) | قطر (GTA)
  offline: الكويت | العراق | لبنان | ليبيا | السودان | اليمن | فلسطين | سوريا | جيبوتي | الصومال | جزر القمر | موريتانيا

الاستخدام:
    from utils.einvoice import submit_invoice, get_status
    result = submit_invoice(invoice)
    get_status(invoice)
"""
import base64
import hashlib
import json as _json
import uuid
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests

from database import db
from utils.errlog import log_exc

# ============================================================
# الدول ومنظماتها (22 دولة عربية)
# ============================================================

COUNTRIES = {
    "EG": {"name": "مصر", "name_en": "Egypt", "authority": "ETA",
           "default_mode": "clearance", "b2c_mode": "reporting",
           "currency": "EGP", "vat_rates": [0, 5, 10, 14]},
    "SA": {"name": "السعودية", "name_en": "Saudi Arabia", "authority": "ZATCA",
           "default_mode": "clearance", "b2c_mode": "reporting",
           "currency": "SAR", "vat_rates": [0, 5, 15]},
    "TN": {"name": "تونس", "name_en": "Tunisia", "authority": "TTN",
           "default_mode": "clearance", "b2c_mode": "reporting",
           "currency": "TND", "vat_rates": [0, 7, 13, 19]},
    "MA": {"name": "المغرب", "name_en": "Morocco", "authority": "DGI",
           "default_mode": "clearance", "b2c_mode": "reporting",
           "currency": "MAD", "vat_rates": [0, 7, 14, 20]},
    "AE": {"name": "الإمارات", "name_en": "UAE", "authority": "FTA",
           "default_mode": "reporting", "b2c_mode": "reporting",
           "currency": "AED", "vat_rates": [0, 5]},
    "OM": {"name": "عُمان", "name_en": "Oman", "authority": "OTA",
           "default_mode": "reporting", "b2c_mode": "reporting",
           "currency": "OMR", "vat_rates": [0, 5]},
    "JO": {"name": "الأردن", "name_en": "Jordan", "authority": "JOFOTARA",
           "default_mode": "reporting", "b2c_mode": "reporting",
           "currency": "JOD", "vat_rates": [0, 5, 10, 16]},
    "BH": {"name": "البحرين", "name_en": "Bahrain", "authority": "NBR",
           "default_mode": "reporting", "b2c_mode": "reporting",
           "currency": "BHD", "vat_rates": [0, 5, 10]},
    "DZ": {"name": "الجزائر", "name_en": "Algeria", "authority": "DGI-DZ",
           "default_mode": "clearance", "b2c_mode": "reporting",
           "currency": "DZD", "vat_rates": [0, 9, 19],
           "note": "متوقع 2027"},
    "QA": {"name": "قطر", "name_en": "Qatar", "authority": "GTA",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "QAR", "vat_rates": [0, 5],
           "note": "قانون معتمد 2026"},
    "KW": {"name": "الكويت", "name_en": "Kuwait", "authority": "Kuwait-Tax",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "KWD", "vat_rates": [0]},
    "IQ": {"name": "العراق", "name_en": "Iraq", "authority": "GCT",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "IQD", "vat_rates": [0, 10, 20, 30]},
    "LB": {"name": "لبنان", "name_en": "Lebanon", "authority": "MOF",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "LBP", "vat_rates": [0, 11]},
    "LY": {"name": "ليبيا", "name_en": "Libya", "authority": "LTD",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "LYD", "vat_rates": [0]},
    "SD": {"name": "السودان", "name_en": "Sudan", "authority": "TRA",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "SDG", "vat_rates": [0, 10, 15, 20]},
    "PS": {"name": "فلسطين", "name_en": "Palestine", "authority": "PNA",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "ILS", "vat_rates": [0, 14.5, 16]},
    "SY": {"name": "سوريا", "name_en": "Syria", "authority": "SyriaTax",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "SYP", "vat_rates": [0, 1, 4, 5, 7, 10, 15]},
    "DJ": {"name": "جيبوتي", "name_en": "Djibouti", "authority": "DjiboutiTax",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "DJF", "vat_rates": [0, 10]},
    "SO": {"name": "الصومال", "name_en": "Somalia", "authority": "SomaliaTax",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "SOS", "vat_rates": [0, 5, 10]},
    "KM": {"name": "جزر القمر", "name_en": "Comoros", "authority": "ComorosTax",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "KMF", "vat_rates": [0]},
    "MR": {"name": "موريتانيا", "name_en": "Mauritania", "authority": "MauritaniaTax",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "MRU", "vat_rates": [0, 14, 16]},
    "YE": {"name": "اليمن", "name_en": "Yemen", "authority": "YemenTax",
           "default_mode": "offline", "b2c_mode": "offline",
           "currency": "YER", "vat_rates": [0, 5]},
}


def _settings():
    import utils.settings as settings_module
    return settings_module


def einvoice_config():
    s = _settings()
    country = (s.get("einv_country") or "EG").upper()
    return {
        "country": country,
        "enabled": s.get_bool("einv_enabled", False),
        "mode": s.get("einv_mode") or COUNTRIES.get(country, {}).get("default_mode", "offline"),
        "environment": s.get("eenv_environment") or "preprod",
        "client_id": s.get("einv_client_id"),
        "client_secret": s.get("einv_client_secret"),
        "api_key": s.get("einv_api_key"),
        "provider_url": s.get("einv_provider_url"),
        "branch_code": s.get("einv_branch_code"),
        "activity_code": s.get("einv_activity_code"),
        "ttn_cert_path": s.get("einv_ttn_cert_path"),
        "ttn_cert_password": s.get("einv_ttn_cert_password"),
        "zatca_csid": s.get("einv_zatca_csid"),
        "zatca_csid_secret": s.get("einv_zatca_csid_secret"),
        "zatca_pcsid": s.get("einv_zatca_pcsid"),
        "zatca_pcsid_secret": s.get("einv_zatca_pcsid_secret"),
    }


# ============================================================
# نموذج الفاتورة الموحدة
# ============================================================

def build_unified(invoice):
    company = None
    if invoice.financial_year and invoice.financial_year.company:
        company = invoice.financial_year.company
    customer = invoice.customer or invoice.supplier
    items = []
    for it in invoice.items:
        qty = float(it.quantity or 0)
        price = float(it.unit_price or 0)
        rate = float(it.tax_rate or 0)
        net = round(qty * price, 2)
        vat = round(net * rate / 100, 2)
        items.append({
            "description": it.description or "",
            "quantity": qty,
            "unit_price": price,
            "tax_rate": rate,
            "net_amount": net,
            "vat_amount": vat,
            "total": round(net + vat, 2),
        })
    total_net = round(sum(i["net_amount"] for i in items), 2)
    total_vat = round(sum(i["vat_amount"] for i in items), 2)
    return {
        "seller": {
            "name": (company.name if company else "") or "",
            "tax_number": (company.tax_number if company else "") or "",
            "commercial_registration": (company.commercial_registration if company else "") or "",
            "address": (getattr(company, "address", None) if company else None) or "",
            "country_code": country_of_config() or "EG",
        },
        "buyer": {
            "name": (customer.full_name if customer else "") or "",
            "type": (customer.type if customer else "individual") or "individual",
            "tax_number": (getattr(customer, "tax_number", None) if customer else "") or "",
            "phone": (customer.phone if customer else "") or "",
            "address": (customer.address if customer else "") or "",
            "ice": (getattr(customer, "ice", None) if customer else None) or "",
        },
        "document": {
            "number": invoice.invoice_number,
            "type": getattr(invoice, "invoice_type", "sales"),
            "issue_date": invoice.issue_date.isoformat() if invoice.issue_date
                          else datetime.now().date().isoformat(),
            "currency": (invoice._base_currency() or {}).get("code", "EGP"),
            "uuid": str(uuid.uuid4()),
        },
        "items": items,
        "totals": {
            "net_amount": total_net,
            "vat_amount": total_vat,
            "total_amount": round(total_net + total_vat, 2),
            "paid_amount": float(invoice.paid_amount or 0),
        },
    }


def country_of_config():
    return einvoice_config()["country"]


# ============================================================
# UBL 2.1 XML Builder
# ============================================================

def build_ubl_xml(unified, country_code=None):
    """يبني XML بصيغة UBL 2.1 متوافقة مع معظم المنظومات."""
    ns = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    cbc = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    cac = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"

    root = ET.Element("Invoice", xmlns=ns)
    ET.SubElement(root, f"{{{cbc}}}UBLVersionID").text = "2.1"
    ET.SubElement(root, f"{{{cbc}}}ID").text = unified["document"]["number"]
    ET.SubElement(root, f"{{{cbc}}}InvoiceTypeCode").text = "380"
    ET.SubElement(root, f"{{{cbc}}}IssueDate").text = unified["document"]["issue_date"]
    ET.SubElement(root, f"{{{cbc}}}DocumentCurrencyCode").text = unified["document"]["currency"]
    ET.SubElement(root, f"{{{cbc}}}UUID").text = unified["document"].get("uuid", str(uuid.uuid4()))

    supplier = ET.SubElement(root, f"{{{cac}}}AccountingSupplierParty")
    sp = ET.SubElement(supplier, f"{{{cac}}}Party")
    sid = ET.SubElement(sp, f"{{{cac}}}PartyIdentification")
    ET.SubElement(sid, f"{{{cbc}}}ID", schemeID="0088").text = unified["seller"]["tax_number"]
    sn = ET.SubElement(sp, f"{{{cac}}}PartyName")
    ET.SubElement(sn, f"{{{cbc}}}Name").text = unified["seller"]["name"]
    addr = ET.SubElement(sp, f"{{{cac}}}PostalAddress")
    ET.SubElement(addr, f"{{{cbc}}}StreetName").text = str(unified["seller"]["address"])
    ctry = ET.SubElement(addr, f"{{{cac}}}Country")
    ET.SubElement(ctry, f"{{{cbc}}}IdentificationCode").text = unified["seller"]["country_code"]
    tax = ET.SubElement(sp, f"{{{cac}}}PartyTaxScheme")
    ET.SubElement(tax, f"{{{cbc}}}CompanyID").text = unified["seller"]["tax_number"]
    ts = ET.SubElement(tax, f"{{{cac}}}TaxScheme")
    ET.SubElement(ts, f"{{{cbc}}}ID").text = "VAT"

    cp = ET.SubElement(root, f"{{{cac}}}AccountingCustomerParty")
    party = ET.SubElement(cp, f"{{{cac}}}Party")
    cid = ET.SubElement(party, f"{{{cac}}}PartyIdentification")
    ET.SubElement(cid, f"{{{cbc}}}ID", schemeID="0088").text = unified["buyer"]["tax_number"]
    cn = ET.SubElement(party, f"{{{cac}}}PartyName")
    ET.SubElement(cn, f"{{{cbc}}}Name").text = unified["buyer"]["name"]

    ET.SubElement(root, f"{{{cac}}}PaymentMeans").append(
        ET.Element(f"{{{cbc}}}PaymentMeansCode"))
    root.find(f"{{{cac}}}PaymentMeans/{{{cbc}}}PaymentMeansCode").text = "30"

    tt = ET.SubElement(root, f"{{{cac}}}TaxTotal")
    ET.SubElement(tt, f"{{{cbc}}}TaxAmount", currencyID=unified["document"]["currency"]).text = str(unified["totals"]["vat_amount"])

    lmt = ET.SubElement(root, f"{{{cac}}}LegalMonetaryTotal")
    ET.SubElement(lmt, f"{{{cbc}}}TaxExclusiveAmount", currencyID=unified["document"]["currency"]).text = str(unified["totals"]["net_amount"])
    ET.SubElement(lmt, f"{{{cbc}}}TaxInclusiveAmount", currencyID=unified["document"]["currency"]).text = str(unified["totals"]["total_amount"])
    ET.SubElement(lmt, f"{{{cbc}}}PayableAmount", currencyID=unified["document"]["currency"]).text = str(unified["totals"]["total_amount"])

    for idx, item in enumerate(unified["items"], 1):
        line = ET.SubElement(root, f"{{{cac}}}InvoiceLine")
        ET.SubElement(line, f"{{{cbc}}}ID").text = str(idx)
        ET.SubElement(line, f"{{{cbc}}}InvoicedQuantity", unitCode="EA").text = str(item["quantity"])
        ET.SubElement(line, f"{{{cbc}}}LineExtensionAmount", currencyID=unified["document"]["currency"]).text = str(item["net_amount"])
        item_el = ET.SubElement(line, f"{{{cac}}}Item")
        ET.SubElement(item_el, f"{{{cbc}}}Name").text = item["description"]
        classified = ET.SubElement(item_el, f"{{{cac}}}ClassifiedTaxCategory")
        ET.SubElement(classified, f"{{{cbc}}}ID").text = "S"
        ET.SubElement(classified, f"{{{cbc}}}Percent").text = str(item["tax_rate"])
        ts3 = ET.SubElement(classified, f"{{{cac}}}TaxScheme")
        ET.SubElement(ts3, f"{{{cbc}}}ID").text = "VAT"
        price = ET.SubElement(line, f"{{{cac}}}Price")
        ET.SubElement(price, f"{{{cbc}}}PriceAmount", currencyID=unified["document"]["currency"]).text = str(item["unit_price"])

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def build_ubl_hash(ubl_xml):
    """حساب SHA-256 hash للـ UBL XML (للتوثيق)."""
    return base64.b64encode(hashlib.sha256(ubl_xml.encode("utf-8")).digest()).decode()


# ============================================================
# QR (TLV/Base64)
# ============================================================

def build_qr_payload(unified, hash_b64=""):
    """TLV tags 1..5 كما في ZATCA و ETA."""
    seller = unified["seller"]["name"]
    vat_no = unified["seller"]["tax_number"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = f"{unified['totals']['total_amount']:.2f}"
    vat = f"{unified['totals']['vat_amount']:.2f}"

    def tlv(tag, value):
        val = value.encode("utf-8")
        return bytes([tag, len(val)]) + val

    payload = tlv(1, seller) + tlv(2, vat_no) + tlv(3, ts) + tlv(4, total) + tlv(5, vat)
    if hash_b64:
        payload += tlv(6, hash_b64)
    return base64.b64encode(payload).decode()


# ============================================================
# الموصّلات (Connectors)
# ============================================================

class ConnectorResult(dict):
    @property
    def ok(self):
        return self.get("status") in ("submitted", "accepted")


class BaseConnector:
    authority = "—"
    timeout = 30

    def __init__(self, cfg):
        self.cfg = cfg

    def _base_headers(self):
        return {"Content-Type": "application/json", "Accept": "application/json"}

    def submit(self, invoice, unified):
        raise NotImplementedError

    def check(self, invoice):
        raise NotImplementedError


# ============================================================
# 🇪🇬 مصر — ETA
# ============================================================

class EgyptETAConnector(BaseConnector):
    authority = "ETA"

    def _host(self):
        return ("https://preprod.invoicing.eta.gov.eg"
                if self.cfg["environment"] != "production"
                else "https://invoicing.eta.gov.eg")

    def _token(self):
        r = requests.post(
            f"{self._host()}/api/v1/auth/token",
            json={"client_id": self.cfg["client_id"],
                  "client_secret": self.cfg["client_secret"]},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("access_token")

    def submit(self, invoice, unified):
        try:
            token = self._token()
        except Exception as e:
            log_exc("einvoicing.eta-token", e)
            return ConnectorResult(status="error", message=f"ETA auth failed: {e}")

        doc_type = "I"
        if unified["document"].get("type") == "credit_note":
            doc_type = "C"
        elif unified["document"].get("type") == "debit_note":
            doc_type = "D"

        payload = {
            "issuer": {"type": "B", "id": unified["seller"]["tax_number"],
                       "name": unified["seller"]["name"]},
            "receiver": {
                "type": "P" if unified["buyer"]["type"] == "individual" else "B",
                "id": unified["buyer"]["tax_number"] or unified["buyer"].get("phone", ""),
                "name": unified["buyer"]["name"]},
            "documentType": doc_type,
            "documentTypeVersion": "1.0",
            "dateTimeIssued": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "taxpayerActivityCode": self.cfg.get("activity_code") or "0000",
            "invoiceLines": [{
                "description": it["description"][:100],
                "itemType": "GS1", "itemCode": "EG-0000", "unitType": "ONE",
                "quantity": it["quantity"], "salesTotal": it["net_amount"],
                "total": it["total"], "valueDifference": 0,
                "totalTaxableFees": 0, "netTotal": it["net_amount"], "itemsDiscount": 0,
                "unitValue": {"currencySold": unified["document"]["currency"],
                              "amountEGP": it["unit_price"]},
                "taxableItems": [{"taxType": "T1", "amount": it["vat_amount"],
                                  "subType": "V001", "rate": it["tax_rate"]}],
            } for it in unified["items"]],
            "taxTotals": [{"taxType": "T1", "amount": unified["totals"]["vat_amount"]}],
            "totalSales": unified["totals"]["net_amount"],
            "netTotal": unified["totals"]["net_amount"],
            "totalAmount": unified["totals"]["total_amount"],
        }
        try:
            r = requests.post(f"{self._host()}/api/v1/documents",
                              json={"document": payload, "signatures": []},
                              headers={**self._base_headers(),
                                       "Authorization": f"Bearer {token}"},
                              timeout=self.timeout)
            data = r.json() if r.content else {}
            if r.status_code in (200, 202):
                return ConnectorResult(status="submitted",
                                       reference=data.get("uuid") or data.get("submissionUUID"),
                                       raw=_json.dumps(data)[:2000])
            return ConnectorResult(status="rejected", message=str(data)[:500],
                                   raw=_json.dumps(data)[:2000])
        except Exception as e:
            log_exc("einvoicing.eta-submit", e)
            return ConnectorResult(status="error", message=str(e))

    def check(self, invoice):
        return ConnectorResult(status="unknown", message="Use ETA portal")


# ============================================================
# 🇸🇦 السعودية — ZATCA Fatoora
# ============================================================

class ZatcaConnector(BaseConnector):
    authority = "ZATCA"

    def _host(self):
        return ("https://gw-fatura.zatca.gov.sa/e-invoicing/developer-portal"
                if self.cfg["environment"] != "production"
                else "https://gw.fatoora.zatca.gov.sa/e-invoicing/core")

    def _auth_headers(self):
        csid = self.cfg.get("zatca_pcsid") or self.cfg.get("zatca_csid") or self.cfg.get("api_key") or ""
        secret = self.cfg.get("zatca_pcsid_secret") or self.cfg.get("zatca_csid_secret") or ""
        creds = base64.b64encode(f"{csid}:{secret}".encode()).decode()
        return {**self._base_headers(), "Authorization": f"Basic {creds}", "Accept-Version": "V2"}

    def submit(self, invoice, unified):
        qr = build_qr_payload(unified)
        if not self.cfg.get("zatca_pcsid") and not self.cfg.get("api_key"):
            return ConnectorResult(status="pending",
                                   message="ZATCA requires CSID. Set einv_api_key. QR generated.",
                                   qr=qr)

        host = self._host()
        mode = self.cfg.get("mode", "clearance")
        endpoint = f"{host}/invoices/reporting/single" if mode == "reporting" else f"{host}/invoices/clearance/single"

        payload = {
            "invoiceHash": build_ubl_hash(_json.dumps(unified)),
            "uuid": unified["document"].get("uuid", str(uuid.uuid4())),
            "invoice": unified,
        }
        headers = self._auth_headers()
        if mode == "clearance":
            headers["Clearance-Status"] = "1"

        try:
            r = requests.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
            data = r.json() if r.content else {}
            if r.status_code in (200, 202) and data.get("status") in ("CLEARED", "REPORTED", "accepted"):
                return ConnectorResult(status="accepted",
                                       reference=data.get("invoiceHash") or data.get("uuid"),
                                       qr=data.get("qr") or qr, raw=_json.dumps(data)[:2000])
            return ConnectorResult(status="rejected", message=str(data)[:500],
                                   raw=_json.dumps(data)[:2000])
        except Exception as e:
            log_exc("einvoicing.zatca-submit", e)
            return ConnectorResult(status="error", message=str(e))

    def onboarding_compliance(self, csr_pem, otp):
        host = self._host()
        try:
            r = requests.post(f"{host}/compliance",
                              json={"csr": base64.b64encode(csr_pem.encode()).decode()},
                              headers={**self._base_headers(), "OTP": otp}, timeout=self.timeout)
            data = r.json() if r.content else {}
            return ConnectorResult(status="accepted" if r.status_code in (200, 202) else "rejected",
                                   reference=data.get("requestID"), message=data.get("complianceCSID"),
                                   raw=_json.dumps(data)[:2000])
        except Exception as e:
            log_exc("einvoicing.zatca-compliance", e)
            return ConnectorResult(status="error", message=str(e))

    def onboarding_production(self, compliance_request_id, otp):
        host = self._host()
        try:
            r = requests.post(f"{host}/production/csids",
                              json={"complianceCSIDRequestId": compliance_request_id},
                              headers={**self._base_headers(), "OTP": otp}, timeout=self.timeout)
            data = r.json() if r.content else {}
            return ConnectorResult(status="accepted" if r.status_code in (200, 202) else "rejected",
                                   reference=data.get("productionCSID"),
                                   message=data.get("binarySecurityToken"),
                                   raw=_json.dumps(data)[:2000])
        except Exception as e:
            log_exc("einvoicing.zatca-production", e)
            return ConnectorResult(status="error", message=str(e))

    def check(self, invoice):
        return ConnectorResult(status="unknown", message="Check via Fatoora portal")


# ============================================================
# 🇹🇳 تونس — TTN / El Fatoora
# ============================================================

class TunisiaTTNConnector(BaseConnector):
    authority = "TTN"

    def _host(self):
        return ("https://api-sandbox.elfatoora.tn"
                if self.cfg["environment"] != "production"
                else "https://api.elfatoora.tn")

    def _token(self):
        r = requests.post(
            f"{self._host()}/api/v1/auth/token",
            data={"grant_type": "client_credentials",
                  "client_id": self.cfg["client_id"],
                  "client_secret": self.cfg["client_secret"],
                  "scope": "invoices:write invoices:read"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("access_token")

    def _sign_xml(self, xml_content):
        cert_path = self.cfg.get("ttn_cert_path")
        cert_pass = self.cfg.get("ttn_cert_password")
        if not cert_path:
            return xml_content
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.serialization import pkcs12, Encoding
            with open(cert_path, "rb") as f:
                p12_data = f.read()
            private_key, certificate, _chain = pkcs12.load_key_and_certificates(
                p12_data, cert_pass.encode() if cert_pass else None)
            sig = private_key.sign(hashlib.sha256(xml_content.encode()).digest(), hashes.SHA256())
            sig_b64 = base64.b64encode(sig).decode()
            cert_b64 = base64.b64encode(certificate.public_bytes(Encoding.DER)).decode()
            return xml_content.replace("</Invoice>",
                f"<Extension><Signature><SignatureValue>{sig_b64}</SignatureValue>"
                f"<KeyInfo><X509Data><X509Certificate>{cert_b64}</X509Certificate>"
                f"</X509Data></KeyInfo></Signature></Extension>\n</Invoice>")
        except Exception as e:
            log_exc("einvoicing.ttn-sign", e)
            return xml_content

    def submit(self, invoice, unified):
        xml = build_ubl_xml(unified)
        signed_xml = self._sign_xml(xml)
        try:
            token = self._token()
        except Exception as e:
            log_exc("einvoicing.ttn-token", e)
            return ConnectorResult(status="error", message=f"TTN auth failed: {e}")
        try:
            r = requests.post(f"{self._host()}/api/v1/invoices", data=signed_xml,
                              headers={"Authorization": f"Bearer {token}",
                                       "Content-Type": "application/xml",
                                       "Accept": "application/json"},
                              timeout=self.timeout)
            data = r.json() if r.content else {}
            if r.status_code in (200, 201, 202):
                return ConnectorResult(status="submitted",
                                       reference=data.get("invoiceId") or data.get("id"),
                                       message=data.get("status"), raw=_json.dumps(data)[:2000])
            return ConnectorResult(status="rejected", message=str(data.get("errors", data))[:500],
                                   raw=_json.dumps(data)[:2000])
        except Exception as e:
            log_exc("einvoicing.ttn-submit", e)
            return ConnectorResult(status="error", message=str(e))

    def check(self, invoice):
        try:
            token = self._token()
            ref = invoice.einv_reference
            if not ref:
                return ConnectorResult(status="unknown", message="No TTN reference")
            r = requests.get(f"{self._host()}/api/v1/invoices/{ref}",
                             headers={"Authorization": f"Bearer {token}"}, timeout=self.timeout)
            data = r.json() if r.content else {}
            status_map = {"VALID": "accepted", "INVALID": "rejected",
                          "SUBMITTED": "submitted", "CREATED": "pending"}
            return ConnectorResult(status=status_map.get(data.get("status"), "unknown"),
                                   reference=ref, raw=_json.dumps(data)[:2000])
        except Exception as e:
            log_exc("einvoicing.ttn-check", e)
            return ConnectorResult(status="error", message=str(e))


# ============================================================
# 🇲🇦 المغرب — DGI / Simpl-TVA
# ============================================================

class MoroccoDGIConnector(BaseConnector):
    authority = "DGI"

    def _host(self):
        return ("https://simpl-tva.tax.gov.ma/sandbox"
                if self.cfg["environment"] != "production"
                else "https://simpl-tva.tax.gov.ma/api")

    def _auth_headers(self):
        return {**self._base_headers(), "Authorization": f"Bearer {self.cfg.get('api_key') or ''}"}

    def submit(self, invoice, unified):
        xml = build_ubl_xml(unified)
        try:
            r = requests.post(f"{self._host()}/invoices/clearance",
                              json={"invoice": unified, "xml": xml},
                              headers=self._auth_headers(), timeout=self.timeout)
            data = r.json() if r.content else {}
            if r.status_code in (200, 201, 202):
                return ConnectorResult(status="accepted",
                                       reference=data.get("validationId") or data.get("id"),
                                       raw=_json.dumps(data)[:2000])
            return ConnectorResult(status="rejected", message=str(data)[:500],
                                   raw=_json.dumps(data)[:2000])
        except Exception as e:
            log_exc("einvoicing.dgi-ma-submit", e)
            return ConnectorResult(status="error", message=str(e))

    def check(self, invoice):
        return ConnectorResult(status="unknown", message="Check via Simpl-TVA")


# ============================================================
# موصّل م统一 عبر مزود (AE/OM/JO/BH)
# ============================================================

class GenericProviderConnector(BaseConnector):
    def __init__(self, cfg, authority):
        super().__init__(cfg)
        self.authority = authority

    def submit(self, invoice, unified):
        url = self.cfg.get("provider_url")
        if not url:
            return ConnectorResult(status="pending",
                                   message=f"{self.authority}: Set einv_provider_url. UBL generated.")
        try:
            r = requests.post(url, json={"authority": self.authority, "invoice": unified},
                              headers=self._base_headers(), timeout=self.timeout)
            data = r.json() if r.content else {}
            if r.status_code in (200, 202):
                return ConnectorResult(status="submitted",
                                       reference=data.get("id") or data.get("uuid"),
                                       raw=_json.dumps(data)[:2000])
            return ConnectorResult(status="rejected", message=str(data)[:500])
        except Exception as e:
            log_exc(f"einvoicing.{self.authority.lower()}-submit", e)
            return ConnectorResult(status="error", message=str(e))

    def check(self, invoice):
        return ConnectorResult(status="unknown", message="Check via provider")


# ============================================================
# 🇩🇿 الجزائر — DGI CTC
# ============================================================

class AlgeriaDGIConnector(BaseConnector):
    authority = "DGI-DZ"

    def _host(self):
        return "https://api-facture.dgi.gov.dz"

    def _token(self):
        try:
            r = requests.post(f"{self._host()}/auth/token",
                              json={"client_id": self.cfg["client_id"],
                                    "client_secret": self.cfg["client_secret"]},
                              headers={"Content-Type": "application/json"}, timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("access_token")
        except Exception as e:
            log_exc("einvoicing.dz-token", e)
            return None

    def submit(self, invoice, unified):
        token = self._token()
        if not token:
            return ConnectorResult(status="error", message="DZ auth failed")
        try:
            ubl_xml = build_ubl_xml(unified)
            r = requests.post(f"{self._host()}/invoices/clearance",
                              json={"invoiceXml": base64.b64encode(ubl_xml.encode()).decode(),
                                    "invoiceHash": build_ubl_hash(ubl_xml),
                                    "uuid": unified["document"].get("uuid", str(uuid.uuid4()))},
                              headers={**self._base_headers(), "Authorization": f"Bearer {token}"},
                              timeout=self.timeout)
            data = r.json() if r.content else {}
            if r.status_code in (200, 201, 202):
                return ConnectorResult(status="accepted",
                                       reference=data.get("irn") or data.get("id"),
                                       raw=_json.dumps(data)[:2000])
            return ConnectorResult(status="rejected", message=str(data)[:500],
                                   raw=_json.dumps(data)[:2000])
        except Exception as e:
            log_exc("einvoicing.dz-submit", e)
            return ConnectorResult(status="error", message=str(e))

    def check(self, invoice):
        return ConnectorResult(status="unknown", message="DGI DZ pending 2027")


# ============================================================
# 🇶🇦 قطر — GTA
# ============================================================

class QatarGTAConnector(BaseConnector):
    authority = "GTA"

    def submit(self, invoice, unified):
        return ConnectorResult(status="pending",
                               message="Qatar: E-invoice law approved May 2026. UBL generated.")

    def check(self, invoice):
        return ConnectorResult(status="unknown", message="GTA pending")


# ============================================================
# 🇧🇭 البحرين — NBR Phase 2
# ============================================================

class BahrainNBRConnector(GenericProviderConnector):
    def __init__(self, cfg):
        super().__init__(cfg, "NBR")


# ============================================================
# 🇦🇪 الإمارات — FTA Peppol
# ============================================================

class UAEFTAConnector(GenericProviderConnector):
    def __init__(self, cfg):
        super().__init__(cfg, "FTA")


# ============================================================
# 🇴🇲 عُمان — OTA Fawtara
# ============================================================

class OmanOTAConnector(GenericProviderConnector):
    def __init__(self, cfg):
        super().__init__(cfg, "OTA")


# ============================================================
# 🇯🇴 الأردن — JOFOTARA
# ============================================================

class JordanJOFOTARAConnector(GenericProviderConnector):
    def __init__(self, cfg):
        super().__init__(cfg, "JOFOTARA")


# ============================================================
# موصل offline — للدول بدون أنظمة
# ============================================================

class OfflineUBLConnector(BaseConnector):
    def __init__(self, cfg, authority="—", country_name=""):
        super().__init__(cfg)
        self.authority = authority
        self._country_name = country_name

    def submit(self, invoice, unified):
        xml = build_ubl_xml(unified)
        return ConnectorResult(status="pending",
                               message=f"{self._country_name}: No active system. UBL XML generated.",
                               xml_preview=xml[:500])

    def check(self, invoice):
        return ConnectorResult(status="unknown", message=f"{self._country_name}: offline")


# ============================================================
# Factory
# ============================================================

def get_connector(cfg=None):
    cfg = cfg or einvoice_config()
    country = cfg["country"]
    if country == "EG":
        return EgyptETAConnector(cfg)
    if country == "SA":
        return ZatcaConnector(cfg)
    if country == "TN":
        return TunisiaTTNConnector(cfg)
    if country == "MA":
        return MoroccoDGIConnector(cfg)
    if country == "AE":
        return UAEFTAConnector(cfg)
    if country == "OM":
        return OmanOTAConnector(cfg)
    if country == "JO":
        return JordanJOFOTARAConnector(cfg)
    if country == "BH":
        return BahrainNBRConnector(cfg)
    if country == "DZ":
        return AlgeriaDGIConnector(cfg)
    if country == "QA":
        return QatarGTAConnector(cfg)
    info = COUNTRIES.get(country, {})
    return OfflineUBLConnector(cfg, info.get("authority", "—"), info.get("name", country))
