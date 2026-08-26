@echo off
REM Starts the Postgres 18 service. Runs elevated via start-pg.ps1 (UAC).
REM Service start mode is left as-is (Manual) -- changing it is the user's call.
set REPORT=d:\Corvos\scripts\pg_start.txt
> "%REPORT%" echo === start postgresql-x64-18 ===
net start postgresql-x64-18 >> "%REPORT%" 2>&1
>> "%REPORT%" echo exit=%ERRORLEVEL%
>> "%REPORT%" echo --- sc query ---
sc query postgresql-x64-18 >> "%REPORT%" 2>&1
