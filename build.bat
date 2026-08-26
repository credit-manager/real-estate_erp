@echo off
chcp 65001 >nul
title Dynamic Pro - Build Desktop Apps
echo ============================================
echo   Dynamic Pro ERP - Build Desktop Apps
echo ============================================
echo.
echo [1/3] Installing build tools...
pip install pywebview pyinstaller

echo [2/3] Building Server app (DynamicPro.exe)...
pyinstaller --noconsole --onefile --icon "app.ico" --name "DynamicPro" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --hidden-import webview.platforms.edgechromium ^
  --hidden-import webview.platforms.winforms ^
  desktop.py

echo [3/3] Building Client app (DynamicPro-Client.exe)...
pyinstaller --noconsole --onefile --icon "app.ico" --name "DynamicPro-Client" ^
  --hidden-import webview.platforms.edgechromium ^
  --hidden-import webview.platforms.winforms ^
  desktop_client.py

echo.
echo ============================================
echo   Done!
echo   dist\DynamicPro.exe          - Server PC
echo   dist\DynamicPro-Client.exe   - Other PCs
echo ============================================
pause
