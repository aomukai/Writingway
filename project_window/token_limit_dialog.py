#!/usr/bin/env python3
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal
import tiktoken

class TokenLimitDialog(QDialog):
    """
    A dialog view for handling token limit errors when submitting prompts to an LLM.
    Allows the user to edit a summary, see real-time token counts, and choose an action.
    
    Signals:
        use_summary(str): Emitted when the user chooses to use the edited summary.
        truncate_story: Emitted when the user chooses to truncate the story.
    """
    
    use_summary = pyqtSignal(str)
    truncate_story = pyqtSignal()

    def __init__(self, error_message, initial_summary, max_tokens, encoding_name="cl100k_base", parent=None):
        """
        Initialize the dialog with the error message, initial summary, and token limit.

        Args:
            error_message (str): The error message from the LLM provider.
            initial_summary (str): The initial summary text to display for editing.
            max_tokens (int): The maximum token limit for the LLM.
            encoding_name (str): The tiktoken encoding to use (default: "cl100k_base").
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.error_message = error_message
        self.initial_summary = initial_summary
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding(encoding_name)
        self.init_ui()

    def init_ui(self):
        """Set up the dialog's user interface."""
        self.setWindowTitle(_("Token Limit Exceeded"))
        self.resize(500, 400)

        # Main layout
        layout = QVBoxLayout(self)

        # Error message
        error_label = QLabel(_("Error: {}").format(self.error_message) + _("\nThe story is too long. Please edit the summary below:"))
        error_label.setWordWrap(True)
        layout.addWidget(error_label)

        # Summary editor
        self.summary_editor = QTextEdit(self.initial_summary)
        self.summary_editor.textChanged.connect(self.update_token_count)
        layout.addWidget(self.summary_editor)

        # Buttons
        button_layout = QHBoxLayout()
        self.use_button = QPushButton(_("Use This Summary"))
        self.use_button.clicked.connect(self.on_use_summary)
        self.truncate_button = QPushButton(_("Truncate Story"))
        self.truncate_button.clicked.connect(self.on_truncate_story)
        button_layout.addStretch()
        button_layout.addWidget(self.use_button)
        button_layout.addWidget(self.truncate_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Token count display
        self.token_label = QLabel(_("Tokens: Calculating..."))
        self.token_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.token_label)

        # Initial token count update
        self.update_token_count()

    def update_token_count(self):
        """Update the token count display based on the current text."""
        text = self.summary_editor.toPlainText()
        tokens = len(self.encoding.encode(text))
        self.token_label.setText(_("Tokens: {}/{}"). format(tokens, self.max_tokens))
        # Optional: Highlight if over limit
        if tokens > self.max_tokens:
            self.token_label.setStyleSheet("color: red;")
            self.use_button.setEnabled(False)
        else:
            self.token_label.setStyleSheet("")
            self.use_button.setEnabled(True)

    def on_use_summary(self):
        """Handle the 'Use This Summary' button click."""
        summary = self.summary_editor.toPlainText().strip()
        if summary:
            self.use_summary.emit(summary)
            self.accept()
        else:
            QMessageBox.warning(self, _("Empty Summary"), _("Please provide a summary before proceeding."))

    def on_truncate_story(self):
        """Handle the 'Truncate Story' button click."""
        self.truncate_story.emit()
        self.accept()

    def get_summary(self):
        """Return the current summary text (for testing or direct access)."""
        return self.summary_editor.toPlainText().strip()


# Example usage (for testing standalone)
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    dialog = TokenLimitDialog(
        error_message="Prompt exceeds 4096 tokens",
        initial_summary="This is a long story that needs summarizing...",
        max_tokens=2000
    )
    dialog.use_summary.connect(lambda text: print(f"Using summary: {text}"))
    dialog.truncate_story.connect(lambda: print("Truncating story"))
    dialog.exec_()
    sys.exit(app.exec_())
