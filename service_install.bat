@echo off
:: Chemin Python
set PYTHON=C:\Users\Zique\AppData\Local\Python\pythoncore-3.14-64\python.exe
:: Creer le service avec chemin complet
schtasks /create /tn "RcloneGUIServer" /tr "\"%PYTHON%\" \"%~dp0app.py\"" /sc onlogon /ru SYSTEM /f
echo Service installe! Redemarrez pour appliquer.
pause