# delete the file called Client.exe on the desktop and rename the file called TempClient.exe to Client.exe

Start-Sleep -s 2
Remove-Item -Path C:\Users\max\Desktop\client.exe
Rename-Item -Path C:\Users\max\Desktop\TempClient.exe -NewName client.exe
# launch the file called Client.exe on the desktop
Start-Process -FilePath C:\Users\max\Desktop\client.exe