@echo off
REM Builds pgvector against the local PostgreSQL 18 install.
REM ponytail: pgvector ships no official Windows binary, so nmake from source is
REM the only route. Build only -- `nmake install` writes into Program Files and
REM needs an elevated shell, so it is deliberately NOT run here.
setlocal

set "LOG=e:\corvos\scripts\pgvector_build.txt"
set "PGROOT=C:\Program Files\PostgreSQL\18"
set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
set "SRC=%TEMP%\pgvector"

> "%LOG%" echo === pgvector build ===

if not exist "%VCVARS%" (
    >> "%LOG%" echo ERROR: vcvars64.bat not found at %VCVARS%
    exit /b 1
)
call "%VCVARS%" > nul 2>&1
>> "%LOG%" echo vcvars loaded

if exist "%SRC%\.git" (
    >> "%LOG%" echo reusing existing clone at %SRC%
    git -C "%SRC%" fetch --tags --depth 1 origin >> "%LOG%" 2>&1
) else (
    git clone --depth 1 --branch v0.8.1 https://github.com/pgvector/pgvector.git "%SRC%" >> "%LOG%" 2>&1
)
if errorlevel 1 (
    >> "%LOG%" echo ERROR: clone/fetch failed
    exit /b 1
)

cd /d "%SRC%"
>> "%LOG%" echo --- version ---
git -C "%SRC%" describe --tags >> "%LOG%" 2>&1

>> "%LOG%" echo --- nmake ---
nmake /F Makefile.win >> "%LOG%" 2>&1
>> "%LOG%" echo nmake exit=%errorlevel%

>> "%LOG%" echo --- artifacts ---
if exist "%SRC%\vector.dll" (>> "%LOG%" echo built: vector.dll) else (>> "%LOG%" echo MISSING: vector.dll)

endlocal
