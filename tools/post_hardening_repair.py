#!/usr/bin/env python3
"""Repair deterministic issues exposed by production hardening CI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
text = APP.read_text(encoding="utf-8")
original = text

# The initial hardening inserted an early health endpoint, while app.py already
# had a database-aware /health endpoint later in create_app. Remove the early
# duplicate block and add only a /ready endpoint beside the existing health rule.
early = '''    db.init_app(app)\n    @app.get("/health")\n    def health_check():\n        return {"status": "ok", "service": "dynamicpro", "version": os.environ.get("DYNAMICPRO_VERSION", "dev")}, 200\n\n    @app.get("/ready")\n    def readiness_check():\n        try:\n            from sqlalchemy import text\n            db.session.execute(text("SELECT 1"))\n            return {"status": "ready", "service": "dynamicpro"}, 200\n        except Exception:\n            return {"status": "not_ready", "service": "dynamicpro"}, 503\n\n\n    # CORS\n'''
expected = '''    db.init_app(app)\n\n    # CORS\n'''
if early in text:
    text = text.replace(early, expected, 1)

health = '''    @app.route("/health")\n    def health():\n        """Health check endpoint for Docker / Nginx."""\n        from sqlalchemy import text\n        try:\n            db.session.execute(text("SELECT 1"))\n            db_ok = True\n        except Exception:\n            db_ok = False\n        return jsonify({\n            "status": "healthy" if db_ok else "degraded",\n            "database": "connected" if db_ok else "disconnected",\n        }), 200 if db_ok else 503\n'''
if health not in text:
    raise SystemExit("existing /health endpoint not found")
if '    @app.route("/ready")\n    def readiness():' not in text:
    ready = health + '''\n    @app.route("/ready")\n    def readiness():\n        """Readiness probe: dependency check used by load balancers."""\n        try:\n            from sqlalchemy import text\n            db.session.execute(text("SELECT 1"))\n            return jsonify({"status": "ready", "database": "connected"}), 200\n        except Exception:\n            return jsonify({"status": "not_ready", "database": "disconnected"}), 503\n'''
    text = text.replace(health, ready, 1)

old_license = '''            except Exception:\n                pass\n            return\n'''
new_license = '''            except Exception as exc:\n                from utils.errlog import log_exc\n                log_exc("app.enforce-company-license")\n                if _is_api_path():\n                    return jsonify({"success": False, "message": "Subscription validation unavailable"}), 503\n                return redirect(url_for("auth.login"))\n            return\n'''
if old_license not in text:
    raise SystemExit("company license exception block not found")
text = text.replace(old_license, new_license, 1)

old_global = '''        except Exception:\n            from utils.errlog import log_exc\n            log_exc("app.enforce-license")\n\n    @app.before_request\n'''
new_global = '''        except Exception as exc:\n            from utils.errlog import log_exc\n            log_exc("app.enforce-license")\n            if _is_api_path():\n                return jsonify({"success": False, "message": "License validation unavailable"}), 503\n            return redirect(url_for("auth.login"))\n\n    @app.before_request\n'''
if old_global not in text:
    raise SystemExit("global license exception block not found")
text = text.replace(old_global, new_global, 1)

if text == original:
    raise SystemExit("no repair changes were applied")
APP.write_text(text, encoding="utf-8")
print("post-hardening app repair applied")
