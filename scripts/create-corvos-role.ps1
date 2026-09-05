# Elevates create-corvos-role.cmd via UAC (same pattern as start-pg.ps1).
$ErrorActionPreference = 'Stop'
$p = Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/c', 'e:\corvos\scripts\create-corvos-role.cmd' `
    -Verb RunAs -Wait -PassThru
Write-Host "elevated exit=$($p.ExitCode)"
