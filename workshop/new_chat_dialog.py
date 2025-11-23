import json
import os
import re
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QRadioButton, QComboBox, QTextEdit, QPushButton, QMessageBox, QFormLayout, QLabel
from PyQt5.QtCore import Qt
from compendium.compendium_manager import CompendiumManager
from compendium.pov_combobox import POVComboBox
from settings.settings_manager import WWSettingsManager
from gettext import gettext as _

class NewChatDialog(QDialog):
    def __init__(self, project_name:str, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.compendium_manager = CompendiumManager(project_name)
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(_("New Chat Mode"))
        layout = QVBoxLayout(self)
        
        # Centered chat name input
        name_layout = QHBoxLayout()
        self.name_label = QLabel(_("Chat Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(_("Enter chat name"))
        self.name_input.setAlignment(Qt.AlignCenter)
        name_layout.addStretch()
        name_layout.addWidget(self.name_label)
        name_layout.addWidget(self.name_input)
        name_layout.addStretch()
        layout.addLayout(name_layout)
        
        # Mode selection
        mode_layout = QVBoxLayout()
        self.writing_coach_radio = QRadioButton(_("Writing Coach"))
        self.writing_coach_radio.setChecked(True)
        mode_layout.addWidget(self.writing_coach_radio)
        
        # Role Play radio button with inline POV combo
        role_play_layout = QHBoxLayout()
        self.role_play_radio = QRadioButton(_("Role Play"))
        self.pov_combo = POVComboBox(self.project_name)
        self.pov_combo.setEnabled(False)
        role_play_layout.addWidget(self.role_play_radio)
        role_play_layout.addWidget(self.pov_combo)
        role_play_layout.addStretch()
        mode_layout.addLayout(role_play_layout)
        
        layout.addLayout(mode_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton(_("OK"))
        self.ok_button.clicked.connect(self.custom_accept)
        self.cancel_button = QPushButton(_("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.role_play_radio.toggled.connect(self.update_pov_enabled)
        self.set_default_name()

    def update_pov_enabled(self, checked):
        self.pov_combo.setEnabled(checked)

    def set_default_name(self):
        names = self.parent().controller.model.conversation_manager.get_conversation_names()
        existing_numbers = [int(m.group(1)) for name in names if (m := re.match(rf'^{re.escape(self.project_name)} (\d+)$', name))]
        number = max(existing_numbers, default=0) + 1
        default_name = f"{self.project_name} {number}"
        self.name_input.setText(default_name)

    def custom_accept(self):
        name = self.get_name()
        if not name:
            QMessageBox.warning(self, _("New Chat"), _("Chat name cannot be empty."))
            return
        if name in self.parent().controller.model.conversation_manager.get_conversation_names():
            QMessageBox.warning(self, _("New Chat"), _("Chat name already exists."))
            return
        if self.role_play_radio.isChecked():
            pov = self.pov_combo.currentText()
        self.accept()

    def get_name(self):
        return self.name_input.text().strip()

    def get_selected_mode(self):
        return "Role Play" if self.role_play_radio.isChecked() else "Writing Coach"

    def get_pov(self):
        if self.role_play_radio.isChecked():
            return getattr(self, '_pov', self.pov_combo.currentText())
        return None