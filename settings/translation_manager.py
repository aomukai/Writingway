import gettext
import os
import logging
from PyQt5.QtCore import QObject, pyqtSignal

# List of supported languages
LANGUAGES = ["en", "de", "es", "fr", "pt", "pl", "ru", "ja", "zh", "ko"]

class TranslationManager(QObject):
    language_changed = pyqtSignal(str)

    def __init__(self, domain="writingway"):
        super().__init__()
        self.domain = domain
        self.locale_dir = os.path.join("assets", "locale")
        self.current_language = "en"
        self.setup_gettext(self.current_language)

    def setup_gettext(self, language):
        """
        Set up gettext for the specified language.
        """
        if language not in LANGUAGES:
            print(f"Invalid language '{language}', falling back to 'en'")
            language = "en"
        
        self.current_language = language
        logging.debug(f"Setting up gettext: language={language}, domain={self.domain}, locale_dir={self.locale_dir}")
        
        if language == "en":
            gettext.install(self.domain)
            return gettext.NullTranslations()
        
        if not os.path.exists(self.locale_dir):
            print(f"Error: locale directory does not exist: {self.locale_dir}")
            gettext.install(self.domain)
            return gettext.NullTranslations()
        
        mo_file = os.path.join(self.locale_dir, language, "LC_MESSAGES", f"{self.domain}.mo")
        if not os.path.exists(mo_file):
            print(f"Error: .mo file not found for language '{language}'")
            gettext.install(self.domain)
            return gettext.NullTranslations()
        
        try:
            translation = gettext.translation(self.domain, localedir=self.locale_dir, languages=[language], fallback=True)
            translation.install()
            return translation
        except Exception as e:
            print(f"Error setting up gettext for {language}: {e}")
            gettext.install(self.domain)
            return gettext.NullTranslations()

    def set_language(self, language):
        """
        Change the current language and emit a signal to update the UI.
        """
        if language != self.current_language:
            self.setup_gettext(language)
            self.language_changed.emit(language)