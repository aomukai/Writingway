#!/usr/bin/env python3
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QHBoxLayout, QPushButton, QTextEdit, QComboBox, QLabel, QCheckBox, QSizePolicy
from PyQt5.QtGui import QColor
from .focus_mode import PlainTextEdit
from .context_panel import ContextPanel

class BottomStack(QWidget):
    """Stacked widget for summary and LLM panels."""
    def __init__(self, controller, model, tint_color=QColor("black")):
        super().__init__()
        self.controller = controller
        self.model = model
        self.tint_color = tint_color
        self.stack = QStackedWidget()
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
        layout.addStretch()
        self.create_summary_button = QPushButton("Create Summary")
        self.create_summary_button.clicked.connect(self.controller.create_summary)
        self.save_summary_button = QPushButton("Save Summary")
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
        self.preview_text.setPlaceholderText("LLM output preview will appear here...")
        preview_buttons = QHBoxLayout()
        self.apply_button = QPushButton()
        self.apply_button.setIcon(self.controller.get_tinted_icon("assets/icons/save.svg", self.tint_color))
        self.apply_button.setToolTip("Appends the LLM's output to your current scene")
        self.apply_button.clicked.connect(self.controller.apply_preview)
        self.include_prompt_checkbox = QCheckBox("Include Action Beats")
        self.include_prompt_checkbox.setToolTip("Include the text from the Action Beats field in the scene text")
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
        self.prompt_input.setPlaceholderText("Enter your action beats here...")
        self.prompt_input.setFixedHeight(100)
        self.prompt_input.textChanged.connect(self.controller.on_prompt_input_text_changed)
        left_layout.addWidget(self.prompt_input)

        buttons_layout = QHBoxLayout()
        self.prompt_dropdown = QComboBox()
        self.prompt_dropdown.setToolTip("Select a prose prompt")
        self.prompt_dropdown.addItem("Select Prose Prompt")
        self.prompt_dropdown.currentIndexChanged.connect(self.controller.prompt_dropdown_changed)
        buttons_layout.addWidget(self.prompt_dropdown)

        self.preview_button = QPushButton()
        self.preview_button.setIcon(self.controller.get_tinted_icon("assets/icons/eye.svg", self.tint_color))
        self.preview_button.setToolTip("Preview the final prompt")
        self.preview_button.clicked.connect(self.controller.preview_prompt)
        buttons_layout.addWidget(self.preview_button)

        self.send_button = QPushButton()
        self.send_button.setIcon(self.controller.get_tinted_icon("assets/icons/send.svg", self.tint_color))
        self.send_button.setToolTip("Sends the action beats to the LLM")
        self.send_button.clicked.connect(self.controller.send_prompt)
        buttons_layout.addWidget(self.send_button)

        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.controller.get_tinted_icon("assets/icons/x-octagon.svg", self.tint_color))
        self.stop_button.setToolTip("Stop the LLM processing")
        self.stop_button.clicked.connect(self.controller.stop_llm)
        buttons_layout.addWidget(self.stop_button)

        self.context_toggle_button = QPushButton()
        self.context_toggle_button.setIcon(self.controller.get_tinted_icon("assets/icons/book.svg", self.tint_color))
        self.context_toggle_button.setToolTip("Toggle context panel")
        self.context_toggle_button.setCheckable(True)
        self.context_toggle_button.clicked.connect(self.controller.toggle_context_panel)
        buttons_layout.addWidget(self.context_toggle_button)

        self.model_indicator = QLabel("")
        self.model_indicator.setStyleSheet("font-weight: bold; padding-left: 10px;")
        self.model_indicator.setToolTip("Selected prompt's model")
        buttons_layout.addWidget(self.model_indicator)
        buttons_layout.addStretch()
        left_layout.addLayout(buttons_layout)

        self.context_panel = ContextPanel(self.model.structure, self.model.project_name)
        self.context_panel.setVisible(False)  # Start with context panel hidden
        left_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        action_layout.addWidget(left_container, stretch=2)
        action_layout.addWidget(self.context_panel, stretch=1)

        layout.addWidget(self.preview_text)
        layout.addLayout(preview_buttons)
        layout.addLayout(action_layout)
        return panel

    def update_tint(self, tint_color):
        """Update icon tints when theme changes."""
        self.tint_color = tint_color
        self.apply_button.setIcon(self.controller.get_tinted_icon("assets/icons/save.svg", tint_color))
        self.send_button.setIcon(self.controller.get_tinted_icon("assets/icons/send.svg", tint_color))
        self.stop_button.setIcon(self.controller.get_tinted_icon("assets/icons/x-octagon.svg", tint_color))
        self.context_toggle_button.setIcon(self.controller.get_tinted_icon(
            "assets/icons/book-open.svg" if self.context_panel.isVisible() else "assets/icons/book.svg", tint_color))
    
    def update_visibility(self, is_visible):
        """Control visibility of the bottom stack without affecting layout"""
        self.setVisible(is_visible)
        # Make sure the context panel starts hidden even when the bottom stack becomes visible
        if hasattr(self, 'context_panel') and is_visible:
            # Only apply the controller's LLM availability to the toggle button state, not directly to visibility
            self.context_toggle_button.setEnabled(self.controller.llm_available)
            # The context panel should remain hidden unless explicitly toggled
            # Do not modify context_panel visibility here