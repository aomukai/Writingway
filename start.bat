@echo off
REM ===========================================
REM Start script for Writingway
REM ===========================================

REM Activate the virtual environment.
echo Activating virtual environment...
call venv\Scripts\activate
set KMP_DUPLICATE_LIB_OK=TRUE

REM Run the main Python script.
echo Running main.py...
python main.py

pause
