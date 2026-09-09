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
                from utils.errlog import log_exc
                log_exc("app.enforce-company-license")
                if _is_api_path():
                    return jsonify({"success": False, "message": "Subscription validation unavailable"}), 503
                return redirect(url_for("auth.login"))
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
            if _is_api_path():
                return jsonify({"success": False, "message": "License validation unavailable"}), 503
            return redirect(url_for("auth.login"))
