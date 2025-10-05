import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QMessageBox, QInputDialog, QFormLayout,
    QSplitter, QWidget, QLabel, QApplication, QListWidget, QListWidgetItem, 
    QComboBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import QShortcut
from muse.prompt_panel import PromptPanel
from settings.theme_manager import ThemeManager
from compendium.context_panel import ContextPanel
from .new_chat_dialog import NewChatDialog

class WorkshopView(QDialog):
    def __init__(self, parent, workshop_controller):
        super().__init__(parent)
        self.setWindowTitle(_("Workshop"))
        self.controller = workshop_controller
        self.font_size = 12
        self.is_streaming = False
        self.pre_stream_cursor_pos = None
        self.recorder = None
        self.transcription_worker = None
        self.recording_timer = QTimer()
        self.available_models = self.get_available_models()
        self.init_ui()
        self.read_settings()

    def get_available_models(self):
        cache_dir = os.path.expanduser("~/.cache/whisper")
        models = [file.split(".")[0] for file in os.listdir(cache_dir) if file.endswith(".pt")] if os.path.exists(cache_dir) else ["tiny"]
        return models

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 10, 0)
        self.outer_splitter = QSplitter(Qt.Horizontal)
        conversation_container = QWidget()
        conversation_layout = QVBoxLayout(conversation_container)
        conversation_layout.setContentsMargins(0, 0, 0, 0)
        self.conversation_list = QListWidget()
        self.conversation_list.setContextMenuPolicy(Qt.CustomContextMenu)
        conversation_layout.addWidget(self.conversation_list)
        self.new_chat_button = QPushButton(_("New Chat"))
        conversation_layout.addWidget(self.new_chat_button)
        self.outer_splitter.addWidget(conversation_container)
        self.outer_splitter.setStretchFactor(0, 1)
        chat_panel = QWidget()
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setFont(QFont("Arial", self.font_size))
        chat_layout.addWidget(self.chat_log)
        self.inner_splitter = QSplitter(Qt.Horizontal)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText(_("Type your message here..."))
        self.chat_input.setFont(QFont("Arial", self.font_size))
        left_layout.addWidget(self.chat_input)
        bottomrow_layout = QHBoxLayout()
        self.prompt_panel = PromptPanel("Workshop")
        self.prompt_panel.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.prompt_panel.setMaximumWidth(300)
        bottomrow_layout.addWidget(self.prompt_panel)
        middle_stack = QFormLayout()
        button_row1 = QHBoxLayout()
        self.preview_button = QPushButton()
        self.preview_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/eye.svg"))
        self.preview_button.setToolTip(_("Preview the final prompt"))
        button_row1.addWidget(self.preview_button)
        self.send_button = QPushButton()
        self.send_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/send.svg"))
        button_row1.addWidget(self.send_button)
        button_row2 = QHBoxLayout()
        self.context_button = QPushButton()
        self.context_button.setCheckable(True)
        self.context_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/book-open.svg"))
        button_row2.addWidget(self.context_button)
        self.pdf_rag_btn = QPushButton()
        self.pdf_rag_btn.setIcon(ThemeManager.get_tinted_icon("assets/icons/file-text.svg"))
        self.pdf_rag_btn.setToolTip("Document Analysis (PDF/Images)")
        button_row2.addWidget(self.pdf_rag_btn)
        middle_stack.addRow(button_row1)
        middle_stack.addRow(button_row2)
        bottomrow_layout.addLayout(middle_stack)
        bottomrow_layout.addStretch()
        audio_stack = QFormLayout()
        audio_stack.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        audio_group_layout = QHBoxLayout()
        self.record_button = QPushButton()
        self.record_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/mic.svg"))
        self.record_button.setCheckable(True)
        audio_group_layout.addWidget(self.record_button)
        self.pause_button = QPushButton()
        self.pause_button.setIcon(ThemeManager.get_tinted_icon("assets/icons/pause.svg"))
        self.pause_button.setCheckable(True)
        self.pause_button.setEnabled(False)
        audio_group_layout.addWidget(self.pause_button)
        audio_group_layout.addStretch()
        self.time_label = QLabel("00:00")
        audio_group_layout.addWidget(self.time_label)
        audio_model_label = QLabel(_("Speech Model: "))
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.available_models)
        audio_lang_label = QLabel(_("Language: "))
        self.language_combo = QComboBox()
        self.language_combo.addItems(["Auto", "English", "Polish", "Spanish", "French", "German", "Italian", "Portuguese", "Russian", "Japanese", "Chinese", "Korean", "Dutch", "Arabic", "Hindi", "Swedish", "Czech", "Finnish", "Turkish", "Greek", "Ukrainian"])
        audio_stack.addRow(audio_group_layout)
        audio_stack.addRow(audio_model_label, self.model_combo)
        audio_stack.addRow(audio_lang_label, self.language_combo)
        bottomrow_layout.addItem(audio_stack)
        left_layout.addLayout(bottomrow_layout)
        self.inner_splitter.addWidget(left_container)
        self.context_panel = ContextPanel(self.parent().model.structure, self.parent().model.project_name, parent=self) if self.parent() else ContextPanel({}, "DefaultProject", parent=self)
        self.inner_splitter.addWidget(self.context_panel)
        self.inner_splitter.setSizes([500, 300])
        chat_layout.addWidget(self.inner_splitter)
        self.outer_splitter.addWidget(chat_panel)
        self.outer_splitter.setStretchFactor(1, 3)
        main_layout.addWidget(self.outer_splitter)
        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl+="), self)
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)

    def read_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        geometry = settings.value("workshop_window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.font_size = settings.value("workshop_window/fontSize", 12, type=int)
        outer_sizes = [int(s) for s in settings.value("workshop_window/outer_splitter", [200, 800])]
        inner_sizes = [int(s) for s in settings.value("workshop_window/inner_splitter", [500, 300])]
        self.update_font_size()
        self.outer_splitter.setSizes(outer_sizes)
        self.inner_splitter.setSizes(inner_sizes)

    def write_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue("workshop_window/geometry", self.saveGeometry())
        settings.setValue("workshop_window/fontSize", self.font_size)
        settings.setValue("workshop_window/outer_splitter", self.outer_splitter.sizes())
        settings.setValue("workshop_window/inner_splitter", self.inner_splitter.sizes())

    def update_font_size(self):
        self.chat_log.setFont(QFont("Arial", self.font_size))
        self.chat_input.setFont(QFont("Arial", self.font_size))

    def append_to_chat_log(self, text):
        self.chat_log.append(text)

    def format_chat_log_html(self):
        # Implement HTML formatting logic here if needed
        pass

    def clear_chat_log(self):
        self.chat_log.clear()

    def get_selected_conversation(self):
        items = self.conversation_list.selectedItems()
        return items[0].text() if items else None

    def add_conversation_item(self, name, icon_path):
        item = QListWidgetItem(name)
        item.setIcon(ThemeManager.get_tinted_icon(icon_path))
        self.conversation_list.addItem(item)

    def set_current_conversation_item(self, name):
        for i in range(self.conversation_list.count()):
            if self.conversation_list.item(i).text() == name:
                self.conversation_list.setCurrentRow(i)
                break

    def remove_conversation_item(self, row):
        self.conversation_list.takeItem(row)

    def show_message_box(self, title, message, icon=QMessageBox.Warning):
        QMessageBox(icon, title, message, parent=self).exec_()

    def show_new_chat_dialog(self):
        dialog = NewChatDialog(self.parent().model.project_name, self)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_selected_mode(), dialog.get_name(), dialog.get_pov()
        return None, None, None

    def show_rename_dialog(self, current_name):
        return QInputDialog.getText(self, _("Rename Conversation"), _("Enter new conversation name:"), text=current_name)

    def show_delete_confirmation(self, name):
        return QMessageBox.question(self, _("Delete Conversation"), _("Are you sure you want to delete '{}'?").format(name)) == QMessageBox.Yes

    def toggle_context_panel_visibility(self, visible):
        self.context_panel.setVisible(visible)
        icon = "assets/icons/book-open.svg" if visible else "assets/icons/book.svg"
        self.context_button.setIcon(ThemeManager.get_tinted_icon(icon))

    def set_send_button_icon(self, icon_path):
        self.send_button.setIcon(ThemeManager.get_tinted_icon(icon_path))

    def set_record_button_icon(self, icon_path):
        self.record_button.setIcon(ThemeManager.get_tinted_icon(icon_path))

    def set_pause_button_icon(self, icon_path):
        self.pause_button.setIcon(ThemeManager.get_tinted_icon(icon_path))

    def set_pause_button_enabled(self, enabled):
        self.pause_button.setEnabled(enabled)

    def set_time_label(self, time_str):
        self.time_label.setText(time_str)

    def set_override_cursor(self, cursor):
        QApplication.setOverrideCursor(cursor)

    def restore_cursor(self):
        QApplication.restoreOverrideCursor()

    def closeEvent(self, event):
        self.controller.close_event_handler(event)  # Delegate to controller