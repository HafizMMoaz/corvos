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
    [Parameter(ValueFromRemainingArguments)] [string[]]$ArgList
)

$ErrorActionPreference = 'Continue'
Set-Location $WorkDir

& $Exe @ArgList 2>&1 | ForEach-Object {
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff'
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        Add-Content -Path $ErrFile -Value "[$ts] $($_.ToString())" -Encoding utf8
    }
    else {
        Add-Content -Path $OutFile -Value "[$ts] $_" -Encoding utf8
    }
}
