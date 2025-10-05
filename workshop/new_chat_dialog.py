import json
import os
import re
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QRadioButton, QComboBox, QTextEdit, QPushButton, QMessageBox, QFormLayout, QLabel
from PyQt5.QtCore import Qt
from compendium.compendium_manager import CompendiumManager
from settings.settings_manager import WWSettingsManager
from gettext import gettext as _

class CustomPOVDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Custom Roleplay Character"))
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(_("Enter character name"))
        form_layout.addRow(_("Name:"), self.name_input)
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(_("(Optional) Enter details for new compendium entry..."))
        self.description_input.setMinimumHeight(100)
        form_layout.addRow(_("Description:"), self.description_input)
        layout.addLayout(form_layout)
        buttons = QHBoxLayout()
        self.ok_button = QPushButton(_("OK"))
        self.cancel_button = QPushButton(_("Cancel"))
        buttons.addWidget(self.ok_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.ok_button.clicked.connect(self.ok_button_pressed)
        self.cancel_button.clicked.connect(self.reject)

    def ok_button_pressed(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, _("Custom Roleplay Character"), _("Character name cannot be empty."))
            return
        self.accept()

    def get_data(self):
        return self.name_input.text().strip(), self.description_input.toPlainText().strip()

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
        self.pov_combo = QComboBox()
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
        self.populate_pov_combo()

    def update_pov_enabled(self, checked):
        self.pov_combo.setEnabled(checked)

    def set_default_name(self):
        names = self.parent().controller.model.conversation_manager.get_conversation_names()
        existing_numbers = [int(m.group(1)) for name in names if (m := re.match(rf'^{re.escape(self.project_name)} (\d+)$', name))]
        number = max(existing_numbers, default=0) + 1
        default_name = f"{self.project_name} {number}"
        self.name_input.setText(default_name)

    def populate_pov_combo(self):
        characters = self.get_characters()
        if not characters:
            characters = ["Alice", "Bob", "Charlie"]
        characters.append(_("Custom..."))
        self.pov_combo.addItems(characters)

    # Move this into CompendiumManager
    def get_characters(self):
        character_dicts = self.compendium_manager.get_category("Characters")
        characters = [d['name'] for d in character_dicts]
        characters.sort()
        return characters

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
            if pov == _("Custom..."):
                custom_dialog = CustomPOVDialog(self)
                if custom_dialog.exec_() == QDialog.Accepted:
                    char_name, desc = custom_dialog.get_data()
#                    if self.add_to_compendium(char_name, desc):
#                        self.parent().parent().enhanced_window.compendium_updated.emit()
                    self._pov = char_name
#                    else:
#                        return
                else:
                    return
        self.accept()

    def add_to_compendium(self, name, desc):
        project_name = self.project_name
        compendium_path = os.path.expanduser(f"~/Documents/Writingway/projects/{project_name}/compendium.json")
        try:
            data = {}
            if os.path.exists(compendium_path):
                with open(compendium_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            categories = data.get("categories", [])
            characters_cat = None
            for cat in categories:
                if cat["name"].lower() == "characters":
                    characters_cat = cat
                    break
            if not characters_cat:
                characters_cat = {"name": "Characters", "entries": []}
                categories.append(characters_cat)
            for entry in characters_cat["entries"]:
                if entry["name"] == name:
                    QMessageBox.warning(self, _("Error"), _("Character already exists."))
                    return False
            characters_cat["entries"].append({"name": name, "description": desc})
            data["categories"] = categories
            with open(compendium_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self.parent().parent().update_pov_character_dropdown()
            return True
        except Exception as e:
            print(f"Error adding to compendium: {e}")
            return False

    def get_name(self):
        return self.name_input.text().strip()

    def get_selected_mode(self):
        return "Role Play" if self.role_play_radio.isChecked() else "Writing Coach"

    def get_pov(self):
        if self.role_play_radio.isChecked():
            return getattr(self, '_pov', self.pov_combo.currentText())
        return None