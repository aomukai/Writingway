from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QTableWidget, QTableWidgetItem, QComboBox, QLabel,
                             QDialogButtonBox, QSplitter, QMessageBox, QInputDialog,
                             QHeaderView, QPushButton, QHBoxLayout, QWidget, QLineEdit)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QStyle
import json
import re
from typing import Dict, List

from .llm_api_aggregator import WWApiAggregator
from .settings_manager import WWSettingsManager
from .theme_manager import ThemeManager

class ProviderInfoDialog(QDialog):
    def __init__(self, parent=None, llm_configs=None):
        super().__init__(parent)
        self.llm_configs = llm_configs or {}
        self.current_provider = None  # Track current provider
        self.current_group = "All"  # Track selected group
        self._updating_ui = False  # Reentrancy guard
        self.table_font_size = 12  # Initial font size for table content
        self.setWindowTitle(_("Provider Information"))
        self.resize(1000, 600)
        self.init_ui()
        self.populate_providers()
        self.read_settings()

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.splitter = QSplitter(Qt.Horizontal)

        self.provider_tree = QTreeWidget()
        self.provider_tree.setHeaderLabels([_("Provider")])
        self.provider_tree.itemSelectionChanged.connect(self.provider_selected)
        self.splitter.addWidget(self.provider_tree)

        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # Filter and group selection
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(_("Filter")))
        self.filter_combobox = QComboBox()
        self.filter_combobox.addItems([
            _("All Models"),
            _("Free Models"),
            _("Chat Capabilities"),
            _("Research Capabilities"),
            _("Instruction Following")
        ])
        self.filter_combobox.currentIndexChanged.connect(self.filter_changed)
        filter_layout.addWidget(self.filter_combobox)

        filter_layout.addWidget(QLabel(_("Group:")))
        self.group_combobox = QComboBox()
        self.group_combobox.addItem(_("All"))
        self.group_combobox.currentIndexChanged.connect(self.group_changed)
        self.group_combobox.setMinimumWidth(100)
        filter_layout.addWidget(self.group_combobox)
        filter_layout.addStretch()
        right_layout.addLayout(filter_layout)

        self.model_table = QTableWidget()
        self.model_table.setSelectionMode(QTableWidget.ContiguousSelection)
        self.model_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.model_table.setStyleSheet(f"""
            QTableWidget {{
                font-family: 'Arial';
                font-size: {self.table_font_size}px;
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
        """)
        self.model_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.model_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.model_table)

        right_widget.setLayout(right_layout)
        self.splitter.addWidget(right_widget)
        self.splitter.setSizes([200, 800])
        main_layout.addWidget(self.splitter)

        # Buttons
        button_layout = QHBoxLayout()
        self.collapse_button = QPushButton()
        self.collapse_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        self.collapse_button.setToolTip(_("Collapse all providers"))
        self.collapse_button.clicked.connect(self.collapse_tree)
        button_layout.addWidget(self.collapse_button)

        # Zoom buttons
        self.zoom_in_button = QPushButton()
        self.zoom_in_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/zoom-in.svg"))
        self.zoom_in_button.setToolTip(_("Zoom in table content (CMD++)"))
        self.zoom_in_button.clicked.connect(self.zoom_in)
        button_layout.addWidget(self.zoom_in_button)

        self.zoom_out_button = QPushButton()
        self.zoom_out_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/zoom-out.svg"))
        self.zoom_out_button.setToolTip(_("Zoom out table content (CMD+-)"))
        self.zoom_out_button.clicked.connect(self.zoom_out)
        button_layout.addWidget(self.zoom_out_button)

        self.reset_zoom_button = QPushButton()
        self.reset_zoom_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.reset_zoom_button.setToolTip(_("Reset table content zoom"))
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        button_layout.addWidget(self.reset_zoom_button)

        button_layout.addStretch()

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.on_close_clicked)
        button_layout.addWidget(button_box)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def keyPressEvent(self, event):
        """Handle CMD++ and CMD+- shortcuts for zooming."""
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
                self.zoom_in()
                event.accept()
                return
            elif event.key() == Qt.Key_Minus:
                self.zoom_out()
                event.accept()
                return
        super().keyPressEvent(event)

    def zoom_in(self):
        """Increase font size of table content."""
        self.table_font_size = min(self.table_font_size + 2, 24)  # Max font size 24
        self.update_table_font()

    def zoom_out(self):
        """Decrease font size of table content."""
        self.table_font_size = max(self.table_font_size - 2, 8)  # Min font size 8
        self.update_table_font()

    def reset_zoom(self):
        """Reset font size of table content to default."""
        self.table_font_size = 12  # Default font size
        self.update_table_font()

    def update_table_font(self):
        """Update the font size of table content only."""
        self.model_table.setStyleSheet(f"""
            QTableWidget {{
                font-family: 'Arial';
                font-size: {self.table_font_size}px;
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
        """)
        # Force table to refresh to apply new font size
        self.model_table.viewport().update()

    def on_close_clicked(self):
        """Save settings and close the dialog."""
        self.write_settings()
        self.reject()

    def populate_providers(self):
        providers = WWApiAggregator.get_llm_providers()
        custom_providers = [
            config["provider"] for config in self.llm_configs.values() if config["provider"] == "Custom"
        ]
        all_providers = sorted(set(providers + custom_providers))

        self.provider_tree.clear()
        for provider in all_providers:
            item = QTreeWidgetItem([provider])
            self.provider_tree.addTopLevelItem(item)

    def provider_selected(self):
        if self._updating_ui:
            return
        selected_items = self.provider_tree.selectedItems()
        if not selected_items:
            self.current_provider = None
            self.current_group = _("All")
            self.update_ui()
            return
        selected_item = selected_items[0]
        if selected_item.parent() is None:  # Top-level provider
            provider_name = selected_item.text(0)
            if provider_name != self.current_provider:
                self.current_provider = provider_name
                self.current_group = _("All")
                self.update_ui()
        else:  # Group selected
            self.current_provider = selected_item.parent().text(0)
            self.current_group = selected_item.text(0)
            self.update_ui()

    def filter_changed(self):
        self.update_ui()

    def group_changed(self):
        self.current_group = self.group_combobox.currentText()
        self.update_ui()

    def collapse_tree(self):
        self._updating_ui = True
        try:
            for i in range(self.provider_tree.topLevelItemCount()):
                item = self.provider_tree.topLevelItem(i)
                item.setExpanded(False)
        finally:
            self._updating_ui = False

    def flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                items.append((new_key, json.dumps(v, ensure_ascii=False)))
            else:
                items.append((new_key, str(v) if v is not None else ""))
        return dict(items)

    def get_all_keys(self, models: List[Dict]) -> List[str]:
        all_keys = set()
        for model in models:
            flattened = self.flatten_dict(model)
            all_keys.update(flattened.keys())
        priority_keys = ['id', 'name', 'context_length']
        other_keys = sorted([k for k in all_keys if k not in priority_keys])
        return priority_keys + other_keys

    def update_ui(self):
        if self._updating_ui:
            return
        self._updating_ui = True
        try:
            if not self.current_provider:
                self.group_combobox.clear()
                self.group_combobox.addItem("All")
                self.model_table.setRowCount(0)
                self.model_table.setColumnCount(0)
                return

            provider_name = self.current_provider
            filter_type = self.filter_combobox.currentText()

            config = {}
            llm_configs = WWSettingsManager.get_llm_configs()
            for name, cfg in llm_configs.items():
                if cfg.get("provider") == provider_name:
                    config["api_key"] = cfg.get("api_key", "")
                    break

            provider = WWApiAggregator.aggregator.create_provider(provider_name, config)
            if not provider:
                self.group_combobox.clear()
                self.group_combobox.addItem("All")
                self.model_table.setRowCount(0)
                self.model_table.setColumnCount(0)
                QMessageBox.warning(self, "Error", _("No models available or error fetching models."))
                return

            if provider.model_requires_api_key and not config.get("api_key"):
                api_key, ok = QInputDialog.getText(
                    self,
                    _("API Key Required"),
                    _("An API key is required for ") + provider_name + _(". Please enter it:"),
                    echo=QLineEdit.Password
                )
                if ok and api_key:
                    config["api_key"] = api_key
                    provider_config = {
                        "provider": provider_name,
                        "endpoint": config.get("endpoint", provider.get_default_endpoint()),
                        "model": "",
                        "api_key": api_key,
                        "timeout": config.get("timeout", 30)
                    }
                    WWSettingsManager.update_llm_config(f"{provider_name}_auto", provider_config)
                    provider = WWApiAggregator.aggregator.create_provider(provider_name, config)
                else:
                    self.group_combobox.clear()
                    self.group_combobox.addItem("All")
                    self.model_table.setRowCount(0)
                    self.model_table.setColumnCount(0)
                    QMessageBox.warning(self, "Error", _("API key is required for ") + provider_name)
                    return

            try:
                model_details = provider.get_model_details()
            except Exception as e:
                self.group_combobox.clear()
                self.group_combobox.addItem("All")
                self.model_table.setRowCount(0)
                self.model_table.setColumnCount(0)
                QMessageBox.warning(self, "Error", _("Failed to fetch models for ") + provider_name + f": {str(e)}")
                return

            # Group models
            grouped_models = {}
            for model in model_details:
                group = model["id"].split("/")[0] if "/" in model["id"] else provider_name
                if group not in grouped_models:
                    grouped_models[group] = []
                grouped_models[group].append(model)

            # Apply filtering
            filtered_models = {}
            for group, models in grouped_models.items():
                filtered = []
                for model in models:
                    pricing = model.get("pricing", {})
                    architecture = model.get("architecture", {})
                    is_free = all(float(v) == 0 for v in pricing.values() if v)
                    is_chat = architecture.get("modality") == "text->text"
                    is_research = "research" in model.get("description", "").lower()
                    is_instruction = architecture.get("instruct_type") in ["alpaca", "zephyr", "general"]

                    if filter_type == _("All Models"):
                        filtered.append(model)
                    elif filter_type == _("Free Models") and is_free:
                        filtered.append(model)
                    elif filter_type == _("Chat Capabilities") and is_chat:
                        filtered.append(model)
                    elif filter_type == _("Research Capabilities") and is_research:
                        filtered.append(model)
                    elif filter_type == _("Instruction Following") and is_instruction:
                        filtered.append(model)

                if filtered:
                    filtered_models[group] = filtered

            # Update group combobox
            self.group_combobox.blockSignals(True)
            self.group_combobox.clear()
            self.group_combobox.addItem("All")
            for group in sorted(filtered_models.keys()):
                self.group_combobox.addItem(group)
            # Restore selected group
            index = self.group_combobox.findText(self.current_group)
            if index >= 0:
                self.group_combobox.setCurrentIndex(index)
            else:
                self.current_group = "All"
                self.group_combobox.setCurrentIndex(0)
            self.group_combobox.blockSignals(False)

            # Update provider tree (only for current provider)
            for i in range(self.provider_tree.topLevelItemCount()):
                item = self.provider_tree.topLevelItem(i)
                if item.text(0) == provider_name:
                    # Preserve expanded state
                    was_expanded = item.isExpanded()
                    item.takeChildren()
                    for group in sorted(filtered_models.keys()):
                        group_item = QTreeWidgetItem([group])
                        item.addChild(group_item)
                    item.setExpanded(was_expanded)
                    item.setSelected(True)
                    break

            # Populate table
            all_models = []
            if self.current_group == "All":
                all_models = [model for models in filtered_models.values() for model in models]
            else:
                all_models = filtered_models.get(self.current_group, [])

            if not all_models:
                self.model_table.setRowCount(0)
                self.model_table.setColumnCount(0)
                return

            column_keys = self.get_all_keys(all_models)
            self.model_table.setColumnCount(len(column_keys))
            self.model_table.setHorizontalHeaderLabels([key.split('.')[-1] for key in column_keys])

            self.model_table.setRowCount(len(all_models))
            for row, model in enumerate(sorted(all_models, key=lambda x: x["id"], reverse=provider.use_reverse_sort)):
                flattened = self.flatten_dict(model)
                for col, key in enumerate(column_keys):
                    value = flattened.get(key, "")
                    value = self.smart_string(value)
                    item = QTableWidgetItem(value)
                    if key == "id":
                        font = QFont()
                        font.setBold(True)
                        item.setFont(font)
                    if len(value) > 50:
                        item.setToolTip(value)
                        item.setText(value[:47] + "...")
                    self.model_table.setItem(row, col, item)

            self.model_table.resizeColumnsToContents()
        finally:
            self._updating_ui = False

    def smart_string(self, value):
        """
        Converts a floating-point number to a string, intelligently removing
        insignificant trailing digits, or returns the string unchanged if it's not numeric.

        Args:
            value: The floating-point number to convert, or a string.

        Returns:
            A string representation of the number, with trailing insignificant
            digits removed, or the original string if it's not numeric.
        """
        try:
            # Convert string to float and back to string to detect scientific notation or long decimals
            float_val = float(value)
            # Use regex to match floats with many trailing zeros or small epsilon (e.g., 0.060000000000000005)
            if re.match(r'^-?\d*\.\d{2,}[1-9]?0*$', value) or 'e' in value.lower():
                # Format to 2 decimal places, strip trailing zeros and decimal point if unnecessary
                return f'{float_val:.2f}'.rstrip('0').rstrip('.')
            return value  # Return unchanged if not a problematic float
        except ValueError:
            return value  # Return unchanged if not a number (e.g., date, string)

    def update_labels(self, labels):
        self.labels = labels
        self.setWindowTitle(_("Provider and Model Information"))
        self.provider_tree.setHeaderLabels([_("Provider")])
        self.filter_combobox.clear()
        self.filter_combobox.addItems([
            _("All Models"),
            _("Free Models"),
            _("Chat Capabilities"),
            _("Research Capabilities"),
            _("Instruction Following")
        ])
        self.update_ui()

    def read_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        self.restoreGeometry(settings.value("ProviderInfoDialog/geometry", self.saveGeometry()))
        self.splitter.restoreState(settings.value("ProviderInfoDialog/splitter", self.splitter.saveState()))
        # Restore table font size
        saved_font_size = settings.value("ProviderInfoDialog/table_font_size", 12, type=int)
        self.table_font_size = max(8, min(24, saved_font_size))  # Ensure within valid range
        self.update_table_font()

    def write_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue("ProviderInfoDialog/geometry", self.saveGeometry())
        settings.setValue("ProviderInfoDialog/splitter", self.splitter.saveState())
        # Save table font size
        settings.setValue("ProviderInfoDialog/table_font_size", self.table_font_size)

    def closeEvent(self, event):
        self.write_settings()
        super().closeEvent(event)