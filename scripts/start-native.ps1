# Starts the Corvos stack natively (no Docker) against the local Postgres 18
# + Memurai. Mirrors the roles in backend/scripts/docker/entrypoint.sh.
#
#   .\start-native.ps1              # api + worker + beat + zero + web
#   .\start-native.ps1 -Service api # just one
#
# ponytail: processes are detached via Start-Process with stdout/stderr sent to
# scripts/logs/*.out|.err, because this shell mangles native-exe output. Ceiling:
# no supervision/restart -- if a service dies you read its log and re-run this.
# Upgrade path: NSSM services or a Procfile runner if that becomes annoying.
[CmdletBinding()]
param(
    [ValidateSet('all', 'api', 'worker', 'beat', 'zero', 'web')]
    [string]$Service = 'all'
)

$ErrorActionPreference = 'Continue'
$root = 'e:\corvos'
$logs = Join-Path $root 'scripts\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$report = Join-Path $root 'scripts\start_native.txt'
$lines = @("=== start-native ($Service) $(Get-Date -Format o) ===")

function ConvertTo-EscapedCommandLine {
    # Start-Process -ArgumentList joins array elements with bare spaces and only
    # quotes elements containing SPACES -- an arg like --queues=a,b,c keeps its
    # commas unquoted, and CommandLineToArgvW splits commas into separate args,
    # which silently ate the wrapper's -OutFile/-ErrFile params. Pre-quote
    # anything with a separator character and hand over ONE escaped string.
    param([string[]]$Parts)
    ($Parts | ForEach-Object {
        if ($_ -match '[ \t,"\x00-\x1f]') { '"' + $_.Replace('"', '\"') + '"' } else { $_ }
    }) -join ' '
}

function Start-Svc {
    # NOTE: the arg-list parameter must NOT be named $Args -- that collides with
    # PowerShell's automatic $args variable and silently arrives empty.
    param($Name, $Exe, $ArgList, $WorkDir)
    $out = Join-Path $logs "$Name.out"
    $err = Join-Path $logs "$Name.err"
    Remove-Item $out, $err -ErrorAction SilentlyContinue
    # uv resolves to a real .exe; pnpm resolves to a .cmd/.ps1 shim, which
    # a raw exec rejects with "not a valid Win32 application" -- those get
    # launched through cmd.exe, which knows how to run a shim.
    $exePath = (Get-Command $Exe -ErrorAction SilentlyContinue).Source
    if (-not $exePath) {
        $script:lines += "FAILED  $Name : '$Exe' not found on PATH"
        return
    }
    if ([IO.Path]::GetExtension($exePath) -ne '.exe') {
        $ArgList = @('/c', $Exe) + $ArgList
        $exePath = "$env:SystemRoot\system32\cmd.exe"
    }
    # Routed through run-logged.ps1 rather than raw -RedirectStandardOutput/
    # -RedirectStandardError: that redirection just streams bytes straight to
    # the file with no per-line timestamp, so the wrapper adds one.
    $wrapper = Join-Path $PSScriptRoot 'run-logged.ps1'
    # Child args go as ONE -ChildArgs value joined with [char]31 -- see
    # run-logged.ps1: loose argv tokens like celery's -A would be parsed as
    # parameters of the wrapper script and kill it before launch.
    $wrapperArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $wrapper,
        '-Exe', $exePath, '-WorkDir', $WorkDir, '-OutFile', $out, '-ErrFile', $err,
        '-ChildArgs', ($ArgList -join [char]31)
    )
    try {
        $escaped = ConvertTo-EscapedCommandLine $wrapperArgs
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $escaped `
            -WindowStyle Hidden -PassThru
        $script:lines += "started $Name pid=$($p.Id) : $exePath $($ArgList -join ' ')"
    }
    catch {
        $script:lines += "FAILED  $Name : $($_.Exception.Message)"
    }
}

# --- backend API ------------------------------------------------------------
# main.py calls load_dotenv() itself, so no --env-file needed here.
if ($Service -in @('all', 'api')) {
    Start-Svc 'api' 'uv' @('run', 'python', 'main.py') (Join-Path $root 'backend')
    Start-Sleep -Seconds 5
}

# --- celery worker ----------------------------------------------------------
# Windows: --pool=threads. The entrypoint's default prefork relies on fork(),
# which billiard cannot do on Windows; --autoscale is prefork-only so it is
# replaced with a fixed --concurrency.
if ($Service -in @('all', 'worker')) {
    $q = 'corvos'
    Start-Svc 'worker' 'uv' @(
        'run', 'celery', '-A', 'app.celery_app', 'worker',
        '--loglevel=info', '--pool=threads', '--concurrency=4',
        '--prefetch-multiplier=1', '-Ofair',
        "--queues=$q,$q.connectors,$q.gateway"
    ) (Join-Path $root 'backend')
    Start-Sleep -Seconds 3
}

# --- celery beat ------------------------------------------------------------
if ($Service -in @('all', 'beat')) {
    Start-Svc 'beat' 'uv' @('run', 'celery', '-A', 'app.celery_app', 'beat', '--loglevel=info') `
    (Join-Path $root 'backend')
}

# --- zero-cache -------------------------------------------------------------
# Env mirrors the zero-cache service in docker/docker-compose.dev.yml, with
# container hostnames swapped for localhost. The connection string is read out
# of web/.env so the password stays out of this script and the process table.
if ($Service -in @('all', 'zero')) {
    $webEnv = Get-Content (Join-Path $root 'web\.env') | Where-Object { $_ -match '^DATABASE_URL=' }
    if (-not $webEnv) {
        $lines += 'FAILED  zero : DATABASE_URL not found in web/.env'
    }
    else {
        $pgUrl = ($webEnv -split '=', 2)[1].Trim() + '?sslmode=disable'
        $env:ZERO_UPSTREAM_DB = $pgUrl
        $env:ZERO_CVR_DB = $pgUrl
        $env:ZERO_CHANGE_DB = $pgUrl
        $env:ZERO_REPLICA_FILE = Join-Path $logs 'zero.db'
        # 4848 (and 4849, its auto-derived change-streamer port) fall inside a
        # Windows TCP excluded-port range reserved by Hyper-V/WSL's NAT (check
        # with `netsh interface ipv4 show excludedportrange protocol=tcp`), so
        # zero-cache dies with EACCES after its ~7min initial resync. 6848 sits
        # clear of every reserved range on this box.
        $env:ZERO_PORT = '6848'
        $env:ZERO_APP_PUBLICATIONS = 'zero_publication'
        $env:ZERO_AUTO_RESET = 'true'
        $env:ZERO_ADMIN_PASSWORD = 'corvos-zero-admin'
        $env:ZERO_QUERY_URL = 'http://localhost:3000/api/zero/query'
        $env:ZERO_MUTATE_URL = 'http://localhost:3000/api/zero/mutate'
        $env:ZERO_QUERY_FORWARD_COOKIES = 'true'
        Start-Svc 'zero' 'pnpm' @('exec', 'zero-cache') (Join-Path $root 'web')
    }
}

# --- web (Next.js dev) ------------------------------------------------------
if ($Service -in @('all', 'web')) {
    Start-Svc 'web' 'pnpm' @('dev') (Join-Path $root 'web')
}

$lines += "logs: $logs"
Set-Content -Path $report -Value $lines -Encoding UTF8
