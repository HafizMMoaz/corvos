@echo off
REM One-time bootstrap: creates the corvos role + database on local Postgres 18.
REM Temporarily switches pg_hba.conf to trust for local connections (a backup is
REM kept), restarts the service, creates role/DB, then restores scram auth.
set PGBIN=C:\Program Files\PostgreSQL\18\bin
set HBA=C:\Program Files\PostgreSQL\18\data\pg_hba.conf
set LOG=e:\corvos\scripts\create_role.txt

> "%LOG%" echo === create corvos role %DATE% %TIME% ===

copy /Y "%HBA%" "%HBA%.pre-corvos.bak" >> "%LOG%" 2>&1
>> "%LOG%" echo backup exit=%ERRORLEVEL%

> "%HBA%" echo local   all   all   trust
>> "%HBA%" echo host    all   all   127.0.0.1/32   trust
>> "%HBA%" echo host    all   all   ::1/128   trust
>> "%LOG%" echo rewrite exit=%ERRORLEVEL%

net stop postgresql-x64-18 >> "%LOG%" 2>&1
net start postgresql-x64-18 >> "%LOG%" 2>&1
>> "%LOG%" echo restart exit=%ERRORLEVEL%

timeout /t 4 /nobreak >nul

"%PGBIN%\psql.exe" -U postgres -h 127.0.0.1 -c "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='corvos') THEN CREATE ROLE corvos LOGIN SUPERUSER PASSWORD 'corvos'; END IF; END $$;" >> "%LOG%" 2>&1
>> "%LOG%" echo role exit=%ERRORLEVEL%

"%PGBIN%\psql.exe" -U postgres -h 127.0.0.1 -tc "SELECT 1 FROM pg_database WHERE datname='corvos'" | findstr 1 >nul
if errorlevel 1 (
    "%PGBIN%\psql.exe" -U postgres -h 127.0.0.1 -c "CREATE DATABASE corvos OWNER corvos;" >> "%LOG%" 2>&1
    >> "%LOG%" echo createdb exit=%ERRORLEVEL%
) else (
    >> "%LOG%" echo createdb skipped - already exists
)

"%PGBIN%\psql.exe" -U postgres -h 127.0.0.1 -d corvos -c "CREATE EXTENSION IF NOT EXISTS vector;" >> "%LOG%" 2>&1
>> "%LOG%" echo pgvector exit=%ERRORLEVEL%

copy /Y "%HBA%.pre-corvos.bak" "%HBA%" >> "%LOG%" 2>&1
>> "%LOG%" echo restore exit=%ERRORLEVEL%

net stop postgresql-x64-18 >> "%LOG%" 2>&1
net start postgresql-x64-18 >> "%LOG%" 2>&1
>> "%LOG%" echo final-restart exit=%ERRORLEVEL%

>> "%LOG%" echo === done ===
exit /b 0
