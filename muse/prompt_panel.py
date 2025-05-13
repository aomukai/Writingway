from PyQt5.QtWidgets import QFormLayout, QGroupBox, QComboBox

from .prompt_utils import load_prompts
from settings.llm_api_aggregator import WWApiAggregator
from settings.settings_manager import WWSettingsManager

class PromptPanel(QGroupBox):
    def __init__(self, prompt_style:str, parent=None):
        super().__init__(parent)
        self.prompt_style = prompt_style
        self.prompt = None
        self._load_prompts()
        self.init_ui()



    def init_ui(self):
         # LLM Settings Group
        llm_settings_layout = QFormLayout()
        llm_settings_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        llm_settings_layout.setContentsMargins(0, 0, 0, 0)

        tip = _("Select a {} Prompt").format(self.prompt_style)

        self.prompt_combo = QComboBox()
        self.provider_combo = QComboBox()
        self.model_combo = QComboBox()

        self.prompt_combo.setToolTip(tip)
        self.prompt_combo.currentIndexChanged.connect(self._on_prompt_combo_changed)
        self.prompt_combo.setMinimumWidth(300)
        self._populate_prompt_combo()
        llm_settings_layout.addRow(self.prompt_combo)

        self.provider_combo.currentIndexChanged.connect(self._on_provider_combo_changed)
        self._populate_provider_combo()
        llm_settings_layout.addRow(self.provider_combo)
        llm_settings_layout.addRow(self.model_combo)
        self.setLayout(llm_settings_layout)
    
    def repopulate_prompts(self):
        self._load_prompts()
        current_prompt = self.prompt_combo.currentText()
        self._populate_prompt_combo()
        self.prompt_combo.setCurrentText(current_prompt)

    def get_prompt(self):
        return self.prompt or {}
    
    def get_overrides(self):
        return {
            "provider": self.provider_combo.currentText(),
            "model": self.model_combo.currentText(),
            "max_tokens": self.prompt.get("max_tokens"),
            "temperature": self.prompt.get("temperature")

        }
    
    def _populate_prompt_combo(self):
        self.prompt_combo.clear()
        self.prompt_combo.addItems([prompt["name"] for prompt in self.prompts])

    def _populate_provider_combo(self):
        providers = WWSettingsManager.get_llm_configs()
        provider_names = list(providers.keys())
        self.provider_combo.clear()
        self.provider_combo.addItems(provider_names)

    def _load_prompts(self):
        self.prompts = load_prompts(self.prompt_style)

    def _on_prompt_combo_changed(self):
        prompt_name = self.prompt_combo.currentText()
        if not prompt_name:
            return
        
        self.prompt = next((prompt for prompt in self.prompts if prompt["name"] == prompt_name), {})
        prompt_provider_name = self.prompt.get("provider", None)
        self.provider_combo.setCurrentText(prompt_provider_name or "Default")
        # if the provider hasn't changed when the prompt changes, then we have to manually set the model
        self.model_combo.setCurrentText(self.prompt.get("model", "Default"))

    def _on_provider_combo_changed(self):
        self.model_combo.clear()
        provider_name = self.provider_combo.currentText()
        provider = WWApiAggregator.aggregator.get_provider(provider_name)
        if provider:
            try:
                models = provider.get_available_models()
                self.model_combo.addItems(models)
                if provider_name == self.prompt["name"]:
                    self.model_combo.setCurrentText(self.prompt.get("model", provider.get_current_model()))
                else:
                    self.model_combo.setCurrentText(provider.get_current_model())
            except Exception as e:
                self.model_combo.addItem(_("Default Model"))
                print(f"Error fetching models for {provider_name}: {e}")
        else:
            self.model_combo.addItem(_("Default Model"))
