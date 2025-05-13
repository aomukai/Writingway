import sys
import logging
from settings.translation_manager import TranslationManager
from settings.settings_manager import WWSettingsManager

def exception_hook(exctype, value, traceback):
    logging.error("Unhandled exception", exc_info=(exctype, value, traceback))
    sys.__excepthook__(exctype, value, traceback)
sys.excepthook = exception_hook

def check_dependencies():
    """Check for required modules and notify the user via Tkinter if any are missing."""
    missing = []
    try:
        import PyQt5
    except ImportError:
        missing.append("PyQt5")
    try:
        import pyttsx3
    except ImportError:
        missing.append("pyttsx3")
    
    if missing:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                _("Missing Dependencies"),
                _("The application requires the following module(s): ") + ", ".join(missing) +
                _("\n\nPlease install them by running:\n\npip install ") + " ".join(missing) +
                _("\n\nOn Windows: Win+R to open a console, then type cmd.")
            )
        except Exception:
            print("The application requires the following module(s): " + ", ".join(missing))
            print("Please install them by running:\n\npip install " + " ".join(missing))
        sys.exit(1)

# Initialize translations
translation_manager = TranslationManager()
translation_manager.set_language(WWSettingsManager.get_general_settings().get("language", "en"))

# Run dependency check after gettext is set up
check_dependencies()

from PyQt5.QtWidgets import QApplication
from workbench import WorkbenchWindow
from settings.theme_manager import ThemeManager

def writingway_preload_settings(app):
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
    window = WorkbenchWindow(translation_manager)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()