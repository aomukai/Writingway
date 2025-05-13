# rewrite_feature.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QComboBox,
    QPushButton, QMessageBox
)
from muse.prompt_utils import load_prompts
from settings.llm_worker import LLMWorker

class RewriteDialog(QDialog):
    """
    A dialog for rewriting a selected passage.
    
    Features:
      - Displays the original (read-only) text.
      - Provides a dropdown list of available rewrite prompts.
      - A "Generate Rewrite" button sends the selected prompt and the original passage to the LLM.
      - Displays the rewritten text for comparison.
      - "Generate" allows re-generation with the same prompt.
      - "Apply" confirms the change (the dialog is accepted) so the caller can replace the selected text.
    """
    def __init__(self, project_name, original_text, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.original_text = original_text
        self.rewritten_text = ""
        self.worker = None
        self.setWindowTitle(_("Rewrite Selected Text"))
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Display original text.
        orig_label = QLabel(_("Original Text:"))
        layout.addWidget(orig_label)
        self.orig_edit = QTextEdit()
        self.orig_edit.setPlainText(self.original_text)
        layout.addWidget(self.orig_edit)
        
        # Dropdown for selecting a rewrite prompt.
        prompt_layout = QHBoxLayout()
        prompt_label = QLabel(_("Select Rewrite Prompt:"))
        prompt_layout.addWidget(prompt_label)
        self.prompt_combo = QComboBox()
        self.prompts = load_prompts("Rewrite")
        if not self.prompts:
            QMessageBox.warning(self, _("Rewrite"), _("No rewrite prompts found."))
        else:
            for p in self.prompts:
                self.prompt_combo.addItem(p.get("name", "Unnamed"))
        prompt_layout.addWidget(self.prompt_combo)
        layout.addLayout(prompt_layout)
        
        # Button to generate the rewrite.
        self.generate_button = QPushButton(_("Generate Rewrite"))
        self.generate_button.clicked.connect(self.generate_rewrite)
        layout.addWidget(self.generate_button)
        
        # Display rewritten text.
        new_label = QLabel(_("Rewritten Text:"))
        layout.addWidget(new_label)
        self.new_edit = QTextEdit()
        self.new_edit.setReadOnly(True)
        layout.addWidget(self.new_edit)
        
        # Control buttons.
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton(_("Apply"))
        self.apply_button.clicked.connect(self.apply_rewrite)
        button_layout.addWidget(self.apply_button)
        self.retry_button = QPushButton(_("Generate"))
        self.retry_button.clicked.connect(self.retry_rewrite)
        button_layout.addWidget(self.retry_button)
        self.cancel_button = QPushButton(_("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def update_text(self, text):
        self.new_edit.insertPlainText(text)

    def on_finished(self):
        pass
    
    def generate_rewrite(self):
        # Get the selected prompt's text.
        if not self.prompts:
            return
        index = self.prompt_combo.currentIndex()
        prompt_data = self.prompts[index]
        prompt_text = prompt_data.get("text", "")
        if not prompt_text:
            QMessageBox.warning(self, _("Rewrite"), _("Selected prompt has no text."))
            return
        
        self.new_edit.clear()  # Clear previous rewritten text.

        # Construct final prompt.
        final_prompt = f"{prompt_text}\n\nOriginal Passage:\n{self.orig_edit.toPlainText()}"
        
        # Build the overrides dictionary to force local LLM usage.
        overrides = {
            "provider": prompt_data.get("provider", "Local"),
            "model": prompt_data.get("model", "Local Model"),
            "max_tokens": prompt_data.get("max_tokens", 2000),
            "temperature": prompt_data.get("temperature", 1.0)
        }
        
        try:
            self.worker = LLMWorker(final_prompt, overrides)
            self.worker.data_received.connect(self.update_text)
            self.worker.finished.connect(self.on_finished)
            self.worker.finished.connect(self.cleanup_worker)  # Schedule thread deletion
            self.worker.start()
        except Exception as e:
            QMessageBox.warning(self, _("Rewrite"), _("Error sending prompt to LLM: {}").format(str(e)))
            return

    
    def retry_rewrite(self):
        # Re-generate using the same selected prompt.
        self.generate_rewrite()
    
    def apply_rewrite(self):
        self.rewritten_text = self.new_edit.toPlainText()
        if not self.rewritten_text:
            QMessageBox.warning(self, _("Rewrite"), _("No rewritten text to apply."))
            return
        self.accept()  # The caller can then retrieve self.rewritten_text.

    def cleanup_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.wait()  # Wait for the thread to fully stop
        if self.worker:
            try:
                self.worker.data_received.disconnect()
                self.worker.finished.disconnect()
            except TypeError:
                pass  # Signals may already be disconnected
            self.worker.deleteLater()  # Schedule deletion
            self.worker = None  # Clear reference

