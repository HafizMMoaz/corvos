# Waits for any running Visual Studio installer/update to finish, then retries
# the Build Tools (C++ workload) install. Status goes to scripts\vcvars_watch.txt.
$ErrorActionPreference = 'Continue'
$log = 'e:\corvos\scripts\vcvars_watch.txt'
$vcvarsCandidates = @(
    'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat'
)

function Test-Vcvars {
    foreach ($c in $vcvarsCandidates) { if (Test-Path $c) { return $c } }
    return $null
}

function Log($msg) { Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format o), $msg) }

Set-Content -Path $log -Value "=== vcvars watcher $(Get-Date -Format o) ==="

$existing = Test-Vcvars
if ($existing) { Log "vcvars already present: $existing"; exit 0 }

$deadline = (Get-Date).AddMinutes(60)
while ((Get-Date) -lt $deadline) {
    $busy = @(Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^(setup|VisualStudioUpdate|vs_setup|devenv)' })
    if ($busy.Count -eq 0) {
        Log 'no VS installer running - starting winget Build Tools install'
        & winget install --id Microsoft.VisualStudio.2022.BuildTools --exact `
            --accept-source-agreements --accept-package-agreements `
            --override '--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended' *>> $log
        Log "winget exit=$LASTEXITCODE"
        Start-Sleep -Seconds 20
        $found = Test-Vcvars
        if ($found) { Log "SUCCESS: $found"; exit 0 }
        Log 'vcvars still missing after winget - will poll again'
    }
    else {
        Log "waiting - VS busy: $($busy.Name -join ', ')"
    }
    Start-Sleep -Seconds 30
}
Log 'TIMEOUT: gave up after 60 minutes'
exit 1
