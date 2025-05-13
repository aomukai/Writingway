import os
import glob
import re
import sys
import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QToolBar, QAction,
    QFontComboBox, QComboBox, QLabel, QMessageBox, QTextEdit, QStyle, QShortcut
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QColor, QTextCharFormat, QPen, QKeySequence

from .focus_mode import PlainTextEdit
from spylls.hunspell import Dictionary
from util.find_dialog import FindDialog
from settings.theme_manager import ThemeManager

class SceneEditor(QWidget):
    """Scene editor with toolbar, text area, and spellchecking support."""

    def __init__(self, controller, tint_color=QColor("black")):
        super().__init__()
        self.controller = controller
        self.tint_color = tint_color
        self.suppress_updates = False

        # Setup dictionary path
        base_module = sys.modules[self.__module__].__file__
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(base_module)))
        self.dict_dir = os.path.join(project_dir, "assets", "dictionaries")

        self.languages = {}
        self.dictionary = None
        self.extra_selections = []
        self.settings_file = os.path.join(self.dict_dir, "editor_settings.json")
        self.saved_language = "Off"
        
        # Load saved language preference if available
        self.load_language_preference()

        self.shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_find.activated.connect(self.open_find_dialog)
        self.find_dialog = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar("Editor Toolbar")
        self.editor = PlainTextEdit()

        self.setup_toolbar()
        self.setup_editor()

        layout.addWidget(self.toolbar)
        layout.addWidget(self.editor)
        layout.setContentsMargins(0, 0, 0, 0)

        self.load_languages()

    def setup_toolbar(self):
        self.toolbar.setStyleSheet("")  # Reset any custom styles to use theme
        # Formatting actions
        for name, icon, tip, func, check in [
            ("bold", "assets/icons/bold.svg", _("Bold"), self.controller.toggle_bold, True),
            ("italic", "assets/icons/italic.svg", _("Italic"), self.controller.toggle_italic, True),
            ("underline", "assets/icons/underline.svg", _("Underline"), self.controller.toggle_underline, True)
        ]:
            setattr(self, f"{name}_action", self.add_action(name, icon, tip, func, check))
        self.toolbar.addSeparator()

        # TTS
        self.tts_action = self.add_action(
            "tts", "assets/icons/play-circle.svg", _("Play TTS (or Stop)"),
            self.controller.toggle_tts, False
        )
        self.toolbar.addSeparator()

        # Alignment
        for name, icon, tip, func in [
            ("align_left", "assets/icons/align-left.svg", _("Align Left"), self.controller.align_left),
            ("align_center", "assets/icons/align-center.svg", _("Center Align"), self.controller.align_center),
            ("align_right", "assets/icons/align-right.svg", _("Align Right"), self.controller.align_right)
        ]:
            setattr(self, f"{name}_action", self.add_action(name, icon, tip, func, False))

        self.toolbar.addSeparator()
        # Font selection
        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self.controller.update_font_family)
        self.toolbar.addWidget(self.font_combo)

        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems([str(s) for s in [10,12,14,16,18,20,24,28,32]])
        self.font_size_combo.setCurrentText("12")
        self.font_size_combo.currentIndexChanged.connect(
            lambda: self.controller.set_font_size(int(self.font_size_combo.currentText()))
        )
        self.toolbar.addWidget(self.font_size_combo)
        self.toolbar.addSeparator()

        # Scene-specific
        for name, icon, tip, func in [
            ("manual_save","assets/icons/save.svg",_("Manual Save"),self.controller.manual_save_scene),
            ("oh_shit","assets/icons/share.svg",_("Show Backups"),self.controller.on_oh_shit),
            ("analysis_editor","assets/icons/feather.svg",_("Analysis Editor"),self.controller.open_analysis_editor),
            ("whisper_app","assets/icons/mic.svg",_("Open Whisper"),self.controller.open_whisper_app),
            ("web_llm","assets/icons/wikidata.svg",_("Open Web with LLM"),self.controller.open_web_llm),
            ("ia_window","assets/icons/arch.svg",_("Open Internet Archive"),self.controller.open_ia_window)
        ]:
            setattr(self, f"{name}_action", self.add_action(name, icon, tip, func, False))

        self.toolbar.addSeparator()
        # Language combo
        self.toolbar.addWidget(QLabel(_("Spell check:")))
        self.lang_combo = QComboBox()
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        self.toolbar.addWidget(self.lang_combo)

    def add_action(self, name, icon_path, tooltip, callback, checkable=False):
        action = QAction(ThemeManager.get_tinted_icon(icon_path, self.tint_color), "", self)
        action.setToolTip(tooltip)
        action.setCheckable(checkable)
        action.triggered.connect(callback)
        self.toolbar.addAction(action)
        return action

    def setup_editor(self):
        e = self.editor
        e.setPlaceholderText(_("Select a node to edit..."))
        e.setContextMenuPolicy(Qt.CustomContextMenu)
        e.customContextMenuRequested.connect(self.show_context_menu)
        e.textChanged.connect(self.controller.on_editor_text_changed)
        e.textChanged.connect(self.start_spellcheck_timer)
        e.cursorPositionChanged.connect(self.update_toolbar_state)
        e.selectionChanged.connect(self.update_toolbar_state)

        # Adjust viewport margins to prevent scrollbar from obscuring content
        scrollbar_width = e.style().pixelMetric(QStyle.PM_ScrollBarExtent)
        e.setViewportMargins(0, 0, scrollbar_width, 0)  # Reserve space on the right for scrollbar

        # Spellcheck timer
        self.spellcheck_timer = QTimer(self)
        self.spellcheck_timer.setSingleShot(True)
        self.spellcheck_timer.setInterval(500)
        self.spellcheck_timer.timeout.connect(self.check_spelling)
        
        # Set a callback to check spelling when content is loaded
        QTimer.singleShot(500, self.delayed_initial_check)

    def load_languages(self):
        self.languages.clear()
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        self.lang_combo.addItem("Off")

        # Populate from .aff/.dic pairs
        for aff in glob.glob(os.path.join(self.dict_dir, '*.aff')):
            code = os.path.splitext(os.path.basename(aff))[0]
            dic = os.path.join(self.dict_dir, f"{code}.dic")
            if os.path.isfile(dic):
                self.languages[code] = code
                self.lang_combo.addItem(code)

        # Add Other entry at bottom
        self.lang_combo.addItem("Other")

        # Restore saved
        saved_index = self.lang_combo.findText(self.saved_language)
        if saved_index >= 0:
            self.lang_combo.setCurrentIndex(saved_index)
        else:
            self.lang_combo.setCurrentIndex(0)
        self.lang_combo.blockSignals(False)

        # Apply saved if not Off/Other
        if self.saved_language not in ("Off", "Other"):
            self.apply_saved_language()

    def on_language_changed(self, idx):
        lang = self.lang_combo.currentText()

        # We turn off the check
        if lang == "Off":
            self.dictionary = None
            self.clear_spellcheck_highlights()
            self.save_language_preference(lang)
            return

        # Handling “Other” items
        if lang == "Other":
            dlg = QMessageBox(self)
            dlg.setWindowTitle(_("Additional Dictionaries"))
            dlg.setTextFormat(Qt.RichText)
            dlg.setTextInteractionFlags(Qt.TextBrowserInteraction)
            dlg.setText(_(
                "For more dictionaries, please visit:<br>"
                "<a href=\"https://github.com/LibreOffice/dictionaries\">"
                "https://github.com/LibreOffice/dictionaries</a><br>"
                "Paste the .aff and .dic file into the folder:<br>"
                "Writingway/assets/dictionaries"
            ))
            dlg.exec_()
            prev = self.saved_language if self.saved_language in self.languages else "Off"
            self.lang_combo.setCurrentText(prev)
            return

        # Build full path (without extension) to the .aff/.dic files
        dict_base = os.path.join(self.dict_dir, lang)
        try:
            # Load the dictionary from "<dict_base>.aff" and "<dict_base>.dic"
            self.dictionary = Dictionary.from_files(dict_base)
            # Run spell‑check immediately
            self.check_spelling()
            # Remember selection
            self.save_language_preference(lang)
        except Exception as e:
            QMessageBox.critical(
                self,
                _("Error"),
                _(f"Cannot load {lang}: {e}")
            )
            self.dictionary = None
            self.clear_spellcheck_highlights()
        
    def save_language_preference(self, lang):
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            settings = {"language": lang}
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
            self.saved_language = lang
        except Exception as e:
            print(f"Error saving language preference: {e}")
            
    def load_language_preference(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.saved_language = settings.get("language", "Off")
        except Exception as e:
            print(f"Error loading language preference: {e}")
            
    def apply_saved_language(self):
        if self.saved_language not in self.languages:
            return

        # Build full path (without extension) to the .aff/.dic files
        dict_base = os.path.join(self.dict_dir, self.saved_language)
        try:
            # Load the dictionary from "<dict_base>.aff" and "<dict_base>.dic"
            self.dictionary = Dictionary.from_files(dict_base)
            # If there's already text in the editor, highlight misspellings right away
            if self.editor.toPlainText():
                self.check_spelling()
        except Exception as e:
            print(f"Error loading dictionary {self.saved_language}: {e}")

    def clear_spellcheck_highlights(self):
        self.extra_selections = []
        self.editor.setExtraSelections([])

    def start_spellcheck_timer(self):
        if self.dictionary:
            self.spellcheck_timer.start()

    def check_spelling(self):
        """Check spelling and highlight misspelled words with improved visibility."""
        if not self.dictionary:
            return
        text = self.editor.toPlainText()
        self.extra_selections = []
        
        # Create enhanced format for spelling errors
        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
        fmt.setUnderlineColor(QColor(255, 0, 0))  # Bright red
        
        # Make underline thicker with pen
        pen = QPen(QColor(255, 0, 0))
        pen.setWidth(2)  # Thicker underline
        fmt.setUnderlineColor(pen.color())
        
        # Use improved regex for word detection that can handle apostrophes and hyphens
        # This matches words and contractions better than the simple \w+ pattern
        word_pattern = r'\b[a-zA-Z]+[\'-]?[a-zA-Z]*\b'
        
        for m in re.finditer(word_pattern, text):
            w = m.group()
            if not self.dictionary.lookup(w):
                cur = QTextCursor(self.editor.document())
                cur.setPosition(m.start())
                cur.setPosition(m.end(), QTextCursor.KeepAnchor)
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cur
                sel.format = fmt
                self.extra_selections.append(sel)
        self.editor.setExtraSelections(self.extra_selections)

    def show_context_menu(self, pos):
        menu = self.editor.createStandardContextMenu(pos)
        cur = self.editor.textCursor()
        if cur.hasSelection():
            act = menu.addAction(_("Rewrite"))
            act.triggered.connect(self.controller.rewrite_selected_text)
        if self.dictionary:
            wc = self.editor.cursorForPosition(pos)
            wc.select(QTextCursor.WordUnderCursor)
            w = wc.selectedText()
            if w and not self.dictionary.lookup(w):
                sugs = self.dictionary.suggest(w)
                if sugs:
                    sm = menu.addMenu(_("Suggestions"))
                    for s in sugs:
                        a = sm.addAction(s)
                        a.triggered.connect(lambda _, s=s, c=wc: self.replace_word(c, s))
                else:
                    menu.addAction(_("(No suggestions)"))
        menu.exec_(self.editor.mapToGlobal(pos))

    def replace_word(self, cursor, new):
        cursor.insertText(new)
        self.check_spelling()

    def update_toolbar_state(self):
        if self.suppress_updates:
            return
        self.suppress_updates = True
        cur = self.editor.textCursor()
        if cur.hasSelection():
            fm = self.get_selection_formats(cur.selectionStart(), cur.selectionEnd())
            self.update_toggles_for_selection(fm)
        else:
            cf = self.editor.currentCharFormat()
            self.update_toggles(cf)
        aln = cur.blockFormat().alignment()
        self.align_left_action.setChecked(aln == Qt.AlignLeft)
        self.align_center_action.setChecked(aln == Qt.AlignCenter)
        self.align_right_action.setChecked(aln == Qt.AlignRight)
        self.suppress_updates = False

    def get_selection_formats(self, start, end):
        """
        Returns a list of character formats for each character in the start-end range.
        Used to analyze the formatting of the selected text.
        """
        formats = []
        cursor = self.editor.textCursor()
        for pos in range(start, end):
            cursor.setPosition(pos)
            formats.append(cursor.charFormat())
        return formats

    def delayed_initial_check(self):
        """Perform a delayed initial spell check to make sure content is loaded."""
        if self.dictionary and self.editor and self.editor.toPlainText():
            self.check_spelling()

    def update_toggles(self, cf):
        self.bold_action.setChecked(cf.fontWeight() >= QFont.Bold)
        self.italic_action.setChecked(cf.fontItalic())
        self.underline_action.setChecked(cf.fontUnderline())

    def update_toggles_for_selection(self, formats):
        """
        formats: a list of QTextCharFormat objects for each character in the selection.
        Checks if all characters have the same style (bold, italic, underline).
        """
        # If no formats, exit
        if not formats:
            return

        # Get the state of the first character as a reference
        first_format = formats[0]
        first_bold = first_format.font().bold()
        first_italic = first_format.font().italic()
        first_underline = first_format.font().underline()

        # Check that all characters have the same style as the first one
        all_bold = all(fmt.font().bold() == first_bold for fmt in formats)
        all_italic = all(fmt.font().italic() == first_italic for fmt in formats)
        all_underline = all(fmt.font().underline() == first_underline for fmt in formats)

        # Set the state of the buttons
        self.bold_action.setChecked(all_bold and first_bold)
        self.italic_action.setChecked(all_italic and first_italic)
        self.underline_action.setChecked(all_underline and first_underline)

    def update_tint(self, tint_color):
        self.tint_color = tint_color
        for name in [
            "bold","italic","underline",
            "tts","align_left","align_center","align_right",
            "manual_save","oh_shit","analysis_editor",
            "whisper_app","web_llm","ia_window"
        ]:
            action = getattr(self, f"{name}_action")
            path = f"assets/icons/{name.replace('_','-')}.svg"
            action.setIcon(ThemeManager.get_tinted_icon(path, tint_color))
            
    def open_find_dialog(self):
        if self.find_dialog is None:
            self.find_dialog = FindDialog(self.editor, self)
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.search_field.setFocus()