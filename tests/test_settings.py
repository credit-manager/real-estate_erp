"""Tests for General Settings endpoints."""
import pytest


class TestSettingsGet:
    def test_get_settings(self, auth_client):
        resp = auth_client.get("/general-settings/api")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "settings" in data
        assert "options" in data

    def test_settings_has_all_defaults(self, auth_client):
        data = auth_client.get("/general-settings/api").get_json()["settings"]
        for key in ("system_name", "default_lang", "default_theme",
                     "invoice_prefix", "renewal_prefix", "payment_prefix",
                     "realestate_max_discount_percent", "realestate_vat_percent",
                     "rental_escalation_percent", "sales_commission_rate"):
            assert key in data

    def test_options_contain_companies(self, auth_client):
        resp = auth_client.get("/general-settings/api").get_json()
        assert "companies" in resp["options"]
        assert "currencies" in resp["options"]
        assert "financial_years" in resp["options"]
        assert "tax_types" in resp["options"]

    def test_secrets_masked(self, auth_client):
        data = auth_client.get("/general-settings/api").get_json()["settings"]
        assert "einv_client_secret_set" in data
        assert "einv_api_key_set" in data
        assert "fcm_server_key_set" in data
        assert "backup_encryption_password_set" in data


class TestSectionSave:
    @pytest.mark.parametrize("section", [
        "profile", "appearance", "documents", "defaults",
        "realestate", "rentals", "sales", "einvoice",
        "backup", "mobile",
    ])
    def test_save_section_valid(self, auth_client, section):
        resp = auth_client.post(f"/general-settings/api/{section}", json={})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_save_invalid_section(self, auth_client):
        resp = auth_client.post("/general-settings/api/invalid", json={})
        assert resp.status_code == 400

    def test_save_appearance_section(self, auth_client):
        resp = auth_client.post("/general-settings/api/appearance", json={
            "default_theme": "dark",
            "default_lang": "en",
            "number_decimals": "3",
            "date_format": "yyyy-mm-dd",
        })
        assert resp.status_code == 200
        data = auth_client.get("/general-settings/api").get_json()["settings"]
        assert data["default_theme"] == "dark"
        assert data["default_lang"] == "en"

    def test_save_documents_section(self, auth_client):
        resp = auth_client.post("/general-settings/api/documents", json={
            "invoice_prefix": "FAT-",
            "doc_default_tax_rate": "15",
        })
        assert resp.status_code == 200

    def test_save_realestate_section(self, auth_client):
        resp = auth_client.post("/general-settings/api/realestate", json={
            "realestate_max_discount_percent": "20",
            "realestate_vat_percent": "15",
            "realestate_contract_approval": "1",
        })
        assert resp.status_code == 200

    def test_save_rentals_section(self, auth_client):
        resp = auth_client.post("/general-settings/api/rentals", json={
            "rental_escalation_enabled": "1",
            "rental_escalation_percent": "7",
        })
        assert resp.status_code == 200

    def test_save_sales_section(self, auth_client):
        resp = auth_client.post("/general-settings/api/sales", json={
            "sales_commission_rate": "5",
        })
        assert resp.status_code == 200

    def test_save_backup_section(self, auth_client):
        resp = auth_client.post("/general-settings/api/backup", json={
            "backup_auto_enabled": "1",
            "backup_auto_interval_days": "7",
            "backup_auto_keep": "5",
        })
        assert resp.status_code == 200

    def test_save_mobile_section(self, auth_client):
        resp = auth_client.post("/general-settings/api/mobile", json={
            "mobile_work_lat": "24.7136",
            "mobile_work_lng": "46.6753",
            "mobile_attendance_radius_meters": "500",
            "mobile_gps_interval_seconds": "60",
        })
        assert resp.status_code == 200


