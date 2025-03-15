# rewrite_feature.py
import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QComboBox,
    QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
from llm_api_aggregator import WWApiAggregator
from llm_worker import LLMWorker

def get_rewrite_prompts(project_name):
    """
    Load the 'Rewrite' prompts for the given project from its prompts JSON file.
    The file is assumed to be named as: prompts_<projectname_no_spaces>.json
    """
    prompts_file = "prompts.json"
    if os.path.exists(prompts_file):
        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("Rewrite", [])
        except Exception as e:
            print("Error loading rewrite prompts:", e)
    return []

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
        self.setWindowTitle("Rewrite Selected Text")
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Display original text.
        orig_label = QLabel("Original Text:")
        layout.addWidget(orig_label)
        self.orig_edit = QTextEdit()
        self.orig_edit.setPlainText(self.original_text)
        layout.addWidget(self.orig_edit)
        
        # Dropdown for selecting a rewrite prompt.
        prompt_layout = QHBoxLayout()
        prompt_label = QLabel("Select Rewrite Prompt:")
        prompt_layout.addWidget(prompt_label)
        self.prompt_combo = QComboBox()
        self.prompts = get_rewrite_prompts(self.project_name)
        if not self.prompts:
            QMessageBox.warning(self, "Rewrite", "No rewrite prompts found.")
        else:
            for p in self.prompts:
                self.prompt_combo.addItem(p.get("name", "Unnamed"))
        prompt_layout.addWidget(self.prompt_combo)
        layout.addLayout(prompt_layout)
        
        # Button to generate the rewrite.
        self.generate_button = QPushButton("Generate Rewrite")
        self.generate_button.clicked.connect(self.generate_rewrite)
        layout.addWidget(self.generate_button)
        
        # Display rewritten text.
        new_label = QLabel("Rewritten Text:")
        layout.addWidget(new_label)
        self.new_edit = QTextEdit()
        self.new_edit.setReadOnly(True)
        layout.addWidget(self.new_edit)
        
        # Control buttons.
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_rewrite)
        button_layout.addWidget(self.apply_button)
        self.retry_button = QPushButton("Generate")
        self.retry_button.clicked.connect(self.retry_rewrite)
        button_layout.addWidget(self.retry_button)
        self.cancel_button = QPushButton("Cancel")
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
            QMessageBox.warning(self, "Rewrite", "Selected prompt has no text.")
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
            self.worker.start()
        except Exception as e:
            QMessageBox.warning(self, "Rewrite", f"Error sending prompt to LLM: {e}")
            return

    
    def retry_rewrite(self):
        # Re-generate using the same selected prompt.
        self.generate_rewrite()
    
    def apply_rewrite(self):
        self.rewritten_text = self.new_edit.toPlainText()
        if not self.rewritten_text:
            QMessageBox.warning(self, "Rewrite", "No rewritten text to apply.")
            return
        self.accept()  # The caller can then retrieve self.rewritten_text.

def show_rewrite_button(parent, project_name, original_text, selection_rect, on_rewrite_applied):
    """
    Create and display a floating 'Rewrite' button near the selected text.

    Parameters:
      - parent: The parent widget (typically the text editor).
      - project_name: Name of the current project.
      - original_text: The text that was selected for rewriting.
      - selection_rect: A QRect indicating the bounding area of the selection, relative to the parent.
      - on_rewrite_applied: Callback function to call with the rewritten text once applied.
    """
    from PyQt5.QtWidgets import QPushButton
    from PyQt5.QtCore import QPoint

    # Create the floating button.
    rewrite_button = QPushButton("Rewrite", parent)
    rewrite_button.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
    rewrite_button.setStyleSheet("background-color: lightyellow; border: 1px solid gray;")
    
    # Determine the button's size hint.
    button_width = rewrite_button.sizeHint().width()
    button_height = rewrite_button.sizeHint().height()
    
    # Position the button near the top-right of the selection rectangle.
    x = selection_rect.right() - button_width
    y = selection_rect.top() - button_height if selection_rect.top() - button_height > 0 else selection_rect.bottom()
    rewrite_button.move(x, y)
    rewrite_button.show()

    def on_button_clicked():
        # Open the rewrite dialog when the button is clicked.
        dialog = RewriteDialog(project_name, original_text, parent)
        if dialog.exec_() == QDialog.Accepted:
            # Call the callback with the rewritten text if the user applied the change.
            on_rewrite_applied(dialog.rewritten_text)
        rewrite_button.hide()

    rewrite_button.clicked.connect(on_button_clicked)
    return rewrite_button
