from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QHBoxLayout, QTextEdit, QLabel
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import QShortcut
from settings.theme_manager import ThemeManager
import muse.prompt_handler as prompt_handler
import tiktoken

class PromptPreviewDialog(QDialog):
    def __init__(self, controller, conversation_payload=None, prompt_config=None, user_input=None, 
                 additional_vars=None, current_scene_text=None, extra_context=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Prompt Preview"))
        self.resize(600, 400)
        self.controller = controller
        self.conversation_payload = conversation_payload
        self.prompt_config = prompt_config
        self.user_input = user_input
        self.additional_vars = additional_vars
        self.current_scene_text = current_scene_text
        self.extra_context = extra_context
        self.font_size = 12  # Default font size in points
        self.final_prompt_text = ""  # Store final prompt text for token counting
        self.init_ui()
        self.read_settings()
        self.update_token_count()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Tree widget for collapsible sections
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)  # Column 0 for header, Column 1 for content widget
        self.tree.setColumnWidth(0, 200)  # Fixed width for headers
        self.populate_tree()
        layout.addWidget(self.tree)

        # Buttons and zoom controls
        button_layout = QHBoxLayout()
        self.zoom_in_button = QPushButton()
        self.zoom_in_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/zoom-in.svg", self.controller.icon_tint))
        self.zoom_in_button.setToolTip(_("Zoom In (Cmd+=)"))
        self.zoom_in_button.clicked.connect(self.zoom_in)

        self.zoom_out_button = QPushButton()
        self.zoom_out_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/zoom-out.svg", self.controller.icon_tint))
        self.zoom_out_button.setToolTip(_("Zoom Out (Cmd+-)"))
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.ok_button = QPushButton(_("OK"))
        self.ok_button.clicked.connect(self.ok_button_clicked)

        button_layout.addWidget(self.zoom_in_button)
        button_layout.addWidget(self.zoom_out_button)

        # Token count label (centered)
        self.token_count_label = QLabel(_("Token Count: 0"))
        self.token_count_label.setFont(QFont("Arial", self.font_size))
        self.token_count_label.setAlignment(Qt.AlignCenter)  # Center the text
        button_layout.addStretch()  # Add stretch before to push label to center
        button_layout.addWidget(self.token_count_label)
        button_layout.addStretch()  # Add stretch after to center the label

        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)

        # Shortcuts for zoom
        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl+="), self)
        self.zoom_in_shortcut.activated.connect(self.zoom_in)
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        self.zoom_out_shortcut.activated.connect(self.zoom_out)

        # Apply initial font size
        self.update_font_size()

    def populate_tree(self):
        """Populate the tree with collapsible sections."""
        if self.conversation_payload:
            sections = self.parse_conversation_payload()
        else:
            self.final_prompt_text = prompt_handler.preview_final_prompt(
                self.prompt_config, self.user_input, self.additional_vars,
                self.current_scene_text, self.extra_context
            )
            sections = self.parse_prompt_sections(self.final_prompt_text)

        for header, content in sections.items():
            # Create a top-level item for the header
            header_item = QTreeWidgetItem(self.tree)
            header_item.setText(0, header)
            header_item.setFont(0, QFont("Arial", self.font_size, QFont.Bold))

            # Create a child item to hold the QTextEdit
            content_item = QTreeWidgetItem(header_item)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(content)
            text_edit.setFont(QFont("Arial", self.font_size))
            text_edit.setStyleSheet("QTextEdit { border: 1px solid #ccc; padding: 4px; }")  # Add boundary box
            self.tree.setItemWidget(content_item, 1, text_edit)

            # Collapse if content is long (>300 chars)
            if len(content.strip()) > 300:
                header_item.setExpanded(False)
            else:
                header_item.setExpanded(True)

        # Adjust tree after adding widgets
        self.tree.expandAll()  # Expand all initially, then collapse long sections
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            text_edit = self.tree.itemWidget(item.child(0), 1)
            content_length = len(text_edit.toPlainText().strip())
            maxheight = min(max(2, int(content_length / 50)), 50) * 30
            text_edit.setMaximumHeight(maxheight)  # Ensure visibility

            if content_length > 300:
                item.setExpanded(False)
            # Resize the content column to fit the widget
            self.tree.resizeColumnToContents(1)

    def parse_conversation_payload(self):
        """Parse the conversation payload into sections based on message roles."""
        sections = {}
        self.final_prompt_text = ""

        for i, message in enumerate(self.conversation_payload):
            role = message.get("role", "unknown").capitalize()
            content = message.get("content", "")
            header = f"{role} Message {i + 1}"
            sections[header] = content
            self.final_prompt_text += content + "\n"

        if not sections:
            sections["Empty"] = "No content available"

        return sections

    def parse_prompt_sections(self, prompt_text):
        """Parse the prompt text into sections based on ### headers."""
        sections = {}
        current_header = None
        current_content = []
        
        for line in prompt_text.splitlines():
            if line.strip().startswith("###"):
                if current_header and current_content:
                    sections[current_header] = "\n".join(current_content).strip()
                current_header = line.strip().replace("###", "").strip()
                current_content = []
            elif current_header:
                current_content.append(line)
        
        if current_header and current_content:
            sections[current_header] = "\n".join(current_content).strip()
        
        if not sections:
            sections["Prompt"] = prompt_text.strip()
        
        return sections

    def zoom_in(self):
        """Increase font size."""
        if self.font_size < 24:  # Arbitrary max size
            self.font_size += 2
            self.update_font_size()

    def zoom_out(self):
        """Decrease font size."""
        if self.font_size > 8:  # Arbitrary min size
            self.font_size -= 2
            self.update_font_size()

    def update_font_size(self):
        """Apply the current font size to all tree items and widgets."""
        for i in range(self.tree.topLevelItemCount()):
            header_item = self.tree.topLevelItem(i)
            header_item.setFont(0, QFont("Arial", self.font_size, QFont.Bold))
            content_widget = self.tree.itemWidget(header_item.child(0), 1)
            if content_widget:
                content_widget.setFont(QFont("Arial", self.font_size))
        # Update token count label font size
        self.token_count_label.setFont(QFont("Arial", self.font_size))

    def update_token_count(self):
        """Calculate and display the token count using tiktoken."""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")  # Use a common encoding, e.g., for GPT models
            tokens = encoding.encode(self.final_prompt_text)
            token_count = len(tokens)
            self.token_count_label.setText(_("Token Count: {}").format(token_count))
        except Exception as e:
            self.token_count_label.setText(_("Token Count: Error ({})").format(str(e)))

    def read_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        geometry = settings.value("prompt_preview/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        # Load font size, default to 12 if not set
        self.font_size = settings.value("prompt_preview/fontSize", 12, type=int)
        self.update_font_size()  # Apply the loaded font size

    def write_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue("prompt_preview/geometry", self.saveGeometry())
        settings.setValue("prompt_preview/fontSize", self.font_size)  # Save font size

    def closeEvent(self, event):
        self.write_settings()
        event.accept()

    def ok_button_clicked(self):
        self.write_settings()
        self.accept()