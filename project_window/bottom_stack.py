#!/usr/bin/env python3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout, QPushButton, 
                            QTextEdit, QComboBox, QSizePolicy,
                            QFormLayout, QSplitter, QCheckBox)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QVariant
from settings.theme_manager import ThemeManager
from .focus_mode import PlainTextEdit
from compendium.context_panel import ContextPanel
from .summary_controller import SummaryController, SummaryMode
from .summary_model import SummaryModel
from muse.prompt_panel import PromptPanel
from muse.prompt_preview_dialog import PromptPreviewDialog

class BottomStack(QWidget):
    """Stacked widget for summary and LLM panels."""
    def __init__(self, controller, model, tint_color=QColor("black")):
        super().__init__()
        self.controller = controller
        self.model = model
        self.tint_color = tint_color
        self.stack = QStackedWidget()
        self.scene_editor = controller.scene_editor
        self.summary_controller = SummaryController(
            SummaryModel(model.project_name),
            self,
            controller.project_tree
        )
        self.summary_controller.progress_updated.connect(self._update_progress)
        self.init_ui()
        self.project_tree = controller.project_tree
        self.project_tree.tree.currentItemChanged.connect(self._update_summary_mode_visibility)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)
        layout.setContentsMargins(0, 0, 0, 0)

        self.summary_panel = self.create_summary_panel()
        self.llm_panel = self.create_llm_panel()
        self.stack.addWidget(self.summary_panel)
        self.stack.addWidget(self.llm_panel)

    def create_summary_panel(self):
        panel = QWidget()
        layout = QHBoxLayout(panel)

        self.summary_prompt_panel = PromptPanel("Summary")
        self.summary_prompt_panel.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.summary_prompt_panel.setMaximumWidth(300)
        layout.addWidget(self.summary_prompt_panel)

        self.summary_preview_button = QPushButton()
        self.summary_preview_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/eye.svg", self.tint_color))
        self.summary_preview_button.setToolTip(_("Preview the final prompt"))
        self.summary_preview_button.clicked.connect(self.summary_controller.preview_summary)
        layout.addWidget(self.summary_preview_button)
        
        layout.addStretch()
        self.summary_mode_combo = QComboBox()
        # Populate combo box with enum values and localized display names
        for mode in SummaryMode:
            self.summary_mode_combo.addItem(mode.display_name(), QVariant(mode))
        self.summary_mode_combo.setToolTip(_("Select summary generation mode"))
        self.summary_mode_combo.setVisible(False)  # Hidden by default
        layout.addWidget(self.summary_mode_combo)

        self.summary_start_button = QPushButton()
        self.summary_start_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/send.svg", self.tint_color))
        self.summary_start_button.setToolTip(_("Start summary generation"))
        self.summary_start_button.clicked.connect(self._start_summary)
        layout.addWidget(self.summary_start_button)

        self.delete_summary_button = QPushButton()
        self.delete_summary_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/trash.svg", self.tint_color))
        self.delete_summary_button.setToolTip(_("Delete current summary"))
        self.delete_summary_button.clicked.connect(self.summary_controller.delete_summary)
        layout.addWidget(self.delete_summary_button)

        layout.addStretch()
        return panel

    def _start_summary(self):
        """Determine whether to create chapter or act summary based on selection."""
        current_item = self.project_tree.tree.currentItem()
        if not current_item:
            return
        level = self.project_tree.get_item_level(current_item)
        if level == 0:
            self.summary_controller.create_act_summary()
        elif level == 1:
            self.summary_controller.create_chapter_summary()

    def _update_summary_mode_visibility(self, current, previous):
        """Show/hide summary mode combo based on whether an Act is selected."""
        if not current:
            self.summary_mode_combo.setVisible(False)
            return
        level = self.project_tree.get_item_level(current)
        self.summary_mode_combo.setVisible(level == 0)

    def create_llm_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText(_("LLM output preview will appear here..."))
        preview_buttons = QHBoxLayout()
        self.apply_button = QPushButton()
        self.apply_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/save.svg", self.tint_color))
        self.apply_button.setToolTip(_("Appends the LLM's output to your current scene"))
        self.apply_button.clicked.connect(self.controller.apply_preview)
        self.include_prompt_checkbox = QCheckBox(_("Include Action Beats"))
        self.include_prompt_checkbox.setToolTip(_("Include the text from the Action Beats field in the scene text"))
        self.include_prompt_checkbox.setChecked(True)
        preview_buttons.addWidget(self.apply_button)
        preview_buttons.addWidget(self.include_prompt_checkbox)
        preview_buttons.addStretch()

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.prompt_input = PlainTextEdit()
        self.prompt_input.setPlaceholderText(_("Enter your action beats here..."))
        self.prompt_input.setFixedHeight(100)
        self.prompt_input.textChanged.connect(self.controller.on_prompt_input_text_changed)
        left_layout.addWidget(self.prompt_input)

        buttons_layout = QHBoxLayout()
        self.prose_prompt_panel = PromptPanel("Prose")
        self.prose_prompt_panel.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.prose_prompt_panel.setMaximumWidth(300)
        buttons_layout.addWidget(self.prose_prompt_panel)

        self.preview_button = QPushButton()
        self.preview_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/eye.svg", self.tint_color))
        self.preview_button.setToolTip(_("Preview the final prompt"))
        self.preview_button.clicked.connect(self.preview_prompt)
        buttons_layout.addWidget(self.preview_button)

        self.send_button = QPushButton()
        self.send_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/send.svg", self.tint_color))
        self.send_button.setToolTip(_("Sends the action beats to the LLM"))
        self.send_button.clicked.connect(self.controller.send_prompt)
        buttons_layout.addWidget(self.send_button)

        self.stop_button = QPushButton()
        self.stop_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/x-octagon.svg", self.tint_color))
        self.stop_button.setToolTip(_("Stop the LLM processing"))
        self.stop_button.clicked.connect(self.controller.stop_llm)
        buttons_layout.addWidget(self.stop_button)

        self.context_toggle_button = QPushButton()
        self.context_toggle_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/book.svg", self.tint_color))
        self.context_toggle_button.setToolTip(_("Toggle context panel"))
        self.context_toggle_button.setCheckable(True)
        self.context_toggle_button.clicked.connect(self.toggle_context_panel)
        buttons_layout.addWidget(self.context_toggle_button)
        
        # Add Wizard button for Brainstorm Mode
        self.wizard_button = QPushButton()
        self.wizard_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/brainstorm-wizard.svg", self.tint_color))
        self.wizard_button.setToolTip(_("Open Brainstorm Mode"))
        self.wizard_button.clicked.connect(self.open_brainstorm_mode)
        buttons_layout.addWidget(self.wizard_button)

        buttons_layout.addStretch()
        pulldown_widget = QWidget()
        pulldown_layout = QFormLayout(pulldown_widget)
        pulldown_layout.setContentsMargins(0, 0, 20, 0)
        pulldown_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.pov_combo = self.add_combo(pulldown_layout, _("POV"), [_("First Person"), _("Third Person Limited"), _("Omniscient"), _("Custom...")], self.controller.handle_pov_change)
        self.pov_character_combo = self.add_combo(pulldown_layout, _("POV Character"), ["Alice", "Bob", "Charlie", _("Custom...")], self.controller.handle_pov_character_change)
        self.tense_combo = self.add_combo(pulldown_layout, _("Tense"), [_("Past Tense"), _("Present Tense"), _("Custom...")], self.controller.handle_tense_change)
        buttons_layout.addWidget(pulldown_widget)

        left_layout.addLayout(buttons_layout)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_container)

        self.context_panel = ContextPanel(self.model.structure, self.model.project_name, self.controller, enhanced_window=self.controller.enhanced_window)
        self.context_panel.setVisible(False)
        splitter.addWidget(self.context_panel)
        splitter.setSizes([500, 300])

        left_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        action_layout.addWidget(splitter)

        layout.addWidget(self.preview_text)
        layout.addLayout(preview_buttons)
        layout.addLayout(action_layout)
        return panel

    def add_combo(self, layout, label_text, items, callback):
        combo = QComboBox()
        combo.addItems(items)
        combo.currentIndexChanged.connect(callback)
        layout.addRow(f"{label_text}:", combo)
        return combo
    
    def update_tint(self, tint_color):
        self.tint_color = tint_color
        self.apply_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/save.svg", tint_color))
        self.send_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/send.svg", tint_color))
        self.stop_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/x-octagon.svg", tint_color))
        self.context_toggle_button.setIcon(ThemeManager.get_tinted_icon(
            "assets/icons/book-open.svg" if self.context_panel.isVisible() else "assets/icons/book.svg", tint_color))
        self.summary_preview_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/eye.svg", tint_color))
        self.summary_start_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/play-circle.svg", tint_color))
        self.delete_summary_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/trash.svg", tint_color))
        self.wizard_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/brainstorm-wizard.svg", tint_color))
        if self.pov_combo:
            self.pov_combo.setToolTip(_("POV: {}").format(self.model.settings.get('global_pov', 'Third Person')))
        if self.pov_character_combo:
            self.pov_character_combo.setToolTip(_("POV Character: {}").format(self.model.settings.get('global_pov_character', 'Character')))
        if self.tense_combo:
            self.tense_combo.setToolTip(_("Tense: {}").format(self.model.settings.get('global_tense', 'Present Tense')))

    def _update_progress(self, message):
        self.controller.statusBar().showMessage(message, 5000)

    def toggle_context_panel(self):
        context_panel = self.context_panel
        if context_panel.isVisible():
            context_panel.setVisible(False)
            self.context_toggle_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/book.svg"))
        else:
            context_panel.build_project_tree()
            context_panel.build_compendium_tree()
            context_panel.setVisible(True)
            self.context_toggle_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/book-open.svg"))

    def get_additional_vars(self):
        return {
            "pov": self.pov_combo.currentText(),
            "pov_character": self.pov_character_combo.currentText(),
            "tense": self.tense_combo.currentText()
        }
    
    def preview_prompt(self):
        additional_vars = self.get_additional_vars()
        prompt_config = self.prose_prompt_panel.get_prompt()
        action_beats = self.prompt_input.toPlainText().strip()
        current_scene_text = self.scene_editor.editor.toPlainText().strip() if self.controller.project_tree.tree.currentItem() and self.controller.project_tree.get_item_level(self.controller.project_tree.tree.currentItem()) >= 2 else None
        extra_context = self.context_panel.get_selected_context_text()
        
        dialog = PromptPreviewDialog(
            self.controller,
            prompt_config=prompt_config,
            user_input=action_beats,
            additional_vars=additional_vars,
            current_scene_text=current_scene_text,
            extra_context=extra_context)
        dialog.exec_()
        
    def open_brainstorm_mode(self):
        """Open the Brainstorm Mode dialog."""
        action_beats = self.prompt_input.toPlainText().strip()
        if not action_beats:
            # Show a warning message
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self.controller, _("Brainstorm Mode"), _("Please enter some action beats before opening Brainstorm Mode."))
            return
        
        # Import here to avoid circular imports
        from muse.brainstorm_dialog import BrainstormModeDialog
        dialog = BrainstormModeDialog(action_beats, self.controller)
        dialog.exec_()