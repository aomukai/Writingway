#!/usr/bin/env python3
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QToolBar, QAction, QFontComboBox, QComboBox, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QColor
from .focus_mode import PlainTextEdit

class SceneEditor(QWidget):
    """Scene editor with toolbar and text area."""
    def __init__(self, controller, tint_color=QColor("black")):
        super().__init__()
        self.controller = controller
        self.tint_color = tint_color
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

    def setup_toolbar(self):
        # Formatting Actions
        self.bold_action = self.add_action("bold", "assets/icons/bold.svg", "Bold", self.controller.toggle_bold, checkable=True)
        self.italic_action = self.add_action("italic", "assets/icons/italic.svg", "Italic", self.controller.toggle_italic, checkable=True)
        self.underline_action = self.add_action("underline", "assets/icons/underline.svg", "Underline", self.controller.toggle_underline, checkable=True)
        self.toolbar.addSeparator()
        self.tts_action = self.add_action("tts", "assets/icons/play-circle.svg", "Play TTS (or Stop if playing)", self.controller.toggle_tts)
        self.toolbar.addSeparator()
        self.align_left_action = self.add_action("align_left", "assets/icons/align-left.svg", "Align Left", self.controller.align_left)
        self.align_center_action = self.add_action("align_center", "assets/icons/align-center.svg", "Center Align", self.controller.align_center)
        self.align_right_action = self.add_action("align_right", "assets/icons/align-right.svg", "Align Right", self.controller.align_right)

        # Font Selection
        self.font_combo = QFontComboBox()
        self.font_combo.setToolTip("Select a font")
        self.font_combo.currentFontChanged.connect(self.controller.update_font_family)
        self.toolbar.addWidget(self.font_combo)
        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems([str(size) for size in [10, 12, 14, 16, 18, 20, 24, 28, 32]])
        self.font_size_combo.setCurrentText("12")
        self.font_size_combo.setToolTip("Select font size")
        self.font_size_combo.currentIndexChanged.connect(lambda: self.controller.set_font_size(int(self.font_size_combo.currentText())))
        self.toolbar.addWidget(self.font_size_combo)

        # Scene-Specific Actions
        self.toolbar.addSeparator()
        self.manual_save_action = self.add_action("manual_save", "assets/icons/save.svg", "Manual Save", self.controller.manual_save_scene)
        self.oh_shit_action = self.add_action("oh_shit", "assets/icons/share.svg", "Show Backups", self.controller.on_oh_shit)
        self.analysis_editor_action = self.add_action("analysis_editor", "assets/icons/feather.svg", "Open Analysis Editor", self.controller.open_analysis_editor)
        self.wikidata_dialog_action = self.add_action("wikidata_dialog", "assets/icons/wikidata.svg", "Open Wikipedia", self.controller.open_wikidata_search)
        self.toolbar.addSeparator()

        # POV, Character, Tense Pulldowns
        pulldown_widget = QWidget()
        pulldown_layout = QHBoxLayout(pulldown_widget)
        pulldown_layout.setContentsMargins(0, 0, 0, 0)
        self.pov_combo = self.add_combo(pulldown_layout, "POV", ["First Person", "Third Person Limited", "Omniscient", "Custom..."], self.controller.handle_pov_change)
        self.pov_character_combo = self.add_combo(pulldown_layout, "POV Character", ["Alice", "Bob", "Charlie", "Custom..."], self.controller.handle_pov_character_change)
        self.tense_combo = self.add_combo(pulldown_layout, "Tense", ["Past Tense", "Present Tense", "Custom..."], self.controller.handle_tense_change)
        self.toolbar.addWidget(pulldown_widget)

    def add_action(self, name, icon_path, tooltip, callback, checkable=False):
        action = QAction(self.controller.get_tinted_icon(icon_path, self.tint_color), "", self)
        action.setToolTip(tooltip)
        action.setCheckable(checkable)
        action.triggered.connect(callback)
        self.toolbar.addAction(action)
        setattr(self, f"{name}_action", action)
        return action

    def add_combo(self, layout, label_text, items, callback):
        layout.addWidget(QLabel(f"{label_text}:"))
        combo = QComboBox()
        combo.addItems(items)
        combo.currentIndexChanged.connect(callback)
        layout.addWidget(combo)
        return combo

    def setup_editor(self):
        self.editor.setPlaceholderText("Select a node to edit its content...")
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.controller.show_editor_context_menu)
        self.editor.setStyleSheet("border: 1px solid #ccc; padding: 2px;")
        self.editor.textChanged.connect(self.controller.on_editor_text_changed)

    def update_tint(self, tint_color):
        """Update icon tints when theme changes."""
        self.tint_color = tint_color
        for action in ["bold", "italic", "underline", "tts", "align_left", "align_center", "align_right", "manual_save", "oh_shit", "analysis_editor"]:
            getattr(self, f"{action}_action").setIcon(self.controller.get_tinted_icon(f"assets/icons/{action.replace('_', '-')}.svg", tint_color))
