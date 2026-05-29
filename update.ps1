param (
    [string]$old_executable_path,
    [int]$process_id
)

Write-Output "Updating Spiking Tool client..."

$ErrorActionPreference = "Stop"

try {
    Start-Sleep -Seconds 2

    $process = Get-Process -Id $process_id -ErrorAction SilentlyContinue
    if ($null -ne $process) {
        Stop-Process -Id $process_id -Force
        Start-Sleep -Seconds 1
    }

    $updated_executable_path = "$env:LOCALAPPDATA\SpikingTool\updater\client.exe"

    if (-not (Test-Path $updated_executable_path)) {
        throw "Downloaded update not found at $updated_executable_path"
    }

    $backupPath = "$old_executable_path.old"
    if (Test-Path $backupPath) {
        Remove-Item -Path $backupPath -Force
    }
    Rename-Item -Path $old_executable_path -NewName (Split-Path -Leaf $backupPath)
    Move-Item -Path $updated_executable_path -Destination $old_executable_path
    Remove-Item -Path $backupPath -ErrorAction SilentlyContinue

    Start-Process -FilePath $old_executable_path

    Write-Output "Update completed successfully."
}
catch {
    Write-Host "An error occurred during update:" -ForegroundColor Red
    $_ | Format-List * -Force
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}
