import os, sys
# لا تضع كلمة مرور افتراضية في الكود — تُقرأ من البيئة أو .db_password عبر config.py
# للتشغيل المحلي فقط: إن لم تكن DB_PASSWORD مضبوطة سيُستخدم .db_password تلقائياً
if not os.environ.get("DB_PASSWORD"):
    _pw_file = os.path.join(os.path.dirname(__file__), ".db_password")
    if not os.path.isfile(_pw_file):
        print("[start.py] تحذير: DB_PASSWORD غير مضبوطة ولا يوجد .db_password — سيتم توليد واحدة تلقائياً.")
os.environ['PYTHONIOENCODING'] = 'utf-8'
from app import create_app
app = create_app()
app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
