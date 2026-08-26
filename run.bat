@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
REM لا تضع كلمة مرور افتراضية هنا — تُقرأ من البيئة أو .db_password
REM إن كانت DB_PASSWORD غير مضبوطة، سيتولى config.py قراءتها من .db_password
if "%DB_PASSWORD%"=="" echo [run.bat] تحذير: DB_PASSWORD غير مضبوطة — سيُستخدم .db_password
set DYNAMICPRO_MODE=production

:restart
echo [%date% %time%] Starting DynamicPro-ERP...
python app.py
echo [%date% %time%] Server stopped. Restarting in 3 seconds...
timeout /t 3 /nobreak >nul
goto restart
