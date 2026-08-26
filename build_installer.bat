@echo off
chcp 65001 >nul
title Dynamic Pro - Build Installer
echo ============================================
echo   Dynamic Pro ERP - Build Installer
echo ============================================
echo.
echo Building setup (DynamicPro-Setup.exe)...
pyinstaller --noconsole --onefile --icon "app.ico" --name "DynamicPro-Setup" ^
  --add-data "app.ico;." ^
  --distpath dist ^
  --workpath "build\installer_work" ^
  installer.py

echo.
echo ============================================
echo   Done!
echo   dist\DynamicPro-Setup.exe
echo   (must stay next to DynamicPro.exe and DynamicPro-Client.exe)
echo ============================================
pause
