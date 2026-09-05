# Restarts only the Next.js dev server. It caches the parse failure from the
# BOM'd package.json, so it needs a fresh process (not just a page reload).
# ponytail: matches the dev-server process by its command line rather than
# killing every node.exe, so zero-cache's worker pool survives.
$ErrorActionPreference = 'Continue'
$report = 'e:\corvos\scripts\web_restart.txt'
$lines = @()

$procs = Get-CimInstance Win32_Process -Filter "Name='node.exe' or Name='cmd.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match 'next' -and $_.CommandLine -notmatch 'zero-cache' }

foreach ($p in $procs) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        $lines += "killed pid=$($p.ProcessId) $($p.Name)"
    }
    catch {
        $lines += "kill failed pid=$($p.ProcessId): $($_.Exception.Message)"
    }
}
if (-not $procs) { $lines += 'no running next dev process found' }

Start-Sleep -Seconds 3
Set-Content -Path $report -Value $lines -Encoding UTF8
& 'e:\corvos\scripts\start-native.ps1' -Service web
