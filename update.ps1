# delete the file called Client.exe on the desktop and rename the file called TempClient.exe to Client.exe

Start-Sleep -s 2
Remove-Item -Path C:\Users\Public\Desktop\Client.exe
Rename-Item -Path C:\Users\Public\Desktop\TempClient.exe -NewName Client.exe