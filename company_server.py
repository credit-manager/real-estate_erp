# -*- coding: utf-8 -*-
"""
company_server.py — تشغيل نسخة مستقلة لكل شركة

Usage:
    python company_server.py --company 1 --port 2222
    python company_server.py --company 2 --port 3333

Or via environment variables:
    set COMPANY_ID=1
    set COMPANY_PORT=2222
    python company_server.py
"""
import os
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="Run DynamicPro ERP for a specific company")
    parser.add_argument("--company", "-c", type=int, required=False,
                        help="Company ID from lic_companies table")
    parser.add_argument("--port", "-p", type=int, required=False,
                        help="Port to run on (e.g. 2222, 3333)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode")
    args = parser.parse_args()

    if args.company:
        os.environ["COMPANY_ID"] = str(args.company)
    if args.port:
        os.environ["COMPANY_PORT"] = str(args.port)

    company_id = os.environ.get("COMPANY_ID", "")
    port = int(os.environ.get("COMPANY_PORT", "5000"))

    print(f"=" * 60)
    print(f"  DynamicPro ERP — Company Server")
    print(f"=" * 60)
    print(f"  Company ID : {company_id or '(default/employee mode)'}")
    print(f"  Port       : {port}")
    print(f"  Host       : {args.host}")
    print(f"  Debug      : {args.debug}")
    print(f"=" * 60)

    from app import create_app
    app = create_app()

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
        sys.exit(0)
    try:
        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)
    except (OSError, AttributeError):
        pass

    app.run(host=args.host, port=port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
