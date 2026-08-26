@echo off
chcp 65001 >nul
title Dynamic Pro ERP
echo ============================================
echo   Dynamic Pro ERP - نظام الإدارة المتكامل
echo ============================================
echo.
echo [1/3] جاري فحص الحزم...
pip install -r requirements.txt >nul 2>&1
echo [2/3] جاري تشغيل الخادم...
echo.
echo النظام متاح الآن على:
echo   هذا الجهاز:    http://localhost:5000
echo   الشبكة:        http://[عنوان الجهاز]:5000
echo.
echo لتسجيل الدخول: admin / admin123
echo.
echo اضغط Ctrl+C لإيقاف الخادم
echo ============================================
echo.
python app.py
pause
