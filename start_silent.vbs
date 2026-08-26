Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\EOS\DynamicPro-ERP\DynamicPro-ERP"
WshShell.Run "cmd /c set PYTHONIOENCODING=utf-8 && python app.py", 0, False
