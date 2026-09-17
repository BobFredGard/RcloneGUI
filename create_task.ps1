$action = New-ScheduledTaskAction -Execute 'C:\Users\Zique\AppData\Local\Python\pythoncore-3.14-64\python.exe' -Argument 'D:\ServerFolders\RcloneGUI\app.py' -WorkingDirectory 'D:\ServerFolders\RcloneGUI'
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName 'RcloneGUI' -Action $action -Trigger $trigger -RunLevel Highest -Force
Write-Host "Tache creee!"