@echo off
REM =================================================
REM  Writingway Setup – Forces Python 3.11 environment
REM =================================================

setlocal EnableDelayedExpansion
chcp 65001 >nul
title Writingway Setup

:: -------------------------------------------------
::  Always run in the script's own folder
:: -------------------------------------------------
cd /d "%~dp0"

:: Determine if this cmd.exe was launched with /c (usually Explorer/double-click)
echo %cmdcmdline% | find /i "/c" >nul
set "IS_CMDLINE=%errorlevel%"

:: -------------------------------------------------
::  Optional: require administrator privileges
::  (needed if winget installs system-wide)
:: -------------------------------------------------
if "%IS_CMDLINE%"=="0" (
   >nul 2>&1 net session || (
    echo In order to download Python 3.11 this setup may need
    echo to run as Administrator. If the first download fails,
    echo right-click this file and choose "Run as administrator".
    echo Alternatively, you can also install Python 3.11 manually
    echo by downloading it from the Microsoft Store or searching Google.
    echo.
    pause
    )
)

echo.
echo =================================================
echo   WRITINGWAY SETUP – installing Python 3.11
echo =================================================
echo.
echo Note: You can rerun this script to fix missing module errors.
echo.

REM -------------------------------------------------
REM  Helper routines
REM -------------------------------------------------
set "STEP=INITIALISING"

goto :main

:abort
echo.
echo *** ERROR: %~1
echo     Step: %STEP%
echo.
pause
goto :terminate

:terminate
if "%IS_CMDLINE%"=="0" (
    exit 1
) else (
    exit /b 1
)
goto :eof

:RUN
REM Usage: call :RUN "command" "step name" "error message"
set "STEP=%~2"
call %~1
if errorlevel 1 call :abort "%~3"
goto :eof

:main
REM -------------------------------------------------
REM  1. Detect existing Python 3.11
REM -------------------------------------------------
set "STEP=Detecting Python 3.11"

py -3.11 -c "import sys; print('PY311_OK')" >nul 2>&1
if errorlevel 1 (
     call :abort "py launcher missing or broken"
)

for /f %%V in ('py -3.11 -c "import sys; print('PY311_OK')" 2^>nul') do if "%%V"=="PY311_OK" (
    echo [OK] Found Python 3.11 on the system.
    goto :create_venv
)
echo [..] Python 3.11 not found.

REM -------------------------------------------------
REM  2. Install Python 3.11 via winget if missing
REM -------------------------------------------------
set "STEP=Installing Python 3.11 via winget"
echo [..] Python 3.11 not found – attempting to install with winget...
set "PYLAUNCHER_ALLOW_INSTALL=TRUE"

where winget >nul 2>&1 || (
    echo winget not available; please install Python 3.11 manually or via the Microsoft Store.
    pause
    call :abort "winget not found"
)

winget install --id Python.Python.3.11 --exact --source winget --accept-package-agreements --accept-source-agreements -h
if errorlevel 1 call :abort "winget install of Python 3.11 failed"

echo [OK] Python 3.11 installed successfully.

REM Re-check Python availability
py -3.11 -c "import sys; print('PY311_OK')" >nul 2>&1
if errorlevel 1 call :abort "py -3.11 still not found after winget install"
pause

:create_venv
REM -------------------------------------------------
REM  3. Create or validate venv
REM -------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    call :RUN "py -3.11 -m venv venv" "Creating venv" "venv creation failed"
    echo [OK] venv created
) else (
    echo [OK] venv folder already exists
)
pause

REM -------------------------------------------------
REM  4. Check venv Python version
REM -------------------------------------------------
set "STEP=Checking venv version"
for /f "delims=" %%V in ('venv\Scripts\python.exe -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "VENV_VER=%%V"
if not defined VENV_VER call :abort "Cannot read venv python version"
if "!VENV_VER:~0,5!" neq "3.11." (
    call :abort "venv uses !VENV_VER! (need 3.11.x) – delete the venv folder and rerun this script"
    goto :eof
)


echo [OK] venv is using Python !VENV_VER!

REM -------------------------------------------------
REM  5. Activate venv + install dependencies
REM -------------------------------------------------
call venv\Scripts\activate || call :abort "Failed to activate venv"

call :RUN "python -m pip install --upgrade pip" "Upgrading pip" "pip upgrade failed"
call :RUN "python -m pip install --upgrade setuptools" "Upgrading setuptools" "setuptools upgrade failed"

if exist requirements.txt (
    call :RUN "pip install -r requirements.txt" "Installing requirements" "requirements.txt install failed"
) else (
    echo No requirements.txt found — skipping dependencies install.
)

call :RUN "python -m spacy download en_core_web_sm" "spaCy model" "spaCy model download failed"
call :RUN "python -m pip install beautifulsoup4" "BeautifulSoup4" "BeautifulSoup4 install failed"

echo.
echo =================================================
echo   SETUP COMPLETE! Writingway is ready.
echo =================================================
pause
exit /b 0
