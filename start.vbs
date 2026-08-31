Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d D:\EOS\DynamicPro-ERP\DynamicPro-ERP && set DYNAMICPRO_MODE=production && set PYTHONIOENCODING=utf-8 && python app.py", 0, False
