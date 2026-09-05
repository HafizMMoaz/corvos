# Runs one child process and writes its stdout/stderr to separate log files
# with a timestamp prefixed on every line.
#
# Invoked by start-native.ps1's Start-Svc (via `powershell -File run-logged.ps1
# ...`) instead of Start-Process's -RedirectStandardOutput/-Error, which just
# streams raw bytes straight to the file with no per-line timestamp.
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Exe,
    [Parameter(Mandatory)] [string]$WorkDir,
    [Parameter(Mandatory)] [string]$OutFile,
    [Parameter(Mandatory)] [string]$ErrFile,
    # Child args arrive as ONE string joined with [char]31. Passing them as
    # separate argv tokens fails: celery's own flags (-A, -Ofair) get parsed
    # as parameters of THIS script and kill the wrapper before it launches
    # anything. A single named-parameter value sidesteps that entirely.
    [string]$ChildArgs
)

$ErrorActionPreference = 'Continue'
Set-Location $WorkDir

$ArgList = if ($ChildArgs) { $ChildArgs -split [char]31 } else { @() }

& $Exe @ArgList 2>&1 | ForEach-Object {
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        Add-Content -Path $ErrFile -Value "[$ts] $($_.ToString())" -Encoding utf8
    }
    else {
        Add-Content -Path $OutFile -Value "[$ts] $_" -Encoding utf8
    }
}
