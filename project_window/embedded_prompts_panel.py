import sys
import json
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QPushButton, QMenu, QInputDialog, QMessageBox, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QBrush
from muse.prompt_utils import get_prompt_categories, load_prompts, get_default_prompt
from settings.llm_api_aggregator import WWApiAggregator
from settings.settings_manager import WWSettingsManager
from settings.theme_manager import ThemeManager
from settings.provider_info_dialog import ProviderInfoDialog

class EmbeddedPromptsPanel(QWidget):
    """Panel for managing prompts embedded in the main window's sidebar and editor."""
    def __init__(self, project_name, controller, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.controller = controller
        self.prompts_file = WWSettingsManager.get_project_path(file="prompts.json")
        self.backup_file = WWSettingsManager.get_project_path(file="prompts.bak.json")
        self.prompts_data = {}
        self.current_prompt_item = None
        self.selected_model = None
        self.pending_model = None
        self.init_ui()
        self.load_prompts()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Horizontal)

        self.tree_widget = QWidget()
        tree_layout = QVBoxLayout(self.tree_widget)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(_("Prompts"))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_tree_context_menu)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.setIndentation(5)
        tree_layout.addWidget(self.tree)
        self.splitter.addWidget(self.tree_widget)

        self.editor_widget = QWidget()
        right_layout = QVBoxLayout(self.editor_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.editor = QTextEdit()
        right_layout.addWidget(self.editor)

        self.replicate_button = QPushButton(_("Replicate"))
        self.replicate_button.setToolTip(_("This is a read-only default prompt. Create a copy to edit it."))
        self.replicate_button.clicked.connect(self.replicate_prompt)
        self.replicate_button.hide()
        right_layout.addWidget(self.replicate_button)

        self.parameters_panel = QWidget()
        params_layout = QVBoxLayout(self.parameters_panel)

        model_group = QHBoxLayout()
        provider_layout = QVBoxLayout()
        provider_header = QHBoxLayout()
        self.provider_label = QLabel(_("Provider:"))
        provider_info_button = QPushButton()
        provider_info_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/info.svg"))
        provider_info_button.setToolTip(_("Show Model Details"))
        provider_info_button.clicked.connect(self.show_provider_info)
        provider_header.addWidget(self.provider_label)
        provider_header.addWidget(provider_info_button)
        provider_header.addStretch()
        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(200)
        provider_layout.addLayout(provider_header)
        provider_layout.addWidget(self.provider_combo)
        model_group.addLayout(provider_layout)

        model_layout = QVBoxLayout()
        model_header = QHBoxLayout()
        self.model_label = QLabel(_("Model:"))
        self.refresh_button = QPushButton("↻")
        self.refresh_button.setToolTip(_("Refresh model list"))
        self.refresh_button.setMaximumWidth(30)
        self.refresh_button.clicked.connect(self.refresh_models)
        model_header.addWidget(self.model_label)
        model_header.addWidget(self.refresh_button)
        model_header.addStretch()
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(300)
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        model_layout.addLayout(model_header)
        model_layout.addWidget(self.model_combo)
        model_group.addLayout(model_layout)
        params_layout.addLayout(model_group)

        settings_group = QHBoxLayout()
        tokens_layout = QVBoxLayout()
        self.max_tokens_label = QLabel(_("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 2147483647)
        self.max_tokens_spin.setValue(2000)
        tokens_layout.addWidget(self.max_tokens_label)
        tokens_layout.addWidget(self.max_tokens_spin)
        settings_group.addLayout(tokens_layout)

        temp_layout = QVBoxLayout()
        self.temp_label = QLabel(_("Temperature:"))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7)
        temp_layout.addWidget(self.temp_label)
        temp_layout.addWidget(self.temp_spin)
        settings_group.addLayout(temp_layout)
        settings_group.addStretch()
        params_layout.addLayout(settings_group)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: red;")
        self.status_label.hide()
        params_layout.addWidget(self.status_label)

        right_layout.addWidget(self.parameters_panel)
        self.parameters_panel.hide()

        self.splitter.addWidget(self.editor_widget)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter)

        btn_layout = QHBoxLayout()
        self.save_all_button = QPushButton(_("Save All"))
        self.save_all_button.clicked.connect(self.save_prompts)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_all_button)
        layout.addLayout(btn_layout)

        self.update_provider_list()

    def on_model_changed(self, text):
        self.selected_model = text

    def update_provider_list(self):
        self.provider_combo.clear()
        self.llm_configs = WWSettingsManager.get_llm_configs()
        self.active_config = WWSettingsManager.get_active_llm_name()
        for provider, config in self.llm_configs.items():
            display_name = f"{provider} ({config['provider']})"
            self.provider_combo.addItem(display_name, userData=provider)
            if provider == self.active_config:
                self.provider_combo.setCurrentText(display_name)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)

    def on_provider_changed(self, provider_text):
        self.refresh_models(True)

    def refresh_models(self, use_cache=False):
        current_index = self.provider_combo.currentIndex()
        if current_index < 0:
            return
        provider_name = self.provider_combo.itemData(current_index)
        if not use_cache:
            self.model_combo.clear()
            self.model_combo.addItem(_("Loading models..."))
            self.model_combo.setEnabled(False)
            self.refresh_button.setEnabled(False)
            QApplication.processEvents()
        try:
            provider = WWApiAggregator.aggregator.get_provider(provider_name)
            self.on_models_updated(provider.get_available_models(not use_cache), None)
        except Exception as e:
            self.on_models_updated([], _("Error fetching models: {}").format(str(e)))

    def on_models_updated(self, models, error_msg):
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.addItem(_("Custom..."))
        self.model_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        if error_msg:
            self.status_label.setText(error_msg)
            self.status_label.show()
        else:
            self.status_label.hide()
        if self.pending_model:
            idx = self.model_combo.findText(self.pending_model)
            if idx != -1:
                self.model_combo.setCurrentIndex(idx)
            self.pending_model = None

    def load_prompts(self):
        default_categories = get_prompt_categories()
        self.prompts_data = load_prompts(None) or {}
        for cat in default_categories:
            if cat not in self.prompts_data or not self.prompts_data[cat]:
                default_prompt = get_default_prompt(cat)
                # Ensure default_prompt is a list of dictionaries
                if cat == "Compendium":
                    self.prompts_data[cat] = default_prompt  # Already a list for Compendium
                else:
                    self.prompts_data[cat] = [default_prompt] if isinstance(default_prompt, dict) else default_prompt
        # Validate and flatten prompts_data
        for cat in self.prompts_data:
            if isinstance(self.prompts_data[cat], list):
                flattened = []
                for item in self.prompts_data[cat]:
                    if isinstance(item, list):
                        flattened.extend(item)  # Flatten nested lists
                    elif isinstance(item, dict):
                        flattened.append(item)
                self.prompts_data[cat] = flattened
        self.refresh_tree()

    def refresh_tree(self):
        self.tree.clear()
        categories = list(self.prompts_data.keys())
        categories.sort()
        bold_font = QFont()
        bold_font.setBold(True)
        for category in categories:
            cat_item = QTreeWidgetItem(self.tree, [category])
            cat_item.setData(0, Qt.UserRole, {"type": "category", "name": category})
            # Mark as category for stylesheet
            cat_item.setData(0, Qt.ItemDataRole.UserRole + 1, "true")  # Custom property for is-category
            cat_item.setBackground(0, QBrush(ThemeManager.get_category_background_color()))
            cat_item.setFont(0, bold_font)  # Apply bold font
            for prompt in self.prompts_data[category]:
                if not isinstance(prompt, dict):
                    print(f"Warning: Skipping invalid prompt in category {category}: {prompt}")
                    continue
                child = QTreeWidgetItem(cat_item, [prompt.get("name", "Unnamed")])
                tooltip = (
                    f"Provider: {prompt.get('provider', 'Default')}\n"
                    f"Model: {prompt.get('model', 'Default Model')}\n"
                    f"Max Tokens: {prompt.get('max_tokens', 2000)}\n"
                    f"Temperature: {prompt.get('temperature', 0.7)}\n"
                    f"Text: {prompt.get('text', '')}"
                )
                if prompt.get("default", False):
                    icon_path = os.path.join("assets", "icons", "alert-triangle.svg")
                    child.setIcon(0, ThemeManager.get_tinted_icon(icon_path))
                    tooltip += _("\nDefault prompt (read-only): LLM settings cannot be modified.")
                child.setToolTip(0, tooltip)
                child.setData(0, Qt.UserRole, {
                    "type": "prompt",
                    "name": prompt.get("name", "Unnamed"),
                    "text": prompt.get("text", ""),
                    "default": prompt.get("default", False),
                    "provider": prompt.get("provider", "Default"),
                    "model": prompt.get("model", "Default Model"),
                    "max_tokens": prompt.get("max_tokens", 2000),
                    "temperature": prompt.get("temperature", 0.7)
                })
        self.tree.expandAll()
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)

    def on_item_clicked(self, item, column):
        self.current_prompt_item = item
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "prompt":
            self.editor.setPlainText(data.get("text", ""))
            provider = data.get("provider", "Default")
            model = data.get("model", "Default")
            for i in range(self.provider_combo.count()):
                if self.provider_combo.itemData(i) == provider:
                    self.provider_combo.setCurrentIndex(i)
                    break
            self.selected_model = model
            idx = self.model_combo.findText(model)
            if idx == -1:
                self.pending_model = model
                self.refresh_models(False)
            else:
                self.model_combo.setCurrentIndex(idx)
            self.max_tokens_spin.setValue(data.get("max_tokens", 2000))
            self.temp_spin.setValue(data.get("temperature", 0.7))
            self.parameters_panel.show()
            self.editor.setReadOnly(data.get("default", False))
            if data.get("default", False):
                self.replicate_button.show()
                self.provider_combo.setEnabled(False)
                self.model_combo.setEnabled(False)
                self.temp_spin.setEnabled(False)
                tooltip_msg = _("Default prompts are read-only. LLM settings cannot be modified.")
                self.provider_combo.setToolTip(tooltip_msg)
                self.model_combo.setToolTip(tooltip_msg)
                self.temp_spin.setToolTip(tooltip_msg)
            else:
                self.replicate_button.hide()
                self.provider_combo.setEnabled(True)
                self.model_combo.setEnabled(True)
                self.temp_spin.setEnabled(True)
                self.provider_combo.setToolTip("")
                self.model_combo.setToolTip("")
                self.temp_spin.setToolTip("")
        else:
            self.editor.clear()
            self.parameters_panel.hide()
            self.editor.setReadOnly(False)
            self.replicate_button.hide()

    def save_prompts(self):
        current_item = self.tree.currentItem()
        prompt_name = None
        if current_item:
            data = current_item.data(0, Qt.UserRole)
            if data and data.get("type") == "prompt":
                prompt_name = data.get("name")
                new_text = self.editor.toPlainText()
                data["text"] = new_text
                provider_index = self.provider_combo.currentIndex()
                provider_config = self.provider_combo.itemData(provider_index)
                data["provider"] = provider_config if isinstance(provider_config, str) else provider_config.get("provider", "Default")
                data["model"] = self.model_combo.currentText()
                data["max_tokens"] = self.max_tokens_spin.value()
                data["temperature"] = self.temp_spin.value()
                tooltip = (
                    f"Provider: {data['provider']}\n"
                    f"Model: {data['model']}\n"
                    f"Max Tokens: {data['max_tokens']}\n"
                    f"Temperature: {data['temperature']}\n"
                    f"Text: {new_text}"
                )
                current_item.setToolTip(0, tooltip)
                parent_item = current_item.parent()
                if parent_item:
                    category = parent_item.text(0)
                    for prompt in self.prompts_data.get(category, []):
                        if prompt.get("name") == data.get("name"):
                            prompt.update(data)
                            break
        try:
            with open(self.prompts_file, "w", encoding="utf-8") as f:
                json.dump(self.prompts_data, f, indent=4)
            with open(self.backup_file, "w", encoding="utf-8") as f:
                json.dump(self.prompts_data, f, indent=4)
            QMessageBox.information(self, _("Save All"), _("Prompts saved successfully."))
            self.refresh_tree()
            if prompt_name:
                self.reselect_prompt_by_name(prompt_name)
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Error saving prompts: {}").format(str(e)))

    def reselect_prompt_by_name(self, prompt_name):
        def find_prompt_item(item):
            if not item:
                return None
            data = item.data(0, Qt.UserRole)
            if data and data.get("type") == "prompt" and data.get("name") == prompt_name:
                return item
            for i in range(item.childCount()):
                child = item.child(i)
                found = find_prompt_item(child)
                if found:
                    return found
            return None
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            found_item = find_prompt_item(root.child(i))
            if found_item:
                self.tree.setCurrentItem(None)
                self.tree.setCurrentItem(found_item)
                return

    def on_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.UserRole)
        menu = QMenu()
        if data.get("type") == "category":
            new_action = menu.addAction(_("New Prompt"))
            action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if action == new_action:
                self.add_new_prompt(item)
        elif data.get("type") == "prompt":
            if data.get("default", False):
                replicate_action = menu.addAction(_("Replicate"))
                info_action = menu.addAction(_("Default prompt (read-only)"))
                action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
                if action == replicate_action:
                    self.replicate_prompt()
                return
            replicate_action = menu.addAction(_("Replicate"))
            rename_action = menu.addAction(_("Rename"))
            move_up_action = menu.addAction(_("Move Up"))
            move_down_action = menu.addAction(_("Move Down"))
            delete_action = menu.addAction(_("Delete"))
            save_action = menu.addAction(_("Save"))
            action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if action == replicate_action:
                self.replicate_prompt()
            elif action == rename_action:
                self.rename_prompt(item)
            elif action == move_up_action:
                self.move_prompt(item, up=True)
            elif action == move_down_action:
                self.move_prompt(item, up=False)
            elif action == delete_action:
                self.delete_prompt(item)
            elif action == save_action:
                self.save_prompt(item)

    def add_new_prompt(self, category_item):
        cat_data = category_item.data(0, Qt.UserRole)
        category_name = cat_data.get("name")
        name, ok = QInputDialog.getText(self, _("New Prompt"), _("Enter prompt name:"))
        if not ok or not name.strip():
            return
        name = name.strip()
        provider_index = self.provider_combo.currentIndex()
        provider_config = self.provider_combo.itemData(provider_index)
        new_prompt = {
            "name": name,
            "text": "",
            "default": False,
            "provider": provider_config if isinstance(provider_config, str) else provider_config.get("provider", "Default"),
            "model": self.model_combo.currentText(),
            "max_tokens": 2000,
            "temperature": 0.7
        }
        self.prompts_data.setdefault(category_name, []).append(new_prompt)
        child = QTreeWidgetItem(category_item, [name])
        child.setData(0, Qt.UserRole, {
            "type": "prompt",
            "name": name,
            "text": "",
            "default": False,
            "provider": new_prompt["provider"],
            "model": new_prompt["model"],
            "max_tokens": 2000,
            "temperature": 0.7
        })
        category_item.setExpanded(True)
        self.tree.setCurrentItem(child)
        self.on_item_clicked(child, 0)

    def save_prompt(self, prompt_item):
        data = prompt_item.data(0, Qt.UserRole)
        if data.get("type") != "prompt" or data.get("default", False):
            QMessageBox.information(self, _("Save Prompt"),
                                    _("Cannot save: Either not a prompt or it is a default prompt (read-only)."))
            return
        new_text = self.editor.toPlainText()
        data["text"] = new_text
        provider_index = self.provider_combo.currentIndex()
        provider_config = self.provider_combo.itemData(provider_index)
        data["provider"] = provider_config if isinstance(provider_config, str) else provider_config.get("provider", "Default")
        data["model"] = self.model_combo.currentText()
        data["max_tokens"] = self.max_tokens_spin.value()
        data["temperature"] = self.temp_spin.value()
        tooltip = (
            f"Provider: {data['provider']}\n"
            f"Model: {data['model']}\n"
            f"Max Tokens: {data['max_tokens']}\n"
            f"Temperature: {data['temperature']}\n"
            f"Text: {new_text}"
        )
        prompt_item.setToolTip(0, tooltip)
        parent_item = prompt_item.parent()
        if parent_item:
            category = parent_item.text(0)
            for prompt in self.prompts_data.get(category, []):
                if prompt.get("name") == data.get("name"):
                    prompt.update(data)
                    break
        try:
            with open(self.prompts_file, "w", encoding="utf-8") as f:
                json.dump(self.prompts_data, f, indent=4)
            with open(self.backup_file, "w", encoding="utf-8") as f:
                json.dump(self.prompts_data, f, indent=4)
            QMessageBox.information(self, _("Save Prompt"), _("Prompt '{}' saved successfully.").format(data['name']))
            self.refresh_tree()
            self.reselect_prompt_by_name(data["name"])
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Error saving prompt: {}").format(str(e)))

    def rename_prompt(self, prompt_item):
        data = prompt_item.data(0, Qt.UserRole)
        if data.get("default", False):
            QMessageBox.information(self, _("Rename Prompt"),
                                    _("Default prompts cannot be renamed."))
            return
        current_name = data.get("name")
        new_name, ok = QInputDialog.getText(
            self, _("Rename Prompt"), _("Enter new prompt name:"), text=current_name)
        if ok and new_name.strip():
            new_name = new_name.strip()
            data["name"] = new_name
            prompt_item.setText(0, new_name)
            parent = prompt_item.parent()
            if parent:
                category = parent.text(0)
                for prompt in self.prompts_data.get(category, []):
                    if prompt.get("name") == current_name:
                        prompt["name"] = new_name
                        break

    def move_prompt(self, prompt_item, up=True):
        data = prompt_item.data(0, Qt.UserRole)
        if data.get("default", False):
            QMessageBox.information(self, _("Move Prompt"),
                                    _("Default prompts cannot be moved."))
            return
        parent = prompt_item.parent()
        if parent is None:
            return
        index = parent.indexOfChild(prompt_item)
        new_index = index - 1 if up else index + 1
        if new_index < 0 or new_index >= parent.childCount():
            return
        parent.takeChild(index)
        parent.insertChild(new_index, prompt_item)
        category = parent.text(0)
        prompts = self.prompts_data.get(category, [])
        if index < len(prompts) and new_index < len(prompts):
            prompts.insert(new_index, prompts.pop(index))

    def delete_prompt(self, prompt_item):
        data = prompt_item.data(0, Qt.UserRole)
        if data.get("default", False):
            QMessageBox.information(self, _("Delete Prompt"),
                                    _("Default prompts cannot be deleted."))
            return
        name = data.get("name")
        parent = prompt_item.parent()
        if parent is None:
            return
        category = parent.text(0)
        reply = QMessageBox.question(self, _("Delete Prompt"), _("Delete prompt '{}'?").format(name),
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            prompts = self.prompts_data.get(category, [])
            for i, prompt in enumerate(prompts):
                if prompt.get("name") == name:
                    prompts.pop(i)
                    break
            parent.removeChild(prompt_item)

    def replicate_prompt(self):
        current_item = self.current_prompt_item
        if not current_item:
            return
        data = current_item.data(0, Qt.UserRole)
        if not data:
            return
        new_name, ok = QInputDialog.getText(
            self, _("Replicate Prompt"),
            _("Enter name for the new prompt:"),
            text=data.get("name") + " Copy"
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        new_prompt = data.copy()
        new_prompt["name"] = new_name
        new_prompt["default"] = False
        parent_item = current_item.parent()
        if parent_item:
            category = parent_item.text(0)
            self.prompts_data.setdefault(category, []).append(new_prompt)
            new_child = QTreeWidgetItem(parent_item, [new_name])
            new_child.setData(0, Qt.UserRole, new_prompt)
            parent_item.setExpanded(True)
            self.tree.setCurrentItem(new_child)
            self.on_item_clicked(new_child, 0)
            QMessageBox.information(self, _("Replicated"), _("Prompt replicated. Save the new prompt after you edit it."))

    def show_provider_info(self):
        dialog = ProviderInfoDialog(self)
        dialog.exec_()