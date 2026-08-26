@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
REM كلمة المرور تُقرأ من البيئة أو .db_password — لا تضع قيمة افتراضية
if "%DB_PASSWORD%"=="" echo [start_bg.bat] تحذير: DB_PASSWORD غير مضبوطة — سيُستخدم .db_password
set DYNAMICPRO_MODE=production
python app.py
