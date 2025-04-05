@echo off
REM ===========================================
REM Start script for Writingway
REM ===========================================

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating and setting up...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing requirements...
    pip install -r requirements.txt
) else (
    echo Activating existing virtual environment...
    call venv\Scripts\activate.bat
)

REM Run the main Python script
echo Running main.py...
python main.py

pause