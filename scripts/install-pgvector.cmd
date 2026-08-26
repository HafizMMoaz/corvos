@echo off
REM Installs the already-built pgvector into PostgreSQL 18 and switches
REM wal_level to logical (required by zero-cache logical replication).
REM
REM MUST run in an ELEVATED shell: it writes into Program Files and restarts
REM the postgresql-x64-18 service.
REM
REM WARNING: the restart briefly drops ALL connections on this instance,
REM including the anyreps_db / arifyhub / baatpay databases.
setlocal

set "LOG=d:\Corvos\scripts\pgvector_install.txt"
set "PGROOT=C:\Program Files\PostgreSQL\18"
set "SRC=%TEMP%\pgvector"
set "PSQL=%PGROOT%\bin\psql.exe"
set "PGPASSFILE=%TEMP%\ros_pgpass.conf"

> "%LOG%" echo === pgvector install ===

net session >nul 2>&1
if errorlevel 1 (
    >> "%LOG%" echo ERROR: not elevated. Re-run this script as Administrator.
    exit /b 1
)

if not exist "%SRC%\vector.dll" (
    >> "%LOG%" echo ERROR: vector.dll missing. Run build-pgvector.cmd first.
    exit /b 1
)

>> "%LOG%" echo --- copying extension files ---
copy /Y "%SRC%\vector.dll" "%PGROOT%\lib\" >> "%LOG%" 2>&1
copy /Y "%SRC%\vector.control" "%PGROOT%\share\extension\" >> "%LOG%" 2>&1
copy /Y "%SRC%\sql\vector--*.sql" "%PGROOT%\share\extension\" >> "%LOG%" 2>&1

>> "%LOG%" echo --- setting wal_level=logical (ALTER SYSTEM) ---
"%PSQL%" -w -U postgres -h 127.0.0.1 -p 5432 -d postgres -c "ALTER SYSTEM SET wal_level = 'logical';" >> "%LOG%" 2>&1

>> "%LOG%" echo --- restarting postgresql-x64-18 ---
net stop postgresql-x64-18 >> "%LOG%" 2>&1
net start postgresql-x64-18 >> "%LOG%" 2>&1

>> "%LOG%" echo --- creating corvos database ---
"%PSQL%" -w -U postgres -h 127.0.0.1 -p 5432 -d postgres -c "CREATE DATABASE corvos;" >> "%LOG%" 2>&1

>> "%LOG%" echo --- enabling extensions in corvos ---
"%PSQL%" -w -U postgres -h 127.0.0.1 -p 5432 -d corvos -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;" >> "%LOG%" 2>&1

>> "%LOG%" echo --- verification ---
"%PSQL%" -w -U postgres -h 127.0.0.1 -p 5432 -d corvos -At -c "select 'wal_level=' || current_setting('wal_level');" >> "%LOG%" 2>&1
"%PSQL%" -w -U postgres -h 127.0.0.1 -p 5432 -d corvos -At -c "select 'installed=' || extname || ' ' || extversion from pg_extension where extname in ('vector','pg_trgm');" >> "%LOG%" 2>&1
"%PSQL%" -w -U postgres -h 127.0.0.1 -p 5432 -d corvos -At -c "select 'roundtrip=' || ('[1,2,3]'::vector <-> '[1,2,4]'::vector)::text;" >> "%LOG%" 2>&1

>> "%LOG%" echo === done ===
endlocal
