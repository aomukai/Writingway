import sys
import copy
import os
from PyQt5.QtWidgets import (
    QApplication, QDialog, QTabWidget, QVBoxLayout,
    QCheckBox, QComboBox, QLabel, QPushButton,
    QFormLayout, QColorDialog, QHBoxLayout, QSpinBox,
    QMessageBox, QListWidget, QListWidgetItem,
    QGroupBox, QWidget
)
from PyQt5.QtGui import QIcon, QPalette, QColor, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QSettings

from .translation_manager import LANGUAGES
from .theme_manager import ThemeManager
from .llm_api_aggregator import WWApiAggregator
from .settings_manager import WWSettingsManager
from .provider_dialog import ProviderDialog

class SettingsDialog(QDialog):
    settings_saved = pyqtSignal()
    
    def __init__(self, translation_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Preferences"))
        self.resize(500, 500)
        self.setWindowIcon(QIcon("assets/icon.png"))

        self.general_settings = WWSettingsManager.get_general_settings()
        self.appearance_settings = WWSettingsManager.get_appearance_settings()
        self.llm_configs = WWSettingsManager.get_llm_configs()
        self.default_provider = WWSettingsManager.get_active_llm_name()
        self.translation_manager = translation_manager
        
        self.original_llm_configs = copy.deepcopy(self.llm_configs)

        self.init_ui()
        self.load_values_from_settings()
        self.read_settings()

        self.unsaved_changes = False

    def init_ui(self):
        self.tabs = QTabWidget()

        self.general_tab = QWidget()
        self.appearance_tab = QWidget()
        self.provider_tab = QWidget()

        self.tabs.addTab(self.general_tab, _("General"))
        self.tabs.addTab(self.appearance_tab, _("Appearance"))
        self.tabs.addTab(self.provider_tab, _("Providers"))

        self.init_general_tab()
        self.init_appearance_tab()
        self.init_provider_tab()

        self.button_box = QHBoxLayout()
        self.save_button = QPushButton(_("Save"))
        self.save_button.clicked.connect(self.save_settings_to_file)
        self.cancel_button = QPushButton(_("Close"))
        self.cancel_button.clicked.connect(self.check_unsaved_changes)
        self.button_box.addWidget(self.save_button)
        self.button_box.addWidget(self.cancel_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        main_layout.addLayout(self.button_box)

        self.setLayout(main_layout)

    def init_general_tab(self):
        layout = QFormLayout()

        self.fast_tts_checkbox = QCheckBox(_("Fast Text to Speech"))
        self.fast_tts_checkbox.stateChanged.connect(self.mark_unsaved_changes)
        layout.addRow(self.fast_tts_checkbox)

        self.enable_autosave_checkbox = QCheckBox(_("Enable Auto-Save"))
        self.enable_autosave_checkbox.stateChanged.connect(self.mark_unsaved_changes)
        layout.addRow(self.enable_autosave_checkbox)
        
        self.show_quote_checkbox = QCheckBox(_("Show Random Quotes"))
        self.show_quote_checkbox.stateChanged.connect(self.mark_unsaved_changes)
        layout.addRow(self.show_quote_checkbox)

        self.enable_debug_logging_checkbox = QCheckBox(_("Enable Debug Logging"))
        self.enable_debug_logging_checkbox.stateChanged.connect(self.mark_unsaved_changes)
        layout.addRow(self.enable_debug_logging_checkbox)

        self.language_combobox = QComboBox()
        self.language_combobox.setMinimumWidth(80)
        self.language_combobox.addItems(LANGUAGES)
        self.language_combobox.currentIndexChanged.connect(self.language_changed)
        self.language_combobox.currentIndexChanged.connect(self.mark_unsaved_changes)
        self.language_label = QLabel(_("Language"))
        layout.addRow(self.language_label, self.language_combobox)

        self.general_tab.setLayout(layout)

    def init_appearance_tab(self):
        layout = QFormLayout()

        self.theme_combobox = QComboBox()
        self.theme_combobox.addItems(ThemeManager.list_themes())
        self.theme_combobox.currentIndexChanged.connect(self.change_theme)
        self.theme_combobox.currentIndexChanged.connect(self.mark_unsaved_changes)
        self.theme_label = QLabel(_("Theme"))
        layout.addRow(self.theme_label, self.theme_combobox)

        self.background_color_button = QPushButton(_("Background Color"))
        self.background_color_button.clicked.connect(self.choose_background_color)
        self.background_color_label = QLabel()
        self.background_color_label.setAutoFillBackground(True)
        self.set_background_color_label(self.appearance_settings["background_color"])
        hbox = QHBoxLayout()
        hbox.addWidget(self.background_color_button)
        hbox.addWidget(self.background_color_label)
        layout.addRow(hbox)

        self.text_size_spinbox = QSpinBox()
        self.text_size_spinbox.setRange(8, 24)
        self.text_size_spinbox.valueChanged.connect(self.update_font_size)
        self.text_size_spinbox.valueChanged.connect(self.mark_unsaved_changes)
        self.text_size_label = QLabel(_("Text Size"))
        layout.addRow(self.text_size_label, self.text_size_spinbox)

        self.sample_group_box = QGroupBox()
        sample_layout = QHBoxLayout()
        sample_layout.setAlignment(Qt.AlignCenter)
        self.sample_text_label = QLabel(_("Sample Text"))
        sample_layout.addWidget(self.sample_text_label)
        self.sample_group_box.setLayout(sample_layout)
        layout.addRow(self.sample_group_box)

        self.appearance_tab.setLayout(layout)

    def init_provider_tab(self):
        layout = QVBoxLayout()
        
        self.providers_group = QGroupBox(_("Configured Providers"))
        providers_layout = QVBoxLayout()
        
        self.providers_list = QListWidget()
        self.providers_list.setMinimumHeight(200)
        self.providers_list.itemClicked.connect(self.provider_item_clicked)
        providers_layout.addWidget(self.providers_list)
        
        buttons_layout = QHBoxLayout()
        self.new_provider_button = QPushButton(_("New Provider"))
        self.new_provider_button.clicked.connect(self.add_new_provider)
        self.edit_provider_button = QPushButton(_("Edit"))
        self.edit_provider_button.clicked.connect(self.edit_selected_provider)
        self.delete_provider_button = QPushButton(_("Delete"))
        self.delete_provider_button.clicked.connect(self.delete_provider)
        
        buttons_layout.addWidget(self.new_provider_button)
        buttons_layout.addWidget(self.edit_provider_button)
        buttons_layout.addWidget(self.delete_provider_button)
        providers_layout.addLayout(buttons_layout)
        
        self.providers_group.setLayout(providers_layout)
        layout.addWidget(self.providers_group)
        
        self.provider_tab.setLayout(layout)
        
        self.edit_provider_button.setEnabled(False)
        self.delete_provider_button.setEnabled(False)

    def populate_providers_list(self):
        """Populate the providers list with configured providers"""
        self.providers_list.clear()
        
        for provider_name, provider_data in self.llm_configs.items():
            item = QListWidgetItem(provider_name)
            if provider_name == self.default_provider:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setData(Qt.UserRole, {"name": provider_name, "is_default": True})
                item.setText(f"{provider_name} ({_('Default Provider')})")
            else:
                item.setData(Qt.UserRole, {"name": provider_name, "is_default": False})
            
            self.providers_list.addItem(item)

    def provider_item_clicked(self, item):
        """Handle provider item selection"""
        self.edit_provider_button.setEnabled(True)
        
        provider_data = item.data(Qt.UserRole)
        provider_name = provider_data["name"]
        is_default_provider = provider_data["is_default"]
        
        self.delete_provider_button.setEnabled(not is_default_provider)

    def add_new_provider(self):
        """Open dialog to add a new provider"""
        default_providers = WWApiAggregator.get_llm_providers()
        self.provider_dialog = ProviderDialog(
            parent=self,
            providers=default_providers
        )
        
        if self.provider_dialog.exec_():
            provider_data = self.provider_dialog.get_provider_data()
            provider_name = provider_data["name"]
            
            if not provider_name:
                QMessageBox.warning(self, _("Warning"), _("Provider name cannot be empty."))
                return
                
            if provider_name in self.llm_configs:
                QMessageBox.warning(self, _("Warning"), _(f"Provider '{provider_name}' already exists."))
                return
                
            self.llm_configs[provider_name] = {
                "provider": provider_data["provider"],
                "endpoint": provider_data["endpoint"] == "Default" and provider_data["endpoint"] or "",
                "model": provider_data["model"],
                "api_key": provider_data["api_key"],
                "timeout": provider_data["timeout"]
            }
            
            if provider_data["is_default"]:
                self.default_provider = provider_name
                
            self.populate_providers_list()
            self.mark_unsaved_changes()

    def edit_selected_provider(self):
        """Open dialog to edit the selected provider"""
        if not self.providers_list.currentItem():
            return
            
        provider_data = self.providers_list.currentItem().data(Qt.UserRole)
        provider_name = provider_data["name"]
        
        if provider_name not in self.llm_configs:
            return
            
        default_providers = WWApiAggregator.get_llm_providers()
        is_default = provider_name == self.default_provider
        
        self.provider_dialog = ProviderDialog(
            parent=self,
            provider_name=provider_name,
            provider_data=self.llm_configs[provider_name],
            providers=default_providers,
            is_default=is_default
        )
        
        if self.provider_dialog.exec_():
            updated_data = self.provider_dialog.get_provider_data()
            
            self.llm_configs[provider_name] = {
                "provider": updated_data["provider"],
                "endpoint": updated_data["endpoint"],
                "model": updated_data["model"],
                "api_key": updated_data["api_key"],
                "timeout": updated_data["timeout"]
            }
            
            if updated_data["is_default"]:
                self.default_provider = provider_name
            elif self.default_provider == provider_name and not updated_data["is_default"]:
                self.default_provider = ""
                
            self.populate_providers_list()
            self.mark_unsaved_changes()

    def set_background_color_label(self, color_code):
        """Sets the background color label's color."""
        palette = self.background_color_label.palette()
        palette.setColor(QPalette.Window, QColor(color_code))
        self.background_color_label.setPalette(palette)
        self.background_color_label.setText(color_code)
        self.background_color_label.update()

    def delete_provider(self):
        """Deletes the currently selected provider."""
        if not self.providers_list.currentItem():
            return
            
        provider_data = self.providers_list.currentItem().data(Qt.UserRole)
        provider_name = provider_data["name"]
        
        if provider_data["is_default"]:
            QMessageBox.warning(self, _("Warning"), _(f"{provider_name} cannot be deleted as it is the default provider."))
            return
            
        reply = QMessageBox.question(
            self, 
            _("Confirm Deletion"),
            _("Are you sure you want to delete the selected provider?"),
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if provider_name in self.llm_configs:
                del self.llm_configs[provider_name]
                
            if self.default_provider == provider_name:
                self.default_provider = ""
                
            self.populate_providers_list()
            self.edit_provider_button.setEnabled(False)
            self.delete_provider_button.setEnabled(False)
            self.mark_unsaved_changes()

    def choose_background_color(self):
        color = QColorDialog.getColor(QColor(self.appearance_settings["background_color"]), self)
        if color.isValid():
            color_code = color.name()
            self.appearance_settings["background_color"] = color_code
            self.set_background_color_label(color_code)
            self.mark_unsaved_changes()

    def language_changed(self, index):
        language = LANGUAGES[index]
        self.general_settings["language"] = language
        self.translation_manager.set_language(language)
        self.update_ui_labels()
        self.mark_unsaved_changes()

    def update_ui_labels(self):
        """Updates all UI labels based on the selected language."""
        self.setWindowTitle(_("Preferences"))
        self.tabs.setTabText(0, _("General"))
        self.tabs.setTabText(1, _("Appearance"))
        self.tabs.setTabText(2, _("Providers"))
        self.fast_tts_checkbox.setText(_("Fast Text to Speech"))
        self.enable_autosave_checkbox.setText(_("Enable Auto-Save"))
        self.show_quote_checkbox.setText(_("Show Random Quotes"))
        self.enable_debug_logging_checkbox.setText(_("Enable Debug Logging"))
        self.language_label.setText(_("Language"))
        self.theme_label.setText(_("Theme"))
        self.background_color_button.setText(_("Background Color"))
        self.text_size_label.setText(_("Text Size"))
        self.providers_group.setTitle(_("Configured Providers"))
        self.sample_text_label.setText(_("Sample Text"))
        
        self.save_button.setText(_("Save"))
        self.cancel_button.setText(_("Close"))
        self.new_provider_button.setText(_("New Provider"))
        self.edit_provider_button.setText(_("Edit"))
        self.delete_provider_button.setText(_("Delete"))
        
        if hasattr(self, 'provider_dialog') and self.provider_dialog.isVisible():
            self.provider_dialog.update_labels()
        
        self.populate_providers_list()

    def load_values_from_settings(self):
        """Loads the settings values into the UI elements."""
        self.fast_tts_checkbox.setChecked(self.general_settings["fast_tts"])
        self.enable_autosave_checkbox.setChecked(self.general_settings["enable_autosave"])
        self.enable_debug_logging_checkbox.setChecked(self.general_settings.get("enable_debug_logging", False))
        index = self.language_combobox.findText(self.general_settings["language"])
        if index >= 0:
            self.language_combobox.setCurrentIndex(index)

        index = self.theme_combobox.findText(self.appearance_settings["theme"])
        if index >= 0:
            self.theme_combobox.setCurrentIndex(index)
        self.text_size_spinbox.setValue(self.appearance_settings["text_size"])
        self.set_background_color_label(self.appearance_settings["background_color"])

        self.populate_providers_list()
        
        self.show_quote_checkbox.setChecked(self.general_settings.get("show_random_quote", False))

    def save_settings_to_file(self):
        """Saves the current UI settings to the JSON file."""
        self.general_settings["fast_tts"] = self.fast_tts_checkbox.isChecked()
        self.general_settings["enable_autosave"] = self.enable_autosave_checkbox.isChecked()
        self.general_settings["show_random_quote"] = self.show_quote_checkbox.isChecked()
        self.general_settings["enable_debug_logging"] = self.enable_debug_logging_checkbox.isChecked()
        self.general_settings["language"] = self.language_combobox.currentText()
        self.appearance_settings["theme"] = self.theme_combobox.currentText()
        self.appearance_settings["text_size"] = self.text_size_spinbox.value()

        deleted_configs = set(self.original_llm_configs.keys()) - set(self.llm_configs.keys())
        for provider_name in deleted_configs:
            success = WWSettingsManager.delete_llm_config(provider_name)
            if not success:
                QMessageBox.warning(self, _("Warning"), _(f"Failed to delete config {provider_name} from settings.json."))

        success = (
            WWSettingsManager.update_general_settings(self.general_settings) and
            WWSettingsManager.update_appearance_settings(self.appearance_settings) and
            WWSettingsManager.update_llm_configs(self.llm_configs, self.default_provider)
        )

        if success:
            self.original_llm_configs = copy.deepcopy(self.llm_configs)
            QMessageBox.information(self, _("Save Result"), _("Settings saved successfully."))
            self.unsaved_changes = False
            self.settings_saved.emit()
        else:
            QMessageBox.warning(self, _("Warning"), _("Failed to save settings."))

    def mark_unsaved_changes(self):
        """Mark that there are unsaved changes."""
        self.unsaved_changes = True

    def check_unsaved_changes(self):
        """Check for unsaved changes and show a warning dialog if there are any."""
        if self.unsaved_changes:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle(_("Unsaved Changes"))
            msg_box.setText(_("You have unsaved changes. Do you want to save them before closing?"))
            save_button = msg_box.addButton(_("Save"), QMessageBox.AcceptRole)
            discard_button = msg_box.addButton(_("Discard"), QMessageBox.DestructiveRole)
            cancel_button = msg_box.addButton(_("Cancel"), QMessageBox.RejectRole)
            msg_box.setDefaultButton(cancel_button)
            msg_box.exec_()

            if msg_box.clickedButton() == save_button:
                self.save_settings_to_file()
                self.close()
            elif msg_box.clickedButton() == discard_button:
                self.close()
            else:
                return
        else:
            self.close()

    def change_theme(self, index):
        """Change the theme based on the selected theme in the combobox."""
        theme_name = self.theme_combobox.itemText(index)
        ThemeManager.apply_to_app(theme_name)

    def update_font_size(self, value):
        """Update the font size for all text UI objects except the TextEdit contents."""
        font = self.font()
        font.setPointSize(value)
        QApplication.instance().setFont(font)
        self.sample_text_label.setFont(font)

    def read_settings(self):
        """Restore window geometry and tab state."""
        settings = QSettings("MyCompany", "WritingwayProject")
        self.restoreGeometry(settings.value("SettingsDialog/geometry", self.saveGeometry()))
        self.tabs.setCurrentIndex(int(settings.value("SettingsDialog/tab_index", 0)))

    def write_settings(self):
        """Save window geometry and tab state."""
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue("SettingsDialog/geometry", self.saveGeometry())
        settings.setValue("SettingsDialog/tab_index", self.tabs.currentIndex())

    def closeEvent(self, event):
        """Save settings when closing the dialog."""
        self.write_settings()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    settings_dialog = SettingsDialog()
    settings_dialog.show()
    sys.exit(app.exec_())