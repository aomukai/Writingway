#!/usr/bin/env python3
from PyQt5.QtWidgets import QToolBar, QAction, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QColor

class GlobalToolbar(QWidget):
    """Global actions toolbar at the top of the window."""
    def __init__(self, controller, tint_color=QColor("black")):
        super().__init__()
        self.controller = controller  # Reference to ProjectWindow for callbacks
        self.tint_color = tint_color
        self.toolbar = QToolBar("Global Actions")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.setContentsMargins(0, 0, 0, 0)

        self.compendium_action = self.add_action("assets/icons/book.svg", "Toggle Compendium", self.controller.open_compendium)
        self.prompt_options_action = self.add_action("assets/icons/settings.svg", "Prompt Options", self.controller.open_prompts_window)
        self.workshop_action = self.add_action("assets/icons/message-square.svg", "Workshop Chat", self.controller.open_workshop)
        self.focus_mode_action = self.add_action("assets/icons/maximize-2.svg", "Focus Mode", self.controller.open_focus_mode)
        # Update visibility based on LLM availability
        self.update_visibility()

    def add_action(self, icon_path, tooltip, callback):
        action = QAction(self.controller.get_tinted_icon(icon_path, self.tint_color), "", self)
        action.setToolTip(tooltip)
        action.triggered.connect(callback)
        self.toolbar.addAction(action)
        return action

    def update_tint(self, tint_color):
        """Update icon tints when theme changes."""
        self.tint_color = tint_color
        self.compendium_action.setIcon(self.controller.get_tinted_icon("assets/icons/book.svg", tint_color))
        self.prompt_options_action.setIcon(self.controller.get_tinted_icon("assets/icons/settings.svg", tint_color))
        self.workshop_action.setIcon(self.controller.get_tinted_icon("assets/icons/message-square.svg", tint_color))
        self.focus_mode_action.setIcon(self.controller.get_tinted_icon("assets/icons/maximize-2.svg", tint_color))

    def update_visibility(self):
        """Update visibility of actions that depend on LLM availability."""
        # If LLM is available, show prompt_options and workshop; otherwise hide them.
        self.prompt_options_action.setVisible(self.controller.llm_available)
        self.workshop_action.setVisible(self.controller.llm_available)
