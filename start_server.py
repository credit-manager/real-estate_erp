import os, sys, traceback

# كلمة المرور تُقرأ من البيئة أو .db_password عبر config.py — لا تضع قيمة افتراضية هنا
os.environ['PYTHONIOENCODING'] = 'utf-8'

log = open(os.path.join(os.path.dirname(__file__), 'server.log'), 'w', encoding='utf-8')
sys.stdout = log
sys.stderr = log

try:
    from app import create_app
    app = create_app()
    log.flush()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
except Exception:
    traceback.print_exc()
    log.flush()
