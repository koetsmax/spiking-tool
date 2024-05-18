Start-Sleep -s 2
Remove-Item -Path C:\Users\sot\Desktop\client.exe
Start-Sleep -s 2
Rename-Item -Path C:\Users\sot\Desktop\TempClient.exe -NewName client.exe
# launch the file called Client.exe on the desktop
Start-Process -FilePath C:\Users\sot\Desktop\client.exe