$action = New-ScheduledTaskAction -Execute 'C:\Users\Zique\AppData\Local\Python\pythoncore-3.14-64\python.exe' -Argument '"D:\ServerFolders\Rclone GUI\app.py"' -WorkingDirectory 'D:\ServerFolders\Rclone GUI'
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Unregister-ScheduledTask -TaskName 'RcloneGUI' -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName 'RcloneGUI' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Write-Host "Tache creee!"