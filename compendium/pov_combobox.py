from PyQt5.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QFormLayout,
    QPushButton, QTextEdit, QLineEdit, QComboBox, QDialog, QMessageBox
)
from .compendium_manager import CompendiumManager, CompendiumEventBus

class POVComboBox(QComboBox):
    def __init__(self, project_name, initial_pov="Character", parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.selected_pov = initial_pov
        self.event_bus = CompendiumEventBus.get_instance()
        self.compendium = CompendiumManager(project_name, event_bus=self.event_bus)
        self.event_bus.add_updated_listener(self.on_compendium_updated)
        self.populate_combo()
        self.set_to_selected_pov()

    def populate_combo(self) -> None:
        self.clear()
        characters = self.compendium.get_characters()
        if not characters:
            characters = ["Alice", "Bob", "Charlie"]
        characters.append(_("Custom..."))
        self.addItems(characters)
        self.currentIndexChanged.connect(self.handle_pov_character_change)

    def handle_pov_character_change(self, index=0):
        value = self.currentText()
        if value == _("Custom..."):
            dialog = CustomPOVDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                name, description = dialog.get_data()

                # Add to compendium triggers a signal that updates the contents of this combo box
                # unless the user tried to enter a name that already exists.
                self.selected_pov = name
                self.add_character_to_compendium(name, description)
                # No need to update dropdown - compendium update took care of it
            else:
                # Revert to previous selection if canceled
                self.set_to_selected_pov()
                return
        else:
            self.selected_pov = value

    def on_compendium_updated(self, project_name):
        if project_name == self.project_name:
            previous_index = self.currentIndex()
            self.blockSignals(True)
            self.clear()
            characters = self.compendium.get_characters()
            if not characters:
                characters = ["Alice", "Bob", "Charlie"]
            characters.append(_("Custom..."))
            self.addItems(characters)
            self.blockSignals(False)
            self.set_to_selected_pov()
            if self.currentIndex() < 0:
                self.setCurrentIndex(min(previous_index, self.count() - 1))

    def set_to_selected_pov(self):
        index = self.findText(self.selected_pov)
        if index >= 0:
            self.blockSignals(True)
            self.setCurrentIndex(index)
            self.blockSignals(False)
        else: # save whatever character is displayed as the selected pov
            value = self.currentText()
            if (value and value != _("Custom...")):
                self.selected_pov = value 

    def add_character_to_compendium(self, name, description):
        try:
            self.compendium.add_character(name, description)
        except Exception as e:
            print(f"Error saving compendium: {e}")
            QMessageBox.warning(self, _("Error"), _("Failed to save compendium: {}").format(str(e)))

class CustomPOVDialog(QDialog):
    """Dialog for entering a custom POV character name and description."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Custom POV Character"))
        self.setModal(True)
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
            QMessageBox.warning(self, _("Custom POV Character"), _("Character name cannot be empty."))
            return
        self.accept()

    def get_data(self):
        return self.name_input.text().strip(), self.description_input.toPlainText().strip()
