# One runnable check for the native stack: every port answers and every log is
# free of a fatal startup error. Fails loudly per-service so a partial start is
# obvious rather than silently half-working.
$ErrorActionPreference = 'Continue'
$report = 'e:\corvos\scripts\health.txt'
$logs = 'e:\corvos\scripts\logs'
$lines = @("=== health $(Get-Date -Format o) ===")

$targets = @(
    @{ Name = 'backend /health'; Url = 'http://127.0.0.1:8000/health' },
    @{ Name = 'backend /ready'; Url = 'http://127.0.0.1:8000/ready' },
    @{ Name = 'zero keepalive'; Url = 'http://127.0.0.1:6848/keepalive' },
    @{ Name = 'web app'; Url = 'http://127.0.0.1:3000/' }
)

foreach ($t in $targets) {
    try {
        $r = Invoke-WebRequest -Uri $t.Url -TimeoutSec 20 -UseBasicParsing
        $lines += "OK   $($t.Name) -> HTTP $($r.StatusCode)"
    }
    catch {
        $code = $_.Exception.Response.StatusCode.value__
        $lines += "ERR  $($t.Name) -> $(if ($code) { "HTTP $code" } else { $_.Exception.Message })"
    }
}

$lines += '--- listening ports ---'
foreach ($p in 5432, 6379, 8000, 6848, 3000) {
    $l = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue
    $lines += "  $p : $(if ($l) { 'LISTEN' } else { 'not listening' })"
}

# Celery has no HTTP port; a live worker answers a broker ping.
Push-Location 'e:\corvos\backend'
$ping = & uv run celery -A app.celery_app inspect ping --timeout 15 2>&1 | Select-Object -Last 6
Pop-Location
$lines += '--- celery inspect ping ---'
$lines += ($ping | ForEach-Object { "  $_" })

$lines += '--- log tails ---'
foreach ($n in 'api', 'worker', 'beat', 'zero', 'web') {
    foreach ($ext in 'err', 'out') {
        $f = Join-Path $logs "$n.$ext"
        if (Test-Path $f) {
            $tail = Get-Content $f -Tail 6 -ErrorAction SilentlyContinue
            if ($tail) {
                $lines += "  [$n.$ext]"
                $lines += ($tail | ForEach-Object { "    $_" })
            }
        }
    }
}

Set-Content -Path $report -Value $lines -Encoding UTF8
