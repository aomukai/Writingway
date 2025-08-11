from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QTableWidget, QTableWidgetItem,
                             QPushButton, QGroupBox, QHBoxLayout, QSpinBox, QDoubleSpinBox,
                             QComboBox, QProgressBar, QLabel, QWidget, QInputDialog, QMessageBox)
from PyQt5.QtCore import Qt, QTimer

from muse.brainstorm_worker import BrainstormWorker, RunGroup
from settings.llm_api_aggregator import WWApiAggregator
from muse.prompt_utils import load_prompts
from settings.settings_manager import WWSettingsManager
from typing import Optional
import json
import os
import time
from muse.brainstorm_results_dialog import BrainstormResultsDialog
from muse.prompt_preview_dialog import PromptPreviewDialog

class BrainstormModeDialog(QDialog):
    def __init__(self, prompt: str, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.setWindowTitle("Brainstorm Mode")
        self.setMinimumSize(800, 600)
        self.worker: Optional[BrainstormWorker] = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Run Groups
        run_groups_box = QGroupBox("Run Groups")
        run_groups_layout = QVBoxLayout()
        self.run_groups_table = QTableWidget()
        self.run_groups_table.setColumnCount(9)
        self.run_groups_table.setHorizontalHeaderLabels(["Provider", "Model", "Runs", "Temperature", "Delay (s)", "Retries", "Backoff Factor", "Max Concurrent", "Max Tokens"])
        run_groups_layout.addWidget(self.run_groups_table)
        
        run_groups_buttons_layout = QHBoxLayout()
        self.add_run_group_button = QPushButton("Add Group")
        self.add_run_group_button.clicked.connect(self.add_run_group)
        self.remove_run_group_button = QPushButton("Remove Group")
        self.remove_run_group_button.clicked.connect(self.remove_run_group)
        run_groups_buttons_layout.addWidget(self.add_run_group_button)
        run_groups_buttons_layout.addWidget(self.remove_run_group_button)
        run_groups_buttons_layout.addStretch()
        run_groups_layout.addLayout(run_groups_buttons_layout)
        run_groups_box.setLayout(run_groups_layout)
        layout.addWidget(run_groups_box)

        # Judge Configuration
        judge_box = QGroupBox("Judge Configuration")
        judge_layout = QFormLayout()
        self.judge_provider_combo = QComboBox()
        self.judge_model_combo = QComboBox()
        self.judge_prompt_combo = QComboBox()
        judge_layout.addRow("Judge Provider:", self.judge_provider_combo)
        judge_layout.addRow("Judge Model:", self.judge_model_combo)
        judge_layout.addRow("Judge Prompt:", self.judge_prompt_combo)
        judge_box.setLayout(judge_layout)
        layout.addWidget(judge_box)

        # Progress and Control
        progress_box = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_box.setLayout(progress_layout)
        layout.addWidget(progress_box)

        # Preset buttons
        preset_layout = QHBoxLayout()
        self.save_preset_button = QPushButton("Save Preset")
        self.save_preset_button.clicked.connect(self.save_preset)
        self.load_preset_button = QPushButton("Load Preset")
        self.load_preset_button.clicked.connect(self.load_preset)
        self.history_button = QPushButton("History")
        self.history_button.clicked.connect(self.show_history)
        preset_layout.addWidget(self.save_preset_button)
        preset_layout.addWidget(self.load_preset_button)
        preset_layout.addWidget(self.history_button)
        preset_layout.addStretch()
        layout.addLayout(preset_layout)
        
        # Main control buttons
        buttons_layout = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_brainstorm)
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.preview_brainstorm)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_brainstorm)
        self.cancel_button.setEnabled(False)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.preview_button)
        buttons_layout.addWidget(self.run_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.close_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)
        self.populate_combos()

    def populate_combos(self):
        llm_configs = WWSettingsManager.get_llm_configs()
        providers = list(llm_configs.keys())
        self.judge_provider_combo.addItems(providers)
        self.judge_provider_combo.currentTextChanged.connect(self.populate_judge_models)
        
        # Populate models for the first provider
        if providers:
            self.populate_judge_models(providers[0])
        else:
            self.judge_model_combo.addItem("Default Model")
        
        # Populate judge prompts
        judge_prompts = load_prompts("Judge")
        if judge_prompts:
            self.judge_prompt_combo.addItems([prompt["name"] for prompt in judge_prompts])
        else:
            self.judge_prompt_combo.addItem("Default Judge Prompt")
        
        # Force update of the combo boxes
        self.judge_provider_combo.update()
        self.judge_model_combo.update()
        self.judge_prompt_combo.update()

    def populate_judge_models(self, provider_name):
        self.judge_model_combo.clear()
        try:
            provider = WWApiAggregator.aggregator.get_provider(provider_name)
            if provider:
                try:
                    models = provider.get_available_models()
                    if models:
                        self.judge_model_combo.addItems(models)
                        # Force update of the combo box
                        self.judge_model_combo.update()
                    else:
                        self.judge_model_combo.addItem("Default Model")
                except Exception as e:
                    self.judge_model_combo.addItem("Default Model")
                    print(f"Error fetching models for {provider_name}: {e}")
            else:
                self.judge_model_combo.addItem("Default Model")
        except Exception as e:
            self.judge_model_combo.addItem("Default Model")
            print(f"Error getting provider {provider_name}: {e}")

    def add_run_group(self):
        row_position = self.run_groups_table.rowCount()
        self.run_groups_table.insertRow(row_position)
        
        provider_combo = QComboBox()
        llm_configs = WWSettingsManager.get_llm_configs()
        providers = list(llm_configs.keys())
        provider_combo.addItems(providers)
        # Use a closure to capture the row_position correctly
        provider_combo.currentTextChanged.connect(lambda text, row=row_position: QTimer.singleShot(0, lambda: self.populate_models(row, text)))
        self.run_groups_table.setCellWidget(row_position, 0, provider_combo)
        
        model_combo = QComboBox()
        # This should be populated based on the provider
        self.run_groups_table.setCellWidget(row_position, 1, model_combo)
        
        # Populate models for the first provider
        # Use a single-shot timer to ensure the UI is fully updated before populating models
        if provider_combo.count() > 0:
            QTimer.singleShot(0, lambda: self.populate_models(row_position, provider_combo.currentText()))
        else:
            # If no providers are available, add a default model
            model_combo.addItem("Default Model")
        
        runs_spinbox = QSpinBox()
        runs_spinbox.setRange(1, 100)
        runs_spinbox.setValue(1)
        self.run_groups_table.setCellWidget(row_position, 2, runs_spinbox)
        
        temp_spinbox = QDoubleSpinBox()
        temp_spinbox.setRange(0.0, 2.0)
        temp_spinbox.setSingleStep(0.1)
        temp_spinbox.setValue(0.7)
        self.run_groups_table.setCellWidget(row_position, 3, temp_spinbox)
        
        delay_spinbox = QSpinBox()
        delay_spinbox.setRange(0, 600)
        delay_spinbox.setValue(1)
        self.run_groups_table.setCellWidget(row_position, 4, delay_spinbox)
        
        retries_spinbox = QSpinBox()
        retries_spinbox.setRange(0, 10)
        retries_spinbox.setValue(3)
        self.run_groups_table.setCellWidget(row_position, 5, retries_spinbox)
        
        backoff_spinbox = QDoubleSpinBox()
        backoff_spinbox.setRange(1.0, 10.0)
        backoff_spinbox.setSingleStep(0.1)
        backoff_spinbox.setValue(2.0)
        self.run_groups_table.setCellWidget(row_position, 6, backoff_spinbox)
        
        max_concurrent_spinbox = QSpinBox()
        max_concurrent_spinbox.setRange(1, 100)
        max_concurrent_spinbox.setValue(5)
        self.run_groups_table.setCellWidget(row_position, 7, max_concurrent_spinbox)
        
        max_tokens_spinbox = QSpinBox()
        max_tokens_spinbox.setRange(1, 128000)
        max_tokens_spinbox.setValue(1024)
        self.run_groups_table.setCellWidget(row_position, 8, max_tokens_spinbox)
        
        # Populate models for the first provider
        # Use a single-shot timer to ensure the UI is fully updated before populating models
        if provider_combo.count() > 0:
            QTimer.singleShot(0, lambda: self.populate_models(row_position, provider_combo.currentText()))
        else:
            # If no providers are available, add a default model
            model_combo.addItem("Default Model")
        
        # Force update of the combo boxes
        provider_combo.update()
        model_combo.update()

    def populate_models(self, row, provider_name):
        model_combo = self.run_groups_table.cellWidget(row, 1)
        # Check if model_combo exists and is a valid QComboBox
        if model_combo is not None and hasattr(model_combo, 'clear'):
            model_combo.clear()
            try:
                provider = WWApiAggregator.aggregator.get_provider(provider_name)
                if provider:
                    try:
                        models = provider.get_available_models()
                        if models:
                            model_combo.addItems(models)
                            # Force update of the combo box
                            model_combo.update()
                        else:
                            model_combo.addItem("Default Model")
                    except Exception as e:
                        model_combo.addItem("Default Model")
                else:
                    model_combo.addItem("Default Model")
            except Exception as e:
                model_combo.addItem("Default Model")
        else:
            # If model_combo is None or invalid, create a temporary one to avoid errors
            model_combo = QComboBox()
            model_combo.addItem("Default Model")

    def remove_run_group(self):
        current_row = self.run_groups_table.currentRow()
        if current_row >= 0:
            self.run_groups_table.removeRow(current_row)

    def run_brainstorm(self):
        run_groups = []
        for row in range(self.run_groups_table.rowCount()):
            # Get widgets from the table
            provider_widget = self.run_groups_table.cellWidget(row, 0)
            model_widget = self.run_groups_table.cellWidget(row, 1)
            runs_widget = self.run_groups_table.cellWidget(row, 2)
            temp_widget = self.run_groups_table.cellWidget(row, 3)
            delay_widget = self.run_groups_table.cellWidget(row, 4)
            retries_widget = self.run_groups_table.cellWidget(row, 5)
            backoff_widget = self.run_groups_table.cellWidget(row, 6)
            max_concurrent_widget = self.run_groups_table.cellWidget(row, 7)
            max_tokens_widget = self.run_groups_table.cellWidget(row, 8)
            
            # Check if all widgets exist and are of the correct type
            if (isinstance(provider_widget, QComboBox) and
                isinstance(model_widget, QComboBox) and
                isinstance(runs_widget, QSpinBox) and
                isinstance(temp_widget, QDoubleSpinBox) and
                isinstance(delay_widget, QSpinBox) and
                isinstance(retries_widget, QSpinBox) and
                isinstance(backoff_widget, QDoubleSpinBox) and
                isinstance(max_concurrent_widget, QSpinBox) and
                isinstance(max_tokens_widget, QSpinBox)):
                
                provider = provider_widget.currentText()
                model = model_widget.currentText()
                runs = runs_widget.value()
                temperature = temp_widget.value()
                delay = delay_widget.value()
                retries = retries_widget.value()
                backoff_factor = backoff_widget.value()
                max_concurrent = max_concurrent_widget.value()
                max_tokens = max_tokens_widget.value()
                
                run_groups.append(RunGroup(
                    provider=provider,
                    model=model,
                    runs=runs,
                    temperature=temperature,
                    delay=delay,
                    retries=retries,
                    backoff_factor=backoff_factor,
                    max_concurrent=max_concurrent,
                    max_tokens=max_tokens
                ))

        if not run_groups:
            return

        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        self.worker = BrainstormWorker(run_groups, self.prompt)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def cancel_brainstorm(self):
        if self.worker:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            
    def preview_brainstorm(self):
        """Preview the final prompt to be sent to the LLM."""
        # Get context from bottom_stack
        action_beats = self.prompt
        extra_context = ""
        current_scene_text = ""
        additional_vars = {}
        
        parent = self.parent()
        if parent:
            # Try to find the bottom stack in the parent hierarchy
            bottom_stack = getattr(parent, 'bottom_stack', None)
            if bottom_stack:
                # Get extra context from context_panel
                if hasattr(bottom_stack, 'context_panel'):
                    extra_context = bottom_stack.context_panel.get_selected_context_text()
                    
                # Get current scene text
                if hasattr(bottom_stack, 'scene_editor') and bottom_stack.scene_editor:
                    current_scene_text = bottom_stack.scene_editor.editor.toPlainText().strip()
                    
                # Get additional variables
                if hasattr(bottom_stack, 'pov_combo'):
                    additional_vars["pov"] = bottom_stack.pov_combo.currentText()
                if hasattr(bottom_stack, 'pov_character_combo'):
                    additional_vars["pov_character"] = bottom_stack.pov_character_combo.currentText()
                if hasattr(bottom_stack, 'tense_combo'):
                    additional_vars["tense"] = bottom_stack.tense_combo.currentText()
        
        # Create a simple prompt config for preview
        prompt_config = {
            "name": "Brainstorm Prompt",
            "text": self.prompt,
            "type": "Prose"
        }
        
        # Create and show the preview dialog
        dialog = PromptPreviewDialog(
            parent,
            prompt_config=prompt_config,
            user_input=action_beats,
            additional_vars=additional_vars,
            current_scene_text=current_scene_text,
            extra_context=extra_context)
        dialog.exec_()

    def update_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)

    def on_finished(self, results):
        # Get judge configuration
        judge_provider = self.judge_provider_combo.currentText()
        judge_model = self.judge_model_combo.currentText()
        judge_prompt_name = self.judge_prompt_combo.currentText()
        
        # Get the actual prompt text from the prompts library
        judge_prompts = load_prompts("Judge")
        judge_prompt_text = ""
        if judge_prompts:
            for prompt in judge_prompts:
                if prompt["name"] == judge_prompt_name:
                    judge_prompt_text = prompt["text"]
                    break
        
        if not judge_prompt_text:
            judge_prompt_text = "Please rank and evaluate the following responses:"
        
        # Evaluate results using the judge
        self.progress_label.setText("Evaluating results...")
        evaluated_results = ""
        if self.worker:
            evaluated_results = self.worker.evaluate_results(results, judge_provider, judge_model, judge_prompt_text)
        
        # Get context from bottom_stack
        action_beats = ""
        extra_context = ""
        parent = self.parent()
        if parent:
            # Try to find the bottom stack in the parent hierarchy
            bottom_stack = getattr(parent, 'bottom_stack', None)
            if bottom_stack:
                # Get action beats from prompt_input
                if hasattr(bottom_stack, 'prompt_input'):
                    action_beats = bottom_stack.prompt_input.toPlainText().strip()
                
                # Get extra context from context_panel
                if hasattr(bottom_stack, 'context_panel'):
                    extra_context = bottom_stack.context_panel.get_selected_context_text()
        
        # Save to history
        self.save_history(results, evaluated_results, action_beats, extra_context)
        
        # Show results in a dialog
        dialog = BrainstormResultsDialog(results, evaluated_results, action_beats, extra_context, parent)
        dialog.exec_()
        
        # Re-enable the run button
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("Finished!")

    def on_error(self, error_message):
        self.progress_label.setText(f"Error: {error_message}")
        # Maybe show a message box as well
        
    def save_preset(self):
        """Save the current configuration as a preset."""
        preset_name, ok = QInputDialog.getText(self, "Save Preset", "Enter preset name:")
        if not ok or not preset_name.strip():
            return
            
        preset_name = preset_name.strip()
        
        # Add a small delay to ensure model combo boxes are fully populated
        QTimer.singleShot(100, lambda: self._save_preset_delayed(preset_name))
    
    def _save_preset_delayed(self, preset_name):
        """Save the current configuration as a preset after a delay."""
        # Get run groups data
        run_groups_data = []
        for row in range(self.run_groups_table.rowCount()):
            provider_widget = self.run_groups_table.cellWidget(row, 0)
            model_widget = self.run_groups_table.cellWidget(row, 1)
            runs_widget = self.run_groups_table.cellWidget(row, 2)
            temp_widget = self.run_groups_table.cellWidget(row, 3)
            delay_widget = self.run_groups_table.cellWidget(row, 4)
            retries_widget = self.run_groups_table.cellWidget(row, 5)
            backoff_widget = self.run_groups_table.cellWidget(row, 6)
            max_concurrent_widget = self.run_groups_table.cellWidget(row, 7)
            max_tokens_widget = self.run_groups_table.cellWidget(row, 8)
            
            if (isinstance(provider_widget, QComboBox) and
                isinstance(model_widget, QComboBox) and
                isinstance(runs_widget, QSpinBox) and
                isinstance(temp_widget, QDoubleSpinBox) and
                isinstance(delay_widget, QSpinBox) and
                isinstance(retries_widget, QSpinBox) and
                isinstance(backoff_widget, QDoubleSpinBox) and
                isinstance(max_concurrent_widget, QSpinBox) and
                isinstance(max_tokens_widget, QSpinBox)):
                
                run_groups_data.append({
                    "provider": provider_widget.currentText(),
                    "model": model_widget.currentText(),
                    "runs": runs_widget.value(),
                    "temperature": temp_widget.value(),
                    "delay": delay_widget.value(),
                    "retries": retries_widget.value(),
                    "backoff_factor": backoff_widget.value(),
                    "max_concurrent": max_concurrent_widget.value(),
                    "max_tokens": max_tokens_widget.value()
                })
        
        # Get judge configuration
        judge_data = {
            "provider": self.judge_provider_combo.currentText(),
            "model": self.judge_model_combo.currentText(),
            "prompt": self.judge_prompt_combo.currentText()
        }
        
        # Create preset data
        preset_data = {
            "run_groups": run_groups_data,
            "judge": judge_data
        }
        
        # Save to file
        presets_dir = WWSettingsManager.get_project_path("brainstorm_presets")
        os.makedirs(presets_dir, exist_ok=True)
        preset_file = os.path.join(presets_dir, f"{preset_name}.json")
        
        try:
            with open(preset_file, 'w') as f:
                json.dump(preset_data, f, indent=2)
            QMessageBox.information(self, "Save Preset", f"Preset '{preset_name}' saved successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Save Preset", f"Error saving preset: {e}")
            
    def save_history(self, results, judge_response, action_beats, extra_context):
        """Save the current brainstorm results to history."""
        try:
            # Create history data
            history_data = {
                "timestamp": time.time(),
                "prompt": self.prompt,
                "action_beats": action_beats,
                "extra_context": extra_context,
                "run_groups": [],
                "judge": {
                    "provider": self.judge_provider_combo.currentText(),
                    "model": self.judge_model_combo.currentText(),
                    "prompt": self.judge_prompt_combo.currentText()
                },
                "results": results,
                "judge_response": judge_response
            }
            
            # Add run groups data
            for row in range(self.run_groups_table.rowCount()):
                provider_widget = self.run_groups_table.cellWidget(row, 0)
                model_widget = self.run_groups_table.cellWidget(row, 1)
                runs_widget = self.run_groups_table.cellWidget(row, 2)
                temp_widget = self.run_groups_table.cellWidget(row, 3)
                delay_widget = self.run_groups_table.cellWidget(row, 4)
                retries_widget = self.run_groups_table.cellWidget(row, 5)
                backoff_widget = self.run_groups_table.cellWidget(row, 6)
                max_concurrent_widget = self.run_groups_table.cellWidget(row, 7)
                max_tokens_widget = self.run_groups_table.cellWidget(row, 8)
                
                if (isinstance(provider_widget, QComboBox) and
                    isinstance(model_widget, QComboBox) and
                    isinstance(runs_widget, QSpinBox) and
                    isinstance(temp_widget, QDoubleSpinBox) and
                    isinstance(delay_widget, QSpinBox) and
                    isinstance(retries_widget, QSpinBox) and
                    isinstance(backoff_widget, QDoubleSpinBox) and
                    isinstance(max_concurrent_widget, QSpinBox) and
                    isinstance(max_tokens_widget, QSpinBox)):
                    
                    history_data["run_groups"].append({
                        "provider": provider_widget.currentText(),
                        "model": model_widget.currentText(),
                        "runs": runs_widget.value(),
                        "temperature": temp_widget.value(),
                        "delay": delay_widget.value(),
                        "retries": retries_widget.value(),
                        "backoff_factor": backoff_widget.value(),
                        "max_concurrent": max_concurrent_widget.value(),
                        "max_tokens": max_tokens_widget.value()
                    })
            
            # Save to file
            history_dir = WWSettingsManager.get_project_path("brainstorm_history")
            os.makedirs(history_dir, exist_ok=True)
            
            # Create filename based on timestamp
            timestamp = int(time.time())
            history_file = os.path.join(history_dir, f"history_{timestamp}.json")
            
            with open(history_file, 'w') as f:
                json.dump(history_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving history: {e}")
            
    def _set_model_text_delayed(self, model_widget, model_text):
        """Set the model text after a delay."""
        if isinstance(model_widget, QComboBox):
            model_widget.setCurrentText(model_text)
            
    def load_builtin_preset(self, preset_name):
        """Load a built-in preset configuration."""
        builtin_presets = {
            "Quick Comparison": {
                "run_groups": [
                    {"provider": "OpenAI", "model": "gpt-3.5-turbo", "runs": 1, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 1024},
                    {"provider": "Anthropic", "model": "claude-3-haiku-20240307", "runs": 1, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 1024},
                    {"provider": "Ollama", "model": "llama2", "runs": 1, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 1, "max_tokens": 1024}
                ],
                "judge": {"provider": "OpenAI", "model": "gpt-4", "prompt": "Default Judge Prompt"}
            },
            "Thorough Analysis": {
                "run_groups": [
                    {"provider": "OpenAI", "model": "gpt-4", "runs": 5, "temperature": 0.7, "delay": 2, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 2048},
                    {"provider": "Anthropic", "model": "claude-3-sonnet-20240229", "runs": 5, "temperature": 0.7, "delay": 2, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 2048},
                    {"provider": "OpenRouter", "model": "mistralai/mistral-7b-instruct", "runs": 5, "temperature": 0.7, "delay": 2, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 2048}
                ],
                "judge": {"provider": "OpenAI", "model": "gpt-4", "prompt": "Default Judge Prompt"}
            },
            "Budget Conscious": {
                "run_groups": [
                    {"provider": "Ollama", "model": "llama2", "runs": 3, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 1, "max_tokens": 1024},
                    {"provider": "LMStudio", "model": "local-model", "runs": 3, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 1, "max_tokens": 1024}
                ],
                "judge": {"provider": "Ollama", "model": "llama2", "prompt": "Default Judge Prompt"}
            }
        }
        
        if preset_name not in builtin_presets:
            return False
            
        preset_data = builtin_presets[preset_name]
        
        # Apply run groups
        run_groups_data = preset_data.get("run_groups", [])
        # Clear existing rows
        self.run_groups_table.setRowCount(0)
        # Add new rows
        for group_data in run_groups_data:
            self.add_run_group()
            row = self.run_groups_table.rowCount() - 1
            
            # Set values
            provider_widget = self.run_groups_table.cellWidget(row, 0)
            model_widget = self.run_groups_table.cellWidget(row, 1)
            runs_widget = self.run_groups_table.cellWidget(row, 2)
            temp_widget = self.run_groups_table.cellWidget(row, 3)
            delay_widget = self.run_groups_table.cellWidget(row, 4)
            retries_widget = self.run_groups_table.cellWidget(row, 5)
            backoff_widget = self.run_groups_table.cellWidget(row, 6)
            max_concurrent_widget = self.run_groups_table.cellWidget(row, 7)
            max_tokens_widget = self.run_groups_table.cellWidget(row, 8)
            
            if isinstance(provider_widget, QComboBox):
                provider_widget.setCurrentText(group_data.get("provider", ""))
            if isinstance(model_widget, QComboBox):
                model_widget.setCurrentText(group_data.get("model", ""))
            if isinstance(runs_widget, QSpinBox):
                runs_widget.setValue(group_data.get("runs", 1))
            if isinstance(temp_widget, QDoubleSpinBox):
                temp_widget.setValue(group_data.get("temperature", 0.7))
            if isinstance(delay_widget, QSpinBox):
                delay_widget.setValue(group_data.get("delay", 1))
            if isinstance(retries_widget, QSpinBox):
                retries_widget.setValue(group_data.get("retries", 3))
            if isinstance(backoff_widget, QDoubleSpinBox):
                backoff_widget.setValue(group_data.get("backoff_factor", 2.0))
            if isinstance(max_concurrent_widget, QSpinBox):
                max_concurrent_widget.setValue(group_data.get("max_concurrent", 5))
            if isinstance(max_tokens_widget, QSpinBox):
                max_tokens_widget.setValue(group_data.get("max_tokens", 1024))
                
            # Update models based on provider
            if isinstance(provider_widget, QComboBox):
                provider_text = provider_widget.currentText()
                model_text = group_data.get("model", "")
                # Populate models for the provider
                self.populate_models(row, provider_text)
                # Add a small delay to ensure model combo box is fully populated
                QTimer.singleShot(100, lambda mw=model_widget, mt=model_text: self._set_model_text_delayed(mw, mt))
                # Force update of the combo boxes
                provider_widget.update()
                if model_widget:
                    model_widget.update()
        
        # Apply judge configuration
        judge_data = preset_data.get("judge", {})
        self.judge_provider_combo.setCurrentText(judge_data.get("provider", ""))
        self.judge_model_combo.setCurrentText(judge_data.get("model", ""))
        self.judge_prompt_combo.setCurrentText(judge_data.get("prompt", ""))
        
        # Update judge models based on provider
        self.populate_judge_models(self.judge_provider_combo.currentText())
        # Set the judge model after populating
        self.judge_model_combo.setCurrentText(judge_data.get("model", ""))
        # Force update of the combo boxes
        self.judge_provider_combo.update()
        self.judge_model_combo.update()
        
        return True
    
    def load_preset(self):
        """Load a preset configuration."""
        # Define built-in presets
        builtin_presets = {
            "Quick Comparison": {
                "run_groups": [
                    {"provider": "OpenAI", "model": "gpt-3.5-turbo", "runs": 1, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 1024},
                    {"provider": "Anthropic", "model": "claude-3-haiku-20240307", "runs": 1, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 1024},
                    {"provider": "Ollama", "model": "llama2", "runs": 1, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 1, "max_tokens": 1024}
                ],
                "judge": {"provider": "OpenAI", "model": "gpt-4", "prompt": "Default Judge Prompt"}
            },
            "Thorough Analysis": {
                "run_groups": [
                    {"provider": "OpenAI", "model": "gpt-4", "runs": 5, "temperature": 0.7, "delay": 2, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 2048},
                    {"provider": "Anthropic", "model": "claude-3-sonnet-20240229", "runs": 5, "temperature": 0.7, "delay": 2, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 2048},
                    {"provider": "OpenRouter", "model": "mistralai/mistral-7b-instruct", "runs": 5, "temperature": 0.7, "delay": 2, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 5, "max_tokens": 2048}
                ],
                "judge": {"provider": "OpenAI", "model": "gpt-4", "prompt": "Default Judge Prompt"}
            },
            "Budget Conscious": {
                "run_groups": [
                    {"provider": "Ollama", "model": "llama2", "runs": 3, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 1, "max_tokens": 1024},
                    {"provider": "LMStudio", "model": "local-model", "runs": 3, "temperature": 0.7, "delay": 1, "retries": 3, "backoff_factor": 2.0, "max_concurrent": 1, "max_tokens": 1024}
                ],
                "judge": {"provider": "Ollama", "model": "llama2", "prompt": "Default Judge Prompt"}
            }
        }
        
        # Save built-in presets to files if they don't exist
        presets_dir = WWSettingsManager.get_project_path("brainstorm_presets")
        os.makedirs(presets_dir, exist_ok=True)
        
        for preset_name, preset_data in builtin_presets.items():
            preset_file = os.path.join(presets_dir, f"{preset_name}.json")
            if not os.path.exists(preset_file):
                try:
                    with open(preset_file, 'w') as f:
                        json.dump(preset_data, f, indent=2)
                except Exception as e:
                    print(f"Error saving built-in preset {preset_name}: {e}")
        
        # Get list of all preset files (including built-in ones)
        preset_files = []
        if os.path.exists(presets_dir):
            preset_files = [f for f in os.listdir(presets_dir) if f.endswith('.json')]
        
        if not preset_files:
            QMessageBox.information(self, "Load Preset", "No presets found.")
            return
            
        # Let user choose a preset
        preset_names = [os.path.splitext(f)[0] for f in preset_files]
        
        # Create a dialog with options to load, rename, or delete
        items = [f"{name}" for name in preset_names]
        item, ok = QInputDialog.getItem(self, "Load Preset", "Select preset:", items, 0, False)
        if not ok:
            return
            
        # Extract the preset name from the selected item
        preset_name = item.split(" (")[0]  # Remove any status text
        
        # Ask what action to perform
        actions = ["Load", "Rename", "Delete"]
        action, ok = QInputDialog.getItem(self, "Preset Action", "Choose action:", actions, 0, False)
        if not ok:
            return
            
        if action == "Delete":
            self.delete_preset(preset_name)
            # Refresh the preset list
            self.load_preset()
            return
        elif action == "Rename":
            self.rename_preset(preset_name)
            # Refresh the preset list
            self.load_preset()
            return
        elif action != "Load":
            return
            
        # Load preset data
        preset_file = os.path.join(presets_dir, f"{preset_name}.json")
        try:
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Load Preset", f"Error loading preset: {e}")
            return
            
        # Apply run groups
        run_groups_data = preset_data.get("run_groups", [])
        # Clear existing rows
        self.run_groups_table.setRowCount(0)
        # Add new rows
        for group_data in run_groups_data:
            self.add_run_group()
            row = self.run_groups_table.rowCount() - 1
            
            # Set values
            provider_widget = self.run_groups_table.cellWidget(row, 0)
            model_widget = self.run_groups_table.cellWidget(row, 1)
            runs_widget = self.run_groups_table.cellWidget(row, 2)
            temp_widget = self.run_groups_table.cellWidget(row, 3)
            delay_widget = self.run_groups_table.cellWidget(row, 4)
            retries_widget = self.run_groups_table.cellWidget(row, 5)
            backoff_widget = self.run_groups_table.cellWidget(row, 6)
            max_concurrent_widget = self.run_groups_table.cellWidget(row, 7)
            max_tokens_widget = self.run_groups_table.cellWidget(row, 8)
            
            if isinstance(provider_widget, QComboBox):
                provider_widget.setCurrentText(group_data.get("provider", ""))
            if isinstance(model_widget, QComboBox):
                model_widget.setCurrentText(group_data.get("model", ""))
            if isinstance(runs_widget, QSpinBox):
                runs_widget.setValue(group_data.get("runs", 1))
            if isinstance(temp_widget, QDoubleSpinBox):
                temp_widget.setValue(group_data.get("temperature", 0.7))
            if isinstance(delay_widget, QSpinBox):
                delay_widget.setValue(group_data.get("delay", 1))
            if isinstance(retries_widget, QSpinBox):
                retries_widget.setValue(group_data.get("retries", 3))
            if isinstance(backoff_widget, QDoubleSpinBox):
                backoff_widget.setValue(group_data.get("backoff_factor", 2.0))
            if isinstance(max_concurrent_widget, QSpinBox):
                max_concurrent_widget.setValue(group_data.get("max_concurrent", 5))
            if isinstance(max_tokens_widget, QSpinBox):
                max_tokens_widget.setValue(group_data.get("max_tokens", 1024))
                
            # Update models based on provider
            if isinstance(provider_widget, QComboBox):
                provider_text = provider_widget.currentText()
                model_text = group_data.get("model", "")
                # Populate models for the provider
                self.populate_models(row, provider_text)
                # Add a small delay to ensure model combo box is fully populated
                QTimer.singleShot(100, lambda mw=model_widget, mt=model_text: self._set_model_text_delayed(mw, mt))
                # Force update of the combo boxes
                provider_widget.update()
                if model_widget:
                    model_widget.update()
        
        # Apply judge configuration
        judge_data = preset_data.get("judge", {})
        self.judge_provider_combo.setCurrentText(judge_data.get("provider", ""))
        self.judge_model_combo.setCurrentText(judge_data.get("model", ""))
        self.judge_prompt_combo.setCurrentText(judge_data.get("prompt", ""))
        
        # Update judge models based on provider
        self.populate_judge_models(self.judge_provider_combo.currentText())
        # Set the judge model after populating
        self.judge_model_combo.setCurrentText(judge_data.get("model", ""))
        # Force update of the combo boxes
        self.judge_provider_combo.update()
        self.judge_model_combo.update()
        
        QMessageBox.information(self, "Load Preset", f"Preset '{preset_name}' loaded successfully.")
        
    def delete_preset(self, preset_name):
        """Delete a preset file."""
        presets_dir = WWSettingsManager.get_project_path("brainstorm_presets")
        preset_file = os.path.join(presets_dir, f"{preset_name}.json")
        
        # Confirm deletion
        reply = QMessageBox.question(self, "Delete Preset", f"Are you sure you want to delete preset '{preset_name}'?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if os.path.exists(preset_file):
                    os.remove(preset_file)
                    QMessageBox.information(self, "Delete Preset", f"Preset '{preset_name}' deleted successfully.")
                else:
                    QMessageBox.warning(self, "Delete Preset", f"Preset '{preset_name}' not found.")
            except Exception as e:
                QMessageBox.warning(self, "Delete Preset", f"Error deleting preset: {e}")
                
    def rename_preset(self, old_name):
        """Rename a preset file."""
        new_name, ok = QInputDialog.getText(self, "Rename Preset", "Enter new preset name:", text=old_name)
        if not ok or not new_name.strip():
            return
            
        new_name = new_name.strip()
        if new_name == old_name:
            return
            
        presets_dir = WWSettingsManager.get_project_path("brainstorm_presets")
        old_file = os.path.join(presets_dir, f"{old_name}.json")
        new_file = os.path.join(presets_dir, f"{new_name}.json")
        
        try:
            if os.path.exists(new_file):
                QMessageBox.warning(self, "Rename Preset", f"A preset with name '{new_name}' already exists.")
                return
                
            if os.path.exists(old_file):
                os.rename(old_file, new_file)
                QMessageBox.information(self, "Rename Preset", f"Preset '{old_name}' renamed to '{new_name}' successfully.")
            else:
                QMessageBox.warning(self, "Rename Preset", f"Preset '{old_name}' not found.")
        except Exception as e:
                QMessageBox.warning(self, "Rename Preset", f"Error renaming preset: {e}")
        
    def show_history(self):
        """Show the brainstorm history dialog."""
        # Get list of history files
        history_dir = WWSettingsManager.get_project_path("brainstorm_history")
        history_files = []
        if os.path.exists(history_dir):
            history_files = [f for f in os.listdir(history_dir) if f.startswith("history_") and f.endswith(".json")]
        
        if not history_files:
            QMessageBox.information(self, "History", "No history found.")
            return
            
        # Sort by timestamp (newest first)
        history_files.sort(reverse=True)
        
        # Create a simple dialog to show history items
        history_names = []
        history_data = {}
        
        for filename in history_files:
            try:
                filepath = os.path.join(history_dir, filename)
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Create a display name for the history item
                timestamp = data.get("timestamp", 0)
                prompt = data.get("prompt", "")[:50] + "..." if len(data.get("prompt", "")) > 50 else data.get("prompt", "")
                display_name = f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))} - {prompt}"
                history_names.append(display_name)
                history_data[display_name] = data
            except Exception as e:
                print(f"Error loading history file {filename}: {e}")
        
        if not history_names:
            QMessageBox.information(self, "History", "No valid history found.")
            return
            
        # Let user choose a history item
        history_name, ok = QInputDialog.getItem(self, "History", "Select history item:", history_names, 0, False)
        if not ok:
            return
            
        # Load the selected history item
        selected_data = history_data.get(history_name)
        if not selected_data:
            QMessageBox.warning(self, "History", "Error loading selected history item.")
            return
            
        # Show results in a dialog
        parent = self.parent()
        results = selected_data.get("results", [])
        judge_response = selected_data.get("judge_response", "")
        action_beats = selected_data.get("action_beats", "")
        extra_context = selected_data.get("extra_context", "")
        
        dialog = BrainstormResultsDialog(results, judge_response, extra_context, action_beats, parent)
        dialog.exec_()