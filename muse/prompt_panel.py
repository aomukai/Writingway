from typing import Dict, List
from PyQt5.QtWidgets import QFormLayout, QGroupBox, QComboBox
from PyQt5.QtCore import QFileSystemWatcher

from .prompt_utils import load_prompts
from settings.llm_api_aggregator import WWApiAggregator
from settings.settings_manager import WWSettingsManager

class PromptPanel(QGroupBox):
    def __init__(self, prompt_style: str, parent=None):
        super().__init__(parent)
        self.prompt_style = prompt_style
        self.prompt = None
        self.prompts: List[Dict] = []
        self._load_prompts()
        self.init_ui()

        self.filepath = WWSettingsManager.get_project_path(file="prompts.json")
        self.watcher = QFileSystemWatcher(self)
        if self.filepath:
            self.watcher.addPath(self.filepath)
            self.watcher.fileChanged.connect(self.repopulate_prompts)


    def init_ui(self):
        # LLM Settings Group
        llm_settings_layout = QFormLayout()
        llm_settings_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        llm_settings_layout.setContentsMargins(0, 0, 0, 0)

        tip = _("Select a {} Prompt").format(self.prompt_style)

        self.prompt_combo = QComboBox()
        self.provider_combo = QComboBox()
        self.model_combo = QComboBox()
        
        # Populate providers before prompts, since prompts determine provider
        self._populate_provider_combo()

        self.prompt_combo.setToolTip(tip)
        self.prompt_combo.currentIndexChanged.connect(self._on_prompt_combo_changed)
        self.prompt_combo.setMinimumWidth(300)
        self._populate_prompt_combo()
        llm_settings_layout.addRow(self.prompt_combo)

        self.provider_combo.currentIndexChanged.connect(self._on_provider_combo_changed)
        llm_settings_layout.addRow(self.provider_combo)
        llm_settings_layout.addRow(self.model_combo)
        self.setLayout(llm_settings_layout)
        
        self._on_provider_combo_changed()
    
    def set_category(self, category: str) -> None:
        """Switch the prompt category, reload prompts, and update the prompt combo box."""
        self.prompt_style = category
        current_prompt = self.prompt_combo.currentText()
        self.prompt = None  # Reset selected prompt
        self._load_prompts()
        self.prompt_combo.setToolTip(_("Select a {} Prompt").format(self.prompt_style))
        self._populate_prompt_combo()
        # Try to reselect the same prompt if it exists in the new category
        if current_prompt in [prompt["name"] for prompt in self.prompts]:
            self.prompt_combo.setCurrentText(current_prompt)
        else:
            self._on_prompt_combo_changed()  # Trigger to update provider/model

    def repopulate_prompts(self) -> None:
        """Reload prompts after add/delete/rename, and ensure selection is maintained"""
        current_id = self.prompt_combo.itemData(self.prompt_combo.currentIndex())
        self._load_prompts()
        self._populate_prompt_combo()
        selected = False
        if current_id is not None:
            for i in range(self.prompt_combo.count()):
                if self.prompt_combo.itemData(i) == current_id:
                    self.prompt_combo.setCurrentIndex(i)
                    selected = True
                    break
        if not selected:
            # Select default if exists, else first
            for i, prompt in enumerate(self.prompts):
                if prompt.get("default", False):
                    self.prompt_combo.setCurrentIndex(i)
                    selected = True
                    break
            if not selected and self.prompt_combo.count() > 0:
                self.prompt_combo.setCurrentIndex(0)
        self._on_prompt_combo_changed()

    def get_prompt(self) -> Dict:
        return self.prompt or {}

    def get_overrides(self) -> Dict:
        return {
            "provider": self.provider_combo.currentText(),
            "model": self.model_combo.currentText(),
            "max_tokens": self.prompt.get("max_tokens") if self.prompt else 2000,
            "temperature": self.prompt.get("temperature") if self.prompt else 0.7
        }
    
    def _populate_prompt_combo(self):
        self.prompt_combo.clear()
        for prompt in self.prompts:
            self.prompt_combo.addItem(prompt["name"], prompt.get("id"))

    def _populate_provider_combo(self):
        providers = WWSettingsManager.get_llm_configs()
        provider_names = list(providers.keys())
        self.provider_combo.clear()
        self.provider_combo.addItems(provider_names)

    def _load_prompts(self):
        loaded_prompts = load_prompts(self.prompt_style)
        self.prompts = loaded_prompts if isinstance(loaded_prompts, list) else []

    def _on_prompt_combo_changed(self):
        prompt_name = self.prompt_combo.currentText()
        if not prompt_name:
            self.prompt = {}
            self.provider_combo.setCurrentText("Default")
            self.model_combo.setCurrentText("Default")
            return
        
        self.prompt = next((prompt for prompt in self.prompts if prompt["name"] == prompt_name), {})
        active_provider = WWSettingsManager.get_active_llm_name()
        active_config = WWSettingsManager.get_active_llm_config() or {}
        active_model = active_config.get("model", "")
        
        if self.prompt.get("default"):
            prompt_provider_name = active_provider
        else:
            prompt_provider_name = self.prompt.get("provider") or active_provider
        self.provider_combo.setCurrentText(prompt_provider_name)
        
        # if the provider hasn't changed when the prompt changes, then we have to manually set the model
        prompt_model = self.prompt.get("model") or active_model
        self.model_combo.setCurrentText(prompt_model)
        
    def _on_provider_combo_changed(self):
        self.model_combo.clear()
        provider_name = self.provider_combo.currentText()
        provider = WWApiAggregator.aggregator.get_provider(provider_name)
        if provider:
            try:
                models = provider.get_available_models()
                self.model_combo.addItems(models)
                if self.prompt and provider_name == self.prompt.get("name"):
                        self.model_combo.setCurrentText(self.prompt.get("model", provider.get_current_model()))
                else:
                    self.model_combo.setCurrentText(provider.get_current_model())
            except Exception as e:
                self.model_combo.addItem(_("Default Model"))
                print(f"Error fetching models for {provider_name}: {e}")
        else:
            self.model_combo.addItem(_("Default Model"))