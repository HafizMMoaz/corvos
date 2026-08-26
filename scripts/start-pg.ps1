# Elevates start-pg.cmd (UAC prompt) to start the stopped Postgres 18 service.
# ponytail: same pattern as run-elevated.ps1 -- kept in a file because inline
# -Command loses `$` sigils in this shell.
$ErrorActionPreference = 'Stop'
$p = Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/c', 'd:\Corvos\scripts\start-pg.cmd' `
    -Verb RunAs -Wait -PassThru
Add-Content -Path 'd:\Corvos\scripts\pg_start.txt' `
    -Value "elevated exit=$($p.ExitCode)" -Encoding UTF8
