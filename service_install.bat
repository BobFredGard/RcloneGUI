@echo off
:: Portable : utilise python du PATH, chemin relatif au script
where python >nul 2>nul
if errorlevel 1 (
  echo Python introuvable dans le PATH. Installez Python puis reessayez.
  pause
  exit /b 1
)
:: Creer le service avec chemin relatif au script
schtasks /create /tn "RcloneGUIServer" /tr "\"python\" \"%~dp0app.py\"" /sc onlogon /ru SYSTEM /f
echo Service installe! Redemarrez pour appliquer.
pause