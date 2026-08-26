# Corvos on/off switch. Run it once to start the stack, run it again to stop.
#
#   .\scripts\ros.ps1            # toggle: start if down, stop if up
#   .\scripts\ros.ps1 -Status    # just report, change nothing
#   .\scripts\ros.ps1 -Start     # force start
#   .\scripts\ros.ps1 -Stop      # force stop
#
# Starting delegates to start-native.ps1 (api + worker + beat + zero + web) so
# there is one definition of how each service launches.
#
# Postgres and Redis are deliberately NOT stopped: this box runs other databases
# (anyreps_db / arifyhub / baatpay) on the same Postgres instance, so killing it
# would take them down too. They are only ever started, never stopped.
#
# ponytail: "is it running" is answered by who owns ports 8000/4848/3000 plus a
# command-line match for celery (which has no port), not by a pidfile. Ceiling:
# if some unrelated app owns port 3000, stop would kill it -- the pids are
# printed before anything dies so you can see that. Upgrade path: real service
# definitions (NSSM) if this ever needs to survive a reboot.
[CmdletBinding()]
param(
    [switch]$Start,
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = 'Continue'
$root = 'd:\Corvos'
$logs = Join-Path $root 'scripts\logs'
$PG_SERVICE = 'postgresql-x64-18'
$WEB_PORT = 3000
$API_PORT = 8000
# zero-cache runs on 6848, not the 4848 default: 4848/4849 sit inside a
# Windows Hyper-V/WSL excluded TCP port range on this box (start-native.ps1
# sets ZERO_PORT=6848 to route around it).
$ZERO_PORT = 6848

# --- discovery --------------------------------------------------------------

function Get-StackPid {
    $found = [System.Collections.Generic.HashSet[int]]::new()

    foreach ($port in $API_PORT, $ZERO_PORT, $WEB_PORT) {
        foreach ($c in Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
            [void]$found.Add([int]$c.OwningProcess)
        }
    }

    # celery worker/beat expose no port, so match how start-native launches them.
    foreach ($p in Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'app\.celery_app' }) {
        [void]$found.Add([int]$p.ProcessId)
    }

    # pids start-native recorded, in case a service died before binding its port.
    $report = Join-Path $root 'scripts\start_native.txt'
    if (Test-Path $report) {
        foreach ($m in Select-String -Path $report -Pattern 'pid=(\d+)' -AllMatches) {
            foreach ($g in $m.Matches) {
                $candidate = [int]$g.Groups[1].Value
                if (Get-Process -Id $candidate -ErrorAction SilentlyContinue) {
                    [void]$found.Add($candidate)
                }
            }
        }
    }

    $found
}

# NOTE: do not hold this in an [ordered]@{} keyed by port number -- an
# OrderedDictionary indexed with an int does positional lookup, not key lookup,
# so $state[8000] throws "argument out of range" instead of returning a value.
function Test-PortUp {
    param([int]$Port)
    [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Get-PortState {
    @(
        [pscustomobject]@{ Port = 5432; Label = 'postgres  ' }
        [pscustomobject]@{ Port = 6379; Label = 'redis     ' }
        [pscustomobject]@{ Port = $API_PORT; Label = 'backend   ' }
        [pscustomobject]@{ Port = $ZERO_PORT; Label = 'zero-cache' }
        [pscustomobject]@{ Port = $WEB_PORT; Label = 'web       ' }
    ) | ForEach-Object {
        $_ | Add-Member -NotePropertyName Up -NotePropertyValue (Test-PortUp -Port $_.Port) -PassThru
    }
}

function Write-Status {
    foreach ($p in Get-PortState) {
        $mark = if ($p.Up) { 'UP  ' } else { 'down' }
        Write-Host ("  {0}  {1}  :{2}" -f $mark, $p.Label, $p.Port)
    }
    $celery = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'app\.celery_app' })
    $mark = if ($celery.Count) { 'UP  ' } else { 'down' }
    Write-Host ("  {0}  celery      ({1} process(es))" -f $mark, $celery.Count)
}

# --- stop -------------------------------------------------------------------

function Stop-Tree {
    param([int]$ProcessId)
    foreach ($child in Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue) {
        Stop-Tree -ProcessId ([int]$child.ProcessId)
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-Stack {
    $targets = Get-StackPid
    if ($targets.Count -eq 0) {
        Write-Host 'Nothing to stop - stack is already down.'
        return
    }

    Write-Host "Stopping Corvos ($($targets.Count) process tree(s))..."
    foreach ($procId in $targets) {
        $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($p) {
            Write-Host ("  kill pid={0} {1}" -f $procId, $p.ProcessName)
            Stop-Tree -ProcessId $procId
        }
    }

    Start-Sleep -Seconds 3
    $left = Get-StackPid
    if ($left.Count) {
        Write-Host "  WARNING: still alive: $($left -join ', ')"
    }
    Write-Host 'Stopped. (Postgres and Redis left running on purpose.)'
    Write-Status
}

# --- start ------------------------------------------------------------------

function Start-Dependency {
    # Postgres: a Windows service, so start it rather than spawning anything.
    $svc = Get-Service -Name $PG_SERVICE -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host "  WARNING: service '$PG_SERVICE' not found - is Postgres 18 installed?"
    }
    elseif ($svc.Status -ne 'Running') {
        Write-Host "  postgres is $($svc.Status) - elevating to start it (expect a UAC prompt)"
        & (Join-Path $root 'scripts\start-pg.ps1')
        Start-Sleep -Seconds 3
    }
    else {
        Write-Host '  postgres already running'
    }

    if (Test-PortUp -Port 6379) {
        Write-Host '  redis already running'
        return
    }
    # Memurai is the native Redis on this box; fall back to a Docker container.
    $redis = Get-Service -Name 'Memurai' -ErrorAction SilentlyContinue
    if ($redis) {
        Write-Host '  starting Memurai (redis)'
        Start-Service -Name 'Memurai' -ErrorAction SilentlyContinue
    }
    else {
        Write-Host '  redis not listening and Memurai not installed - start it yourself:'
        Write-Host '    docker run -d --name redis -p 6379:6379 redis:latest'
    }
}

function Start-Stack {
    Write-Host 'Checking dependencies...'
    Start-Dependency

    Write-Host 'Starting Corvos (api, worker, beat, zero-cache, web)...'
    & (Join-Path $root 'scripts\start-native.ps1')

    $report = Join-Path $root 'scripts\start_native.txt'
    if (Test-Path $report) { Get-Content $report | ForEach-Object { "  $_" } }

    # The API needs ~110s on this box (postgres checkpointer + embedding-model
    # warmup happen before uvicorn binds), so this waits well past that. A
    # too-short wait just prints a misleading "down" -- it does not break start.
    Write-Host 'Waiting for ports to come up (up to 180s; the API warms up slowly)...'
    $deadline = (Get-Date).AddSeconds(180)
    while ((Get-Date) -lt $deadline) {
        if ((Test-PortUp -Port $API_PORT) -and (Test-PortUp -Port $WEB_PORT)) { break }
        Start-Sleep -Seconds 3
    }

    Write-Status
    Write-Host ''
    Write-Host "  web      http://localhost:$WEB_PORT"
    Write-Host "  api      http://localhost:$API_PORT/docs"
    Write-Host "  logs     $logs"
    Write-Host '  health   .\scripts\check-health.ps1'
    Write-Host ''
    Write-Host '  Run this script again to stop everything.'
}

# --- dispatch ---------------------------------------------------------------

$running = (Get-StackPid).Count -gt 0

if ($Status) {
    Write-Host "Corvos is $(if ($running) { 'RUNNING' } else { 'STOPPED' })"
    Write-Status
    return
}

if ($Start -and $Stop) {
    Write-Host 'Pick one of -Start or -Stop, not both.'
    return
}

if ($Stop) { Stop-Stack; return }
if ($Start) { Start-Stack; return }

# No explicit flag: toggle on current state.
if ($running) { Stop-Stack } else { Start-Stack }
