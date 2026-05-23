# One-time fix for Windows Defender / SmartScreen false positives on this project.
# Right-click PowerShell -> Run as administrator, then:
#   Set-ExecutionPolicy -Scope Process Bypass; & ".\defender_exclusions.ps1"

#Requires -RunAsAdministrator

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$paths = @(
    $root
    "C:\Python313"
    "$env:LOCALAPPDATA\Programs\Python\Python312"
)

foreach ($path in $paths) {
    if (-not (Test-Path $path)) {
        Write-Host "Skip (not found): $path"
        continue
    }
    try {
        Add-MpPreference -ExclusionPath $path -ErrorAction Stop
        Write-Host "Added exclusion: $path"
    }
    catch {
        if ($_.Exception.Message -match "already exists") {
            Write-Host "Already excluded: $path"
        }
        else {
            Write-Warning "Failed for ${path}: $($_.Exception.Message)"
        }
    }
}

Write-Host ""
Write-Host "Done. Double-click run_client_admin.bat or run py client.py from an admin shell."
