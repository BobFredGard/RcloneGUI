# Portable : utilise le dossier du script, détecte python dans le PATH
$ProjectDir = $PSScriptRoot
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $Python) { Write-Error "Python introuvable dans le PATH"; exit 1 }
$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$ProjectDir\app.py`"" -WorkingDirectory $ProjectDir
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName 'RcloneGUI' -Action $action -Trigger $trigger -RunLevel Highest -Force
Write-Host "Tache creee!"