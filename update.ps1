param(
    [Parameter(Mandatory = $true)]
    [string]$CurrentExe,
    [Parameter(Mandatory = $true)]
    [string]$NewExe,
    [Parameter(Mandatory = $true)]
    [int]$PidToWait
)

$ErrorActionPreference = "Stop"

for ($i = 0; $i -lt 120; $i++) {
    if (-not (Get-Process -Id $PidToWait -ErrorAction SilentlyContinue)) {
        break
    }
    Start-Sleep -Milliseconds 500
}
Start-Sleep -Seconds 1

if (Test-Path $CurrentExe) {
    Remove-Item -Path $CurrentExe -Force
}
Move-Item -Path $NewExe -Destination $CurrentExe -Force
Start-Process -FilePath $CurrentExe
