import sys
import os
import json

def check_dependencies():
    """Check for required modules and notify the user via Tkinter if any are missing."""
    missing = []
    # Check for PyQt5
    try:
        import PyQt5
    except ImportError:
        missing.append("PyQt5")
    # Check for pyttsx3
    try:
        import pyttsx3
    except ImportError:
        missing.append("pyttsx3")
    
    if missing:
        # Try to use Tkinter (which is included with most Python installations) for a GUI error message.
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()  # Hide the main window.
            messagebox.showerror(
                "Missing Dependencies",
                "The application requires the following module(s): " + ", ".join(missing) +
                "\n\nPlease install them by running:\n\npip install " + " ".join(missing) +
                "\n\nOn Windows: Win+R to open a console, then type cmd."
            )
        except Exception:
            # Fallback to console output if Tkinter isn't available.
            print("The application requires the following module(s): " + ", ".join(missing))
            print("Please install them by running:\n\npip install " + " ".join(missing))
        sys.exit(1)

# Run dependency check before any further imports.
check_dependencies()

# Now import the modules needed for the application.
from PyQt5.QtWidgets import QApplication
from workbench import WorkbenchWindow
from settings.theme_manager import ThemeManager
from settings.settings_manager import WWSettingsManager

def writingway_preload_settings(app):
    # Load and apply the saved theme to the application.
    theme = WWSettingsManager.get_appearance_settings()["theme"]
    try:
        ThemeManager.apply_to_app(theme)
    except Exception as e:
        print("Error applying theme:", e)
    
    fontsize = WWSettingsManager.get_appearance_settings()["text_size"]
    if fontsize:
        font = app.font()
        font.setPointSize(fontsize)
        app.setFont(font)


def main():
    app = QApplication(sys.argv)
    writingway_preload_settings(app)
    window = WorkbenchWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