class TestValidation:
    def test_invalid_number_decimals(self, auth_client):
        resp = auth_client.post("/general-settings/api/appearance", json={
            "number_decimals": "5",
        })
        assert resp.status_code == 400

    def test_invalid_theme(self, auth_client):
        resp = auth_client.post("/general-settings/api/appearance", json={
            "default_theme": "neon",
        })
        assert resp.status_code == 400

    def test_invalid_lang(self, auth_client):
        resp = auth_client.post("/general-settings/api/appearance", json={
            "default_lang": "fr",
        })
        assert resp.status_code == 400

    def test_invalid_date_format(self, auth_client):
        resp = auth_client.post("/general-settings/api/appearance", json={
            "date_format": "dd-mm-yyyy",
        })
        assert resp.status_code == 400

    def test_invalid_einv_country(self, auth_client):
        resp = auth_client.post("/general-settings/api/einvoice", json={
            "einv_country": "XX",
        })
        assert resp.status_code == 400

    def test_invalid_einv_mode(self, auth_client):
        resp = auth_client.post("/general-settings/api/einvoice", json={
            "einv_mode": "invalid_mode",
        })
        assert resp.status_code == 400

    def test_invalid_einv_environment(self, auth_client):
        resp = auth_client.post("/general-settings/api/einvoice", json={
            "einv_environment": "staging",
        })
        assert resp.status_code == 400

    def test_invalid_realestate_discount(self, auth_client):
        resp = auth_client.post("/general-settings/api/realestate", json={
            "realestate_max_discount_percent": "150",
        })
        assert resp.status_code == 400

    def test_invalid_rental_escalation(self, auth_client):
        resp = auth_client.post("/general-settings/api/rentals", json={
            "rental_escalation_percent": "200",
        })
        assert resp.status_code == 400

    def test_invalid_sales_commission(self, auth_client):
        resp = auth_client.post("/general-settings/api/sales", json={
            "sales_commission_rate": "150",
        })
        assert resp.status_code == 400


class TestCompanySave:
    def test_save_company(self, auth_client):
        settings_data = auth_client.get("/general-settings/api").get_json()
        companies = settings_data["options"]["companies"]
        if not companies:
            pytest.skip("No companies in test DB")
        cid = companies[0]["id"]
        resp = auth_client.post("/general-settings/api/company", json={
            "id": cid,
            "name": "شركة اختبار",
            "phone": "0501234567",
        })
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_save_company_missing_id(self, auth_client):
        resp = auth_client.post("/general-settings/api/company", json={
            "name": "test",
        })
        assert resp.status_code == 400

    def test_save_company_missing_name(self, auth_client):
        settings_data = auth_client.get("/general-settings/api").get_json()
        companies = settings_data["options"]["companies"]
        if not companies:
            pytest.skip("No companies in test DB")
        resp = auth_client.post("/general-settings/api/company", json={
            "id": companies[0]["id"],
            "name": "",
        })
        assert resp.status_code == 400

    def test_save_company_not_found(self, auth_client):
        resp = auth_client.post("/general-settings/api/company", json={
            "id": 999999,
            "name": "test",
        })
        assert resp.status_code == 404

    def test_save_company_invalid_id(self, auth_client):
        resp = auth_client.post("/general-settings/api/company", json={
            "id": "abc",
            "name": "test",
        })
        assert resp.status_code == 400


class TestLayoutSave:
    def test_save_layout(self, auth_client):
        resp = auth_client.post("/general-settings/api/layout", json={
            "layout_style": "horizontal",
            "sidebar_width": "280",
            "compact_menu": True,
            "grouped_modules": False,
        })
        assert resp.status_code == 200
        data = auth_client.get("/general-settings/api").get_json()["settings"]
        assert data.get("layout_style") == "horizontal"

    def test_save_layout_invalid_style(self, auth_client):
        resp = auth_client.post("/general-settings/api/layout", json={
            "layout_style": "diagonal",
        })
        assert resp.status_code == 200  # falls back to vertical


class TestNextNumber:
    def test_next_invoice_number(self, auth_client):
        resp = auth_client.get("/general-settings/api/next-number?type=invoice")
        assert resp.status_code == 200
        num = resp.get_json()["number"]
        assert "-" in num  # has a prefix separator

    def test_next_po_number(self, auth_client):
        resp = auth_client.get("/general-settings/api/next-number?type=po")
        assert resp.status_code == 200
        assert resp.get_json()["number"].startswith("PO-")

    def test_next_contract_number(self, auth_client):
        resp = auth_client.get("/general-settings/api/next-number?type=contract")
        assert resp.status_code == 200
        assert resp.get_json()["number"].startswith("RC-")

    def test_invalid_type(self, auth_client):
        resp = auth_client.get("/general-settings/api/next-number?type=invalid")
        assert resp.status_code == 400


class TestCache:
    def test_cache_invalidation_on_save(self, auth_client):
        auth_client.post("/general-settings/api/profile", json={
            "system_name": "Test Cache System",
        })
        data = auth_client.get("/general-settings/api").get_json()["settings"]
        assert data["system_name"] == "Test Cache System"
