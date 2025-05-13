#!/bin/bash
# ===========================================
# Start script for Writingway (macOS/Linux)
# ===========================================

# Activate the virtual environment.
echo "Activating virtual environment..."
source venv/bin/activate
export KMP_DUPLICATE_LIB_OK=TRUE

# Run the main Python script.
echo "Running main.py..."
python main.py
