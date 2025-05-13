#!/usr/bin/env python3
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QHBoxLayout, QLabel, QMessageBox

class CreateSummaryDialog(QDialog):
    def __init__(self, default_prompt, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Create Summary"))
        self.prompt = ""
        self.init_ui(default_prompt)
        
    def init_ui(self, default_prompt):
        layout = QVBoxLayout(self)
        label = QLabel(_("Edit summarizer prompt:"))
        layout.addWidget(label)
        self.prompt_edit = QLineEdit(default_prompt)
        layout.addWidget(self.prompt_edit)
        button_layout = QHBoxLayout()
        ok_button = QPushButton(_("Okay"))
        cancel_button = QPushButton(_("Cancel"))
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
    def accept(self):
        self.prompt = self.prompt_edit.text().strip()
        if not self.prompt:
            QMessageBox.warning(self, _("Input Error"), _("The summarizer prompt cannot be empty."))
            return
        super().accept()
