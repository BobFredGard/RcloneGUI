@echo off
:: Desinstaller le service Windows
schtasks /delete /tn "RcloneGUIServer" /f
echo Service desinstalle!
pause