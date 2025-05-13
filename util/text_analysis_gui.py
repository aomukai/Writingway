#!/usr/bin/env python
"""
text_analysis_gui.py

A PyQt5-based GUI that uses the core analysis module to:
- Provide a text editor for input.
- Highlight problematic sentences based on complexity, weak formulations, passive constructions, 
  non-standard speech verbs, filter words, telling not showing, weak verbs, overused words,
  pronoun clarity issues, and repetitive sentence starts.
- Features a collapsible interface with splitters for maximizing the text area.
"""

import sys
import importlib
import traceback
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextEdit, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QFrame, QCheckBox,
    QGroupBox, QGridLayout, QTabWidget, QSplitter, QScrollArea,
    QToolTip
)
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QBrush, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from util.analyzers import text_analysis

# Dictionary of languages and corresponding module names.
LANGUAGES = {
    "English": "text_analysis",
    "Dansk": "text_analysis_da",
    "Deutsch": "text_analysis_de",
    "Español": "text_analysis_es",
    "Français": "text_analysis_fr",
    "Hrvatski": "text_analysis_hr",
    "Italian": "text_analysis_it",
    "Lietuvių": "text_analysis_lt",
    "Nederlands": "text_analysis_nl",
    "Norsk Bokmål": "text_analysis_nb",
    "Polski": "text_analysis_pl",
    "Português": "text_analysis_pt",
    "Română": "text_analysis_ro",
    "Slovenščina": "text_analysis_sl",
    "Suomi": "text_analysis_fi",
    "Svenska": "text_analysis_sv",
    "Ελληνικά": "text_analysis_el",
    "Русский": "text_analysis_ru",
    "Українська": "text_analysis_uk",
    "Македонски": "text_analysis_mk",
    "日本語": "text_analysis_ja",
    "한국어": "text_analysis_ko",
    "中文": "text_analysis_zh"
}

LANGUAGE_CLASS_MAP = {
    "English": "English",
    "Dansk": "Danish",
    "Deutsch": "German",
    "Español": "Spanish",
    "Français": "French",
    "Hrvatski": "Croatian",
    "Italian": "Italian",
    "Lietuvių": "Lithuanian",
    "Nederlands": "Dutch",
    "Norsk Bokmål": "Norwegian",
    "Polski": "Polish",
    "Português": "Portuguese",
    "Română": "Romanian",
    "Slovenščina": "Slovenian",
    "Suomi": "Finnish",
    "Svenska": "Swedish",
    "Ελληνικά": "Greek",
    "Русский": "Russian",
    "Українська": "Ukrainian",
    "Македонски": "Macedonian",
    "日本語": "Japanese",
    "한국어": "Korean",
    "中文": "Chinese"
}

GENRE_TARGET_GRADES = {
    "Romance": 9,
    "Thriller": 11,
    "Hard Sci-Fi": 13,
    "Space Opera": 12,
    "Young Adult": 9,
    "Mystery": 10,
    "Fantasy": 11,
    "Historical Fiction": 12,
    "Literary Fiction": 13,
    "Horror": 11,
    "Non-Fiction": 12,
    "Biography": 11,
    "Self-help": 10,
    "Satire": 12,
    "Adventure": 10,
    "Crime": 11,
    "Paranormal": 10,
    "Dystopian": 12,
    "Memoir": 10,
    "Comedy": 9
}
CUSTOM_OPTION = "Custom"

# Define colors for each issue type.
COLORS = {
    "complex": QColor("#FFC0C0"),      # Red - Complex sentences
    "weak": QColor("#CCFFCC"),         # Green - Weak formulations/passive voice
    "nonstandard": QColor("#ADD8E6"),  # Light blue - Non-standard speech verbs
    "filter": QColor("#FFE4B5"),       # Light orange - Filter words
    "telling": QColor("#E6E6FA"),      # Lavender - Telling not showing
    "weak_verb": QColor("#FFDAB9"),    # Peach - Weak verbs
    "overused": QColor("#F0E68C"),     # Khaki - Overused words
    "pronoun": QColor("#FFB6C1"),      # Light pink - Unclear pronoun references
    "repetitive": QColor("#D8BFD8")    # Thistle - Repetitive sentence starts
}

class ComprehensiveAnalysisWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(Exception)

    def __init__(self, full_text, target_grade, analysis_instance):
        super().__init__()
        self.full_text = full_text
        self.target_grade = target_grade
        self.analysis_instance = analysis_instance

    def run(self):
        try:
            results = self.analysis_instance.comprehensive_analysis(self.full_text, self.target_grade)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(e)

class TextAnalysisApp(QWidget):
    def __init__(self, parent=None, initial_text="", save_callback=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setWindowTitle("Writingway Text Analysis Editor")
        self.resize(1000, 800)
        self.save_callback = save_callback
        self.analysis_instance = None
        self.current_language = "English"
        
        # Initialize UI first
        self.init_ui()
        
        # FORCE ENGLISH INITIALIZATION
        try:
            from util.analyzers import text_analysis
            if text_analysis.initialize():
                self.analysis_instance = text_analysis.EnglishTextAnalysis()
                self.current_module = text_analysis
                
                # LOAD TOOLTIP TEXTS BEFORE SETTING LANGUAGE IN THE COMBOBOX
                if hasattr(self.analysis_instance, "get_tooltips"):
                    current_tooltips = self.analysis_instance.get_tooltips()
                    self.set_tooltips(current_tooltips)
                    
                self.language_combo.setCurrentText("English")
                self.results_label.setText("English model initialized")
                
                # FORCE IMMEDIATE TOOLTIP UPDATE
                QApplication.processEvents()
                
                # SAVE THE MODEL DIRECTLY IN THE INSTANCE
                if text_analysis.nlp is not None:
                    self.analysis_instance.nlp = text_analysis.nlp
                else:
                    raise RuntimeError("Global English model not loaded")
                    
        except Exception as e:
            print("English init error:", e)
            self.results_label.setText("Critical error loading English")
            self.analysis_instance = None

        self.text_edit.setPlainText(initial_text)

    def init_ui(self):
        """Initializes the user interface."""
        # Main layout for the entire application.
        main_layout = QVBoxLayout(self)
    
        # Create tab widget.
        self.tabs = QTabWidget()
    
        # === Main Analysis Tab ===
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
    
        # Create the main splitter for the analysis tab.
        self.main_splitter = QSplitter(Qt.Vertical)
    
        # Top section - Legend and instructions.
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
    
        self.legend_container = self.create_legend_with_tooltips({})
        top_layout.addWidget(self.legend_container)
    
        instruction = QLabel("Enter your text below. Problematic text will be highlighted according to the legend.")
        top_layout.addWidget(instruction)
    
        # Middle section - Text editor.
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(True)
        self.text_edit.setMinimumHeight(300)  # Ensure editor is always visible.
    
        # Bottom section - Controls.
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
    
        # Analysis controls group.
        controls_group = QGroupBox("Analysis Controls")
        controls_layout = QHBoxLayout(controls_group)
    
        # Genre selection.
        genre_layout = QVBoxLayout()
        genre_label = QLabel("Select:")
        genre_layout.addWidget(genre_label)
    
        # Language selection combo box.
        self.language_combo = QComboBox()
        self.language_combo.addItems(LANGUAGES.keys())
        self.language_combo.currentTextChanged.connect(self.change_language)
        genre_layout.addWidget(self.language_combo)
    
        # Genre selection combo box.
        self.genre_combo = QComboBox()
        genre_options = list(GENRE_TARGET_GRADES.keys()) + [CUSTOM_OPTION]
        self.genre_combo.addItems(genre_options)
        self.genre_combo.currentTextChanged.connect(self.genre_changed)
        genre_layout.addWidget(self.genre_combo)
    
        # Custom target grade layout.
        custom_grade_layout = QHBoxLayout()
        self.custom_label = QLabel("Target Grade:")
        self.custom_entry = QLineEdit()
        self.custom_entry.setFixedWidth(50)
    
        custom_grade_layout.addWidget(self.custom_label)
        custom_grade_layout.addWidget(self.custom_entry)
        genre_layout.addLayout(custom_grade_layout)
    
        # Hide custom controls initially.
        self.custom_label.hide()
        self.custom_entry.hide()
    
        # Analysis options.
        options_layout = QVBoxLayout()
        options_label = QLabel("Analysis Types:")
        options_layout.addWidget(options_label)
    
        # Add layouts to the controls layout.
        controls_layout.addLayout(genre_layout)
        controls_layout.addLayout(options_layout)
    
        # Add controls group to bottom layout.
        bottom_layout.addWidget(controls_group)

        # Create scrollable area for checkboxes.
        self.analysis_options = {}
        analysis_options_scroll = QScrollArea()
        analysis_options_scroll.setWidgetResizable(True)
        analysis_options_widget = QWidget()
        analysis_options_layout = QVBoxLayout(analysis_options_widget)
        self.create_analysis_checkboxes(analysis_options_layout)
        analysis_options_scroll.setWidget(analysis_options_widget)
        options_layout.addWidget(analysis_options_scroll)
    
        controls_layout.addLayout(options_layout)
        controls_group.setLayout(controls_layout)
        bottom_layout.addWidget(controls_group)

        # Analysis button.
        self.analyze_button = QPushButton("Run Analysis")
        self.analyze_button.clicked.connect(self.run_analysis)
        bottom_layout.addWidget(self.analyze_button)

        # Results summary label.
        self.results_label = QLabel("")
        self.results_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.results_label.setLineWidth(1)
        self.results_label.setWordWrap(True)
        bottom_layout.addWidget(self.results_label)
    
        # Add the main splitter widgets.
        self.main_splitter.addWidget(top_widget)
        self.main_splitter.addWidget(self.text_edit)
        self.main_splitter.addWidget(bottom_widget)
    
        # Set initial splitter sizes to give text editor most space.
        self.main_splitter.setSizes([150, 400, 150])
    
        # Add the main splitter to the analysis tab.
        analysis_layout.addWidget(self.main_splitter)
    
        # === Settings Tab ===
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
    
        # Create scrollable area for settings.
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_content = QWidget()
        settings_content_layout = QVBoxLayout(settings_content)
        self.setup_settings_tab(settings_content_layout)
        settings_scroll.setWidget(settings_content)
        settings_layout.addWidget(settings_scroll)
    
        # Add both tabs to the tab widget.
        self.tabs.addTab(analysis_tab, "Text Analysis")
        self.tabs.addTab(settings_tab, "Settings")
    
        # Add the tab widget to the main layout.
        main_layout.addWidget(self.tabs)

        # NEW: Save & Close button to return updated text.
        save_close_button = QPushButton("Save & Close")
        save_close_button.clicked.connect(self.save_and_close)
        main_layout.addWidget(save_close_button)
        
    def change_language(self, language):
        """Handles language switching with model state validation."""
        if language == self.current_language:
            return

        self.current_language = language
        module_name = LANGUAGES.get(language)
        
        if not module_name:
            self.revert_to_english()
            return

        try:
            # Special handling for English
            if module_name == "text_analysis":
                from util.analyzers import text_analysis
                if not text_analysis.initialize():
                    raise RuntimeError("English model failed to initialize")
                
                # Create new instance with proper model injection
                self.analysis_instance = text_analysis.EnglishTextAnalysis()
                
                # Force model reference from global module
                if text_analysis.nlp is not None:
                    self.analysis_instance.nlp = text_analysis.nlp
                    
                if not hasattr(self.analysis_instance, 'nlp') or self.analysis_instance.nlp is None:
                    raise RuntimeError("English model reference missing")
                
                self.current_module = text_analysis
                self.language_combo.setCurrentText("English")
                self.results_label.setText("English model active")
                
                # Update tooltip texts for English
                if hasattr(self.analysis_instance, "get_tooltips"):
                    self.set_tooltips(self.analysis_instance.get_tooltips())
                return

            # Handling other languages
            module = importlib.import_module(f"util.analyzers.{module_name}")
            class_name = LANGUAGE_CLASS_MAP[language] + "TextAnalysis"
            analysis_class = getattr(module, class_name)
            new_instance = analysis_class()
            
            # Connect model_loaded signal to update tooltips when the model finishes downloading
            if hasattr(new_instance, 'model_loaded'):
                new_instance.model_loaded.connect(self.on_model_loaded)
            
            # Initialize model; if download is in progress, update instance and exit early
            if not new_instance.initialize():
                if getattr(new_instance, 'download_in_progress', False):
                    self.results_label.setText(f"Downloading {language} model...")
                    self.analysis_instance = new_instance
                    return
                else:
                    self.revert_to_english()
                    return
            
            # Update references after successful initialization
            self.analysis_instance = new_instance
            self.current_module = module
            self.language_combo.setCurrentText(language)
            self.results_label.setText(f"{language} model active")
            
            # Update tooltips if available
            if hasattr(new_instance, "get_tooltips"):
                self.set_tooltips(new_instance.get_tooltips())

        except Exception as e:
            print(f"Language switch error: {str(e)}")
            self.revert_to_english()

    def handle_language_error(self, language, error_msg):
        """Handles errors during language switching"""
        logging.error(f"Language switch error ({language}): {error_msg}")
        traceback.print_exc()
        self.results_label.setText(f"Error loading {language}. Reverting to English.")
        self.revert_to_english()

    def revert_to_english(self):
        """Forceful English revert with model verification."""
        try:
            from util.analyzers import text_analysis
            
            # Reinitialize core English module
            if not text_analysis.initialize():
                raise RuntimeError("Core English initialization failed")
                
            # Create new instance with model injection
            self.analysis_instance = text_analysis.EnglishTextAnalysis()
            
            # Force model reference from global state
            if text_analysis.nlp is not None:
                self.analysis_instance.nlp = text_analysis.nlp
                
            # Final verification
            if not hasattr(self.analysis_instance, 'nlp') or self.analysis_instance.nlp is None:
                raise RuntimeError("Model reference not propagated")
                
            self.current_language = "English"
            self.language_combo.setCurrentText("English")
            self.results_label.setText("English model restored")
            
            # Update tooltips
            if hasattr(self.analysis_instance, "get_tooltips"):
                self.set_tooltips(self.analysis_instance.get_tooltips())
                
        except Exception as e:
            print(f"Critical English revert failure: {str(e)}")
            self.results_label.setText("Fatal error: English unavailable")
            self.analysis_instance = None
                
    def on_model_loaded(self):
        """Callback triggered when the model finishes downloading."""
        # Once the model is loaded, update the tooltips immediately.
        if hasattr(self.analysis_instance, "get_tooltips"):
            self.set_tooltips(self.analysis_instance.get_tooltips())
        self.results_label.setText(f"{self.current_language} model active")

    def check_module_ready(self, language):
        """Checks if the module is ready. (Not used with the signal/slot approach)"""
        pass  # Remove or modify as needed
        
    def create_legend_with_tooltips(self, tooltips):
        """
        Creates and returns the legend widget using provided tooltip translations.
        :param tooltips: Dictionary with keys corresponding to issue types and tooltip strings.
        """
        legend_group = QGroupBox("Highlighting Legend")
        legend_layout = QGridLayout()

        # Define the legend items with keys matching those in the tooltip dictionary.
        legend_items = [
            ("Complex sentences", COLORS["complex"], tooltips.get("complex", "")),
            ("Weak formulations/passive voice", COLORS["weak"], tooltips.get("weak", "")),
            ("Non-standard speech verbs", COLORS["nonstandard"], tooltips.get("nonstandard", "")),
            ("Filter words", COLORS["filter"], tooltips.get("filter", "")),
            ("Telling not showing", COLORS["telling"], tooltips.get("telling", "")),
            ("Weak verbs", COLORS["weak_verb"], tooltips.get("weak_verb", "")),
            ("Overused words", COLORS["overused"], tooltips.get("overused", "")),
            ("Unclear pronoun references", COLORS["pronoun"], tooltips.get("pronoun", "")),
            ("Repetitive sentence starts", COLORS["repetitive"], tooltips.get("repetitive", ""))
        ]

        for i, (label_text, color, tip) in enumerate(legend_items):
            row, col = divmod(i, 3)
    
            swatch = QFrame()
            swatch.setFixedSize(20, 20)
            swatch.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
    
            label = QLabel(label_text)
            label.setToolTip(tip.strip().replace('\n', ' '))
    
            legend_layout.addWidget(swatch, row, col * 2)
            legend_layout.addWidget(label, row, col * 2 + 1)

        legend_group.setLayout(legend_layout)
        return legend_group
        
    def set_tooltips(self, tooltips):
        """Updates the legend's tooltips based on the provided translations."""
        new_legend = self.create_legend_with_tooltips(tooltips)
        parent_layout = self.legend_container.parentWidget().layout()
        index = parent_layout.indexOf(self.legend_container)
        parent_layout.takeAt(index)
        self.legend_container.deleteLater()
        self.legend_container = new_legend
        parent_layout.insertWidget(index, self.legend_container)

    def create_analysis_checkboxes(self, layout):
        """Creates and adds analysis type checkboxes to the given layout."""
        self.analysis_options["complexity"] = QCheckBox("Sentence complexity")
        self.analysis_options["complexity"].setChecked(True)
        layout.addWidget(self.analysis_options["complexity"])

        self.analysis_options["weak_formulations"] = QCheckBox("Weak formulations/passive voice")
        self.analysis_options["weak_formulations"].setChecked(True)
        layout.addWidget(self.analysis_options["weak_formulations"])

        self.analysis_options["speech_verbs"] = QCheckBox("Non-standard speech verbs")
        self.analysis_options["speech_verbs"].setChecked(True)
        layout.addWidget(self.analysis_options["speech_verbs"])

        self.analysis_options["filter_words"] = QCheckBox("Filter words")
        self.analysis_options["filter_words"].setChecked(True)
        layout.addWidget(self.analysis_options["filter_words"])
        
        self.analysis_options["telling"] = QCheckBox("Telling not showing")
        self.analysis_options["telling"].setChecked(True)
        layout.addWidget(self.analysis_options["telling"])
        
        self.analysis_options["weak_verbs"] = QCheckBox("Weak verbs")
        self.analysis_options["weak_verbs"].setChecked(True)
        layout.addWidget(self.analysis_options["weak_verbs"])
        
        self.analysis_options["overused"] = QCheckBox("Overused words")
        self.analysis_options["overused"].setChecked(True)
        layout.addWidget(self.analysis_options["overused"])
        
        self.analysis_options["pronoun_clarity"] = QCheckBox("Unclear pronoun references")
        self.analysis_options["pronoun_clarity"].setChecked(True)
        layout.addWidget(self.analysis_options["pronoun_clarity"])
        
        self.analysis_options["repetitive"] = QCheckBox("Repetitive sentence starts")
        self.analysis_options["repetitive"].setChecked(True)
        layout.addWidget(self.analysis_options["repetitive"])

    def setup_settings_tab(self, layout):
        """Sets up the settings tab with analysis thresholds and interface customization."""
        # Thresholds group.
        thresholds_group = QGroupBox("Analysis Thresholds")
        thresholds_layout = QGridLayout()
        
        thresholds_layout.addWidget(QLabel("Overused words threshold:"), 0, 0)
        self.overused_threshold = QLineEdit("3")
        self.overused_threshold.setFixedWidth(50)
        thresholds_layout.addWidget(self.overused_threshold, 0, 1)
        
        thresholds_layout.addWidget(QLabel("Overused words window (chars):"), 1, 0)
        self.overused_window = QLineEdit("1000")
        self.overused_window.setFixedWidth(50)
        thresholds_layout.addWidget(self.overused_window, 1, 1)
        
        thresholds_layout.addWidget(QLabel("Repetitive starts threshold:"), 2, 0)
        self.repetitive_threshold = QLineEdit("3")
        self.repetitive_threshold.setFixedWidth(50)
        thresholds_layout.addWidget(self.repetitive_threshold, 2, 1)
        
        thresholds_group.setLayout(thresholds_layout)
        layout.addWidget(thresholds_group)
        
        # Appearance settings.
        appearance_group = QGroupBox("Interface Customization")
        appearance_layout = QVBoxLayout()
        
        self.maximize_editor_btn = QPushButton("Maximize Text Editor")
        self.maximize_editor_btn.clicked.connect(self.toggle_maximize_editor)
        appearance_layout.addWidget(self.maximize_editor_btn)
        
        self.restore_layout_btn = QPushButton("Restore Default Layout")
        self.restore_layout_btn.clicked.connect(self.restore_default_layout)
        appearance_layout.addWidget(self.restore_layout_btn)
        
        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)
        
        # User guide.
        guide_group = QGroupBox("Tips")
        guide_layout = QVBoxLayout(guide_group)
        
        tip_text = QLabel(
            "<b>Interface Tips:</b><br>"
            "• Drag the splitter handles to resize sections<br>"
            "• Double-click a splitter handle to collapse/expand a section<br>"
            "• Use 'Maximize Text Editor' for a distraction-free writing experience<br>"
            "• Switch to the Analysis tab to see your text and run analysis<br>"
            "• Click 'Restore Default Layout' to reset the interface"
        )
        tip_text.setWordWrap(True)
        guide_layout.addWidget(tip_text)
        
        guide_group.setLayout(guide_layout)
        layout.addWidget(guide_group)
        
        layout.addStretch()

    def toggle_maximize_editor(self):
        """Maximizes or restores the text editor area."""
        # Switch to the analysis tab.
        self.tabs.setCurrentIndex(0)
        
        if self.maximize_editor_btn.text() == "Maximize Text Editor":
            # Save current sizes for later restoration.
            self.saved_sizes = self.main_splitter.sizes()
            # Emphasize the editor (nearly invisible top and bottom sections).
            self.main_splitter.setSizes([1, 10000, 1])
            self.maximize_editor_btn.setText("Restore Layout")
        else:
            if hasattr(self, 'saved_sizes'):
                self.main_splitter.setSizes(self.saved_sizes)
            else:
                self.restore_default_layout()
            self.maximize_editor_btn.setText("Maximize Text Editor")

    def restore_default_layout(self):
        """Resets the splitters to default positions."""
        self.tabs.setCurrentIndex(0)
        self.main_splitter.setSizes([150, 400, 150])
        self.maximize_editor_btn.setText("Maximize Text Editor")

    def genre_changed(self, text):
        """Shows or hides the custom target grade controls based on the genre selection."""
        if text == CUSTOM_OPTION:
            self.custom_label.show()
            self.custom_entry.show()
        else:
            self.custom_label.hide()
            self.custom_entry.hide()

    def run_analysis(self):
        """Runs the text analysis on the input text."""
        full_text = self.text_edit.toPlainText()
        if not full_text:
            self.results_label.setText("Please enter text for analysis.")
            return
        if self.analysis_instance is None or self.analysis_instance.nlp is None:
            self.results_label.setText("The model is not loaded.")
            return

        selected_genre = self.genre_combo.currentText()
        if selected_genre == CUSTOM_OPTION:
            try:
                target_grade = float(self.custom_entry.text())
            except ValueError:
                self.results_label.setText("Invalid difficulty level. Please enter a valid number.")
                return
        else:
            target_grade = GENRE_TARGET_GRADES.get(selected_genre, 8)

        self.results_label.setText("Analyzing text...")
        self.worker = ComprehensiveAnalysisWorker(full_text, target_grade, self.analysis_instance)
        self.worker.finished.connect(self.update_highlighting)
        self.worker.error.connect(self.handle_error)
        self.worker.start()

    def update_highlighting(self, results):
        """
        Updates the text highlighting based on the analysis results.
        Recomputes the enabled analysis options and applies the corresponding text formats.
        """
        enabled_analyses = {key: checkbox.isChecked() for key, checkbox in self.analysis_options.items()}
        cursor = self.text_edit.textCursor()
        formats = {key: QTextCharFormat() for key in COLORS}
        for issue_type, color in COLORS.items():
            formats[issue_type].setBackground(QBrush(color))
        
        cursor.setPosition(0)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.setCharFormat(QTextCharFormat())
        
        stats = {key: 0 for key in ["complex_sentences", "weak_formulations", "nonstandard_speech", "filter_words", "telling_not_showing", "weak_verbs", "overused_words", "pronoun_clarity", "repetitive_starts"]}
        
        if enabled_analyses.get("complexity", False):
            for sent in results["sentence_analysis"]:
                if sent["complex"]:
                    cursor.setPosition(sent["start"])
                    cursor.setPosition(sent["end"], QTextCursor.KeepAnchor)
                    cursor.mergeCharFormat(formats["complex"])
                    stats["complex_sentences"] += 1
        
        if enabled_analyses.get("weak_formulations", False):
            for start, end in results["weak_formulations"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["weak"])
                stats["weak_formulations"] += 1
            for start, end in results["passive_voice"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["weak"])
                stats["weak_formulations"] += 1
        
        if enabled_analyses.get("speech_verbs", False):
            for start, end, unused in results["nonstandard_speech"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["nonstandard"])
                stats["nonstandard_speech"] += 1
        
        if enabled_analyses.get("filter_words", False):
            for start, end, unused in results["filter_words"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["filter"])
                stats["filter_words"] += 1
        
        if enabled_analyses.get("telling", False):
            for start, end, unused in results["telling_not_showing"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["telling"])
                stats["telling_not_showing"] += 1
        
        if enabled_analyses.get("weak_verbs", False):
            for start, end, unused, unused in results["weak_verbs"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["weak_verb"])
                stats["weak_verbs"] += 1
        
        if enabled_analyses.get("overused", False):
            for start, end, unused, unused in results["overused_words"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["overused"])
                stats["overused_words"] += 1
        
        if enabled_analyses.get("pronoun_clarity", False):
            for start, end, unused in results["pronoun_clarity"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["pronoun"])
                stats["pronoun_clarity"] += 1
        
        if enabled_analyses.get("repetitive", False):
            for start, end, unused in results["repeated_sentence_starts"]:
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(formats["repetitive"])
                stats["repetitive_starts"] += 1
        
        self.update_results_summary(stats, results["dialogue_ratio"])

    def update_results_summary(self, stats, dialogue_ratio):
        """Updates the results summary label with the analysis statistics."""
        summary = "Analysis Results Summary:\n"
        total_issues = sum(stats.values())
        summary += f"Total issues found: {total_issues}\n"
        summary += f"- Complex sentences: {stats['complex_sentences']}\n"
        summary += f"- Weak formulations/passive: {stats['weak_formulations']}\n"
        summary += f"- Non-standard speech verbs: {stats['nonstandard_speech']}\n"
        summary += f"- Filter words: {stats['filter_words']}\n"
        summary += f"- Telling not showing: {stats['telling_not_showing']}\n"
        summary += f"- Weak verbs: {stats['weak_verbs']}\n"
        summary += f"- Overused words: {stats['overused_words']}\n"
        summary += f"- Unclear pronoun references: {stats['pronoun_clarity']}\n"
        summary += f"- Repetitive sentence starts: {stats['repetitive_starts']}\n"
        
        dialogue_percentage = round(dialogue_ratio * 100, 1)
        summary += f"\nDialogue percentage: {dialogue_percentage}%"
        if dialogue_percentage > 70:
            summary += " (dialogue-heavy)"
        elif dialogue_percentage < 20:
            summary += " (narrative-heavy)"
        
        self.results_label.setText(summary)

    def handle_error(self, exception):
        """Handles errors during analysis."""
        self.results_label.setText(f"Error during analysis: {exception}")

    def save_and_close(self):
        """
        Called when the 'Save & Close' button is clicked.
        Retrieves the current text from the analysis editor, calls the save_callback
        (if provided) with the updated text, and then closes this window.
        """
        updated_text = self.text_edit.toPlainText()
        if self.save_callback:
            self.save_callback(updated_text)
        self.close()

def main():
    app = QApplication(sys.argv)
    # For standalone testing, no initial text or callback is provided.
    window = TextAnalysisApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
