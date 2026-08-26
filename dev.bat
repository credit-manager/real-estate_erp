@echo off
chcp 65001 >nul
title Dynamic Pro ERP - Dev Server (Auto Reload)
echo ============================================
echo   Dynamic Pro ERP - خادم التطوير
echo   أي تعديل في الكود أو القوالب يظهر فوراً
echo   افتح: http://localhost:5000
echo ============================================
echo.
start "" "http://localhost:5000"
python app.py
pause
