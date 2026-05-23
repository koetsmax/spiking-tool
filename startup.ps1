# This script will launch both the server and controller

# Launch the server
Start-Process -FilePath "python" -ArgumentList "server.py" -WorkingDirectory $PSScriptRoot -NoNewWindow

# Launch the controller
Start-Process -FilePath "python" -ArgumentList "controller.py" -WorkingDirectory $PSScriptRoot -NoNewWindow