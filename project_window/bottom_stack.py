#!/usr/bin/env python3
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout, QPushButton, 
                            QTextEdit, QComboBox, QCheckBox, QSizePolicy,
                            QFormLayout, QSplitter)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from settings.theme_manager import ThemeManager
from .focus_mode import PlainTextEdit
from compendium.context_panel import ContextPanel
from .summary_controller import SummaryController
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
        self.scene_editor = controller.scene_editor  # Access editor via controller
        self.summary_controller = SummaryController(
            SummaryModel(model.project_name),
            self,
            controller.project_tree
        )
        self.summary_controller.status_updated.connect(self._update_status)
        self.init_ui()

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

        # LLM Settings Group
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
        self.create_summary_button = QPushButton(_("Create Summary"))
        self.create_summary_button.clicked.connect(self.summary_controller.create_summary)
        self.save_summary_button = QPushButton(_("Save Summary"))
        self.save_summary_button.clicked.connect(self.controller.save_summary)
        layout.addWidget(self.create_summary_button)
        layout.addWidget(self.save_summary_button)
        layout.addStretch()

        return panel

    def create_llm_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Preview Area
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

        # Action Beats Area
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

        # LLM Settings Group
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

        # POV, Character, Tense Pulldowns
        buttons_layout.addStretch()  # Push combos to the right
        pulldown_widget = QWidget()
        pulldown_layout = QFormLayout(pulldown_widget)
        pulldown_layout.setContentsMargins(0, 0, 20, 0)
        # Tell combo boxes to expand to the same size
        pulldown_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.pov_combo = self.add_combo(pulldown_layout, _("POV"), [_("First Person"), _("Third Person Limited"), _("Omniscient"), _("Custom...")], self.controller.handle_pov_change)
        self.pov_character_combo = self.add_combo(pulldown_layout, _("POV Character"), ["Alice", "Bob", "Charlie", _("Custom...")], self.controller.handle_pov_character_change)
        self.tense_combo = self.add_combo(pulldown_layout, _("Tense"), [_("Past Tense"), _("Present Tense"), _("Custom...")], self.controller.handle_tense_change)
        buttons_layout.addWidget(pulldown_widget)

        left_layout.addLayout(buttons_layout)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_container)

        self.context_panel = ContextPanel(self.model.structure, self.model.project_name, self.controller)
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
        """Update icon tints when theme changes."""
        self.tint_color = tint_color
        self.apply_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/save.svg", tint_color))
        self.send_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/send.svg", tint_color))
        self.stop_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/x-octagon.svg", tint_color))
        self.context_toggle_button.setIcon(ThemeManager.get_tinted_icon(
            "assets/icons/book-open.svg" if self.context_panel.isVisible() else "assets/icons/book.svg", tint_color))
        # Update combo tooltips if needed
        if self.pov_combo:
            self.pov_combo.setToolTip(_("POV: {}").format(self.model.settings.get('global_pov', 'Third Person')))
        if self.pov_character_combo:
            self.pov_character_combo.setToolTip(_("POV Character: {}").format(self.model.settings.get('global_pov_character', 'Character')))
        if self.tense_combo:
            self.tense_combo.setToolTip(_("Tense: {}").format(self.model.settings.get('global_tense', 'Present Tense')))

    def _update_status(self, message):
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
    
<<<<<<< HEAD
    def summary_prompt_changed(self):
        """Handle changes in the summary prompt dropdown."""
        selected_prompt = self.summary_prompt_dropdown.currentText()
        if selected_prompt == "Select Summary Prompt":
            self.summary_model_combo.clear()
            self.summary_model_combo.addItem("Default Model")
            return

        prompts = self._load_summary_prompts()
        self.summary_model_combo.clear()

        for prompt in prompts:
            if prompt["name"] == selected_prompt:
                llm = WWApiAggregator.aggregator.get_provider(prompt["provider"])
                if llm:
                    self.summary_model_combo.addItems(llm.get_available_models())
                    self.summary_model_combo.setCurrentText(prompt["model"])
                else:
                    self.summary_model_combo.addItem(prompt["model"])
                break

    def _load_summary_prompts(self):
        """
        Load summary prompts from the project's prompts JSON file.

        Returns:
            list: A list of summary prompt dictionaries, or an empty list if loading fails.
        """
        prompts_file = WWSettingsManager.get_project_path(file="prompts.json")
        if not os.path.exists(prompts_file):
            return []

        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("Summary", [])
        except Exception as e:
            print(f"Error loading summary prompts: {e}")
            return []

=======
    def preview_prompt(self):
        additional_vars = self.get_additional_vars()
        prompt_config = self.prose_prompt_panel.get_prompt()
        action_beats = self.prompt_input.toPlainText().strip()
        current_scene_text = self.scene_editor.editor.toPlainText().strip() if self.controller.project_tree.tree.currentItem() and self.controller.project_tree.get_item_level(self.controller.project_tree.tree.currentItem()) >= 2 else None
        extra_context = self.context_panel.get_selected_context_text()
        
        # Show the preview dialog
        dialog = PromptPreviewDialog(
            self.controller,
            prompt_config=prompt_config, 
            user_input=action_beats, 
            additional_vars=additional_vars, 
            current_scene_text=current_scene_text, 
            extra_context=extra_context)
        dialog.exec_()
>>>>>>> 55d0572421381460816e7174fb7d9d8eb97e1f4f
