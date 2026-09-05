# Applies the Alembic schema to the corvos database.
# MUST run before zero-cache starts: zero-cache requires the `zero_publication`
# publication to already exist, else it crash-loops with
# "Unknown or invalid publications". See docker-compose.deps-only.yml.
$ErrorActionPreference = 'Continue'
$log = 'e:\corvos\scripts\migrate_tail.txt'
$raw = Join-Path $env:TEMP 'ros_alembic_raw.txt'

Push-Location 'e:\corvos\backend'
& uv run alembic upgrade head *> $raw
$code = $LASTEXITCODE
Pop-Location

$tail = Get-Content $raw -ErrorAction SilentlyContinue | Select-Object -Last 30
Set-Content -Path $log -Value (@("alembic exit=$code", '--- tail ---') + $tail) -Encoding UTF8
