import json
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton, 
    QHBoxLayout, QComboBox, QSpinBox, QGroupBox, QFormLayout,
    QMessageBox, QWidget, QScrollArea
)
from PyQt5.QtCore import Qt
from theme_manager import ThemeManager  # Importing our theme manager module

SETTINGS_FILE = "settings.json"

class ProviderConfigWidget(QWidget):
    """Widget for configuring a single provider."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        
        # Configuration name
        self.name_edit = QLineEdit()
        layout.addRow("Configuration Name:", self.name_edit)
        
        # Provider selection
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Local", "OpenAI", "OpenRouter", "TogetherAI", "Custom"])
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        layout.addRow("Provider:", self.provider_combo)
        
        # Endpoint URL
        self.endpoint_edit = QLineEdit()
        layout.addRow("Endpoint URL:", self.endpoint_edit)

        # Model
        self.model_edit = QLineEdit()
        layout.addRow("Model:", self.model_edit)

        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("API Key:", self.api_key_edit)
        
        # Request timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 300)
        self.timeout_spin.setValue(60)
        layout.addRow("Timeout (seconds):", self.timeout_spin)
        
        # Delete button
        self.delete_button = QPushButton("Delete Configuration")
        self.delete_button.setStyleSheet("color: red;")
        layout.addRow("", self.delete_button)

        # Initially set default endpoint based on provider
        self.on_provider_changed(self.provider_combo.currentText())

    def on_provider_changed(self, provider):
        """Update endpoint URL when provider changes."""
        if provider == "Local":
            self.endpoint_edit.setText("http://localhost:1234/v1/chat/completions")
        elif provider == "OpenAI":
            self.endpoint_edit.setText("https://api.openai.com/v1/chat/completions")
        elif provider == "OpenRouter":
            self.endpoint_edit.setText("https://openrouter.ai/api/v1/chat/completions")
        elif provider == "TogetherAI":
            self.endpoint_edit.setText("https://api.together.xyz/v1/chat/completions")
        else:
            self.endpoint_edit.setText("")

    def get_config(self):
        """Get the configuration as a dictionary."""
        return {
            "name": self.name_edit.text().strip(),
            "provider": self.provider_combo.currentText(),
            "endpoint": self.endpoint_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "api_key": self.api_key_edit.text().strip(),
            "timeout": self.timeout_spin.value()
        }

    def set_config(self, config):
        """Set the configuration from a dictionary."""
        self.name_edit.setText(config.get("name", ""))
        self.provider_combo.setCurrentText(config.get("provider", "Local"))
        self.endpoint_edit.setText(config.get("endpoint", ""))
        self.model_edit.setText(config.get("model", ""))
        self.api_key_edit.setText(config.get("api_key", ""))
        self.timeout_spin.setValue(config.get("timeout", 60))

class OptionsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options")
        self.resize(600, 800)
        self.provider_configs = []  # List to store provider config widgets
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.layout = QVBoxLayout(scroll_widget)
        
        # Appearance Settings Group - Moved to the top for prominence
        appearance_group = QGroupBox("Appearance Settings")
        appearance_layout = QVBoxLayout()
        self.theme_label = QLabel("Select Theme:")
        appearance_layout.addWidget(self.theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(ThemeManager.list_themes())
        appearance_layout.addWidget(self.theme_combo)
        appearance_group.setLayout(appearance_layout)
        self.layout.addWidget(appearance_group)
        
        # General Settings Group
        general_group = QGroupBox("General Settings")
        general_layout = QVBoxLayout()
        self.tts_speed_checkbox = QCheckBox("Enable fast TTS")
        general_layout.addWidget(self.tts_speed_checkbox)
        
        # Auto-save toggle
        self.autosave_checkbox = QCheckBox("Enable Auto-Save")
        general_layout.addWidget(self.autosave_checkbox)
        general_group.setLayout(general_layout)
        self.layout.addWidget(general_group)
        
        # Provider Configurations Group
        providers_group = QGroupBox("Provider Configurations")
        self.providers_layout = QVBoxLayout()
        
        # Active configuration selector
        active_layout = QHBoxLayout()
        self.active_config_combo = QComboBox()
        active_layout.addWidget(QLabel("Active Configuration:"))
        active_layout.addWidget(self.active_config_combo)
        self.providers_layout.addLayout(active_layout)
        
        # Add New Configuration button
        add_config_btn = QPushButton("Add New Configuration")
        add_config_btn.clicked.connect(self.add_provider_config)
        self.providers_layout.addWidget(add_config_btn)
        
        providers_group.setLayout(self.providers_layout)
        self.layout.addWidget(providers_group)
        
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        save_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def add_provider_config(self, config=None):
        """Add a new provider configuration widget."""
        config_widget = ProviderConfigWidget()
        if config:
            config_widget.set_config(config)
        
        # Connect delete button
        config_widget.delete_button.clicked.connect(lambda: self.remove_provider_config(config_widget))
        
        # Add to layout and list
        self.provider_configs.append(config_widget)
        self.providers_layout.insertWidget(self.providers_layout.count() - 1, config_widget)
        
        # Update active config combo
        self.update_active_config_combo()

    def remove_provider_config(self, config_widget):
        """Remove a provider configuration widget."""
        self.provider_configs.remove(config_widget)
        config_widget.deleteLater()
        self.update_active_config_combo()

    def update_active_config_combo(self):
        """Update the active configuration combo box."""
        current_text = self.active_config_combo.currentText()
        self.active_config_combo.clear()
        
        for config in self.provider_configs:
            name = config.name_edit.text().strip()
            if name:
                self.active_config_combo.addItem(name)
        
        if current_text and self.active_config_combo.findText(current_text) >= 0:
            self.active_config_combo.setCurrentText(current_text)

    def load_settings(self):
        """Load settings from file."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                
                # Load appearance setting
                theme = settings.get("theme", "Standard")
                self.theme_combo.setCurrentText(theme)
                
                # Load general settings
                self.tts_speed_checkbox.setChecked(settings.get("tts_fast", False))
                self.autosave_checkbox.setChecked(settings.get("autosave", False))
                
                # Load provider configurations
                provider_configs = settings.get("llm_configs", [])
                active_config = settings.get("active_llm_config", "")
                
                # Create widgets for each configuration
                for config in provider_configs:
                    self.add_provider_config(config)
                
                # Set active configuration
                if active_config:
                    self.active_config_combo.setCurrentText(active_config)
                
            except Exception as e:
                print("Error loading settings:", e)
                QMessageBox.warning(self, "Error", f"Error loading settings: {str(e)}")

    def save_settings(self):
        """Save settings to file and apply the selected theme immediately."""
        # Validate configuration names are unique
        names = []
        for config in self.provider_configs:
            name = config.name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Validation Error", 
                                  "All configurations must have a name.")
                return
            if name in names:
                QMessageBox.warning(self, "Validation Error", 
                                  f"Configuration name '{name}' is used multiple times.")
                return
            names.append(name)
        
        # Build settings dictionary
        settings = {
            "theme": self.theme_combo.currentText(),
            "tts_fast": self.tts_speed_checkbox.isChecked(),
            "autosave": self.autosave_checkbox.isChecked(),
            "llm_configs": [config.get_config() for config in self.provider_configs],
            "active_llm_config": self.active_config_combo.currentText()
        }
        
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            # Apply the selected theme immediately
            ThemeManager.apply_to_app(self.theme_combo.currentText())
            self.accept()
            QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")
        except Exception as e:
            print("Error saving settings:", e)
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")


# For testing standalone
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    window = OptionsWindow()
    window.show()
    sys.exit(app.exec_())
