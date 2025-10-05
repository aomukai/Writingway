import datetime
import logging
import re
from PyQt5.QtGui import QCursor, QPixmap
from muse.prompt_preview_dialog import PromptPreviewDialog
from settings.llm_worker import LLMWorker
from settings.llm_api_aggregator import WWApiAggregator
from .rag_pdf import PdfRagApp
from .chat_session import WritingCoachSession, RolePlaySession
from .workshop_model import WorkshopModel
from .workshop_view import WorkshopView
from .audio_utils import AudioRecorder, TranscriptionWorker

class WorkshopController:
    def __init__(self, parent=None):
        self.model = WorkshopModel(parent.model if parent else None)
        self.view = WorkshopView(parent, self)
        self.parent_controller = parent
        self.current_session = None
        self.worker = None
        self.is_streaming = False
        self.pre_stream_cursor_pos = None
        self.waiting_cursor = QCursor(QPixmap("assets/icons/clock.svg"))
        self.normal_cursor = QCursor()
        self.pdf_window = None
        self.connect_signals()
        self.load_conversations()
        if self.model.conversation_manager.last_viewed_chat:
            self.view.set_current_conversation_item(self.model.conversation_manager.last_viewed_chat)
            self.on_conversation_selection_changed()

    def connect_signals(self):
        self.view.new_chat_button.clicked.connect(self.new_conversation)
        self.view.conversation_list.itemSelectionChanged.connect(self.on_conversation_selection_changed)
        self.view.conversation_list.customContextMenuRequested.connect(self.show_conversation_context_menu)
        self.view.send_button.clicked.connect(self.on_send_or_stop)
        self.view.preview_button.clicked.connect(self.preview_prompt)
        self.view.context_button.clicked.connect(self.toggle_context_panel)
        self.view.pdf_rag_btn.clicked.connect(self.open_pdf_rag_tool)
        self.view.record_button.clicked.connect(self.toggle_recording)
        self.view.pause_button.clicked.connect(self.toggle_pause)
        self.view.recording_timer.timeout.connect(self.update_recording_time)
        self.view.zoom_in_shortcut.activated.connect(self.zoom_in)
        self.view.zoom_out_shortcut.activated.connect(self.zoom_out)
        if self.parent_controller and hasattr(self.parent_controller.model, "structureChanged"):
            self.parent_controller.model.structureChanged.connect(self.view.context_panel.on_structure_changed)

    def load_conversations(self):
        self.view.conversation_list.clear()
        for name in self.model.conversation_manager.get_conversation_names():
            mode = self.model.conversation_manager.get_mode(name)
            icon_path = self.model.conversation_manager.get_icon_path(mode)
            self.view.add_conversation_item(name, icon_path)

    def on_conversation_selection_changed(self):
        name = self.view.get_selected_conversation()
        if name:
            conv = self.model.conversation_manager.get_conversation(name)
            self.current_session = self.create_session(conv["mode"], conv["messages"])
            self.model.conversation_manager.set_last_viewed(name)
            self.update_chat_log()
            category = "Roleplay" if conv["mode"] == "Role Play" else "Workshop"
            self.view.prompt_panel.set_category(category)
            self.model.conversation_manager.save()

    def create_session(self, mode, messages):
        if mode == "Writing Coach":
            return WritingCoachSession(messages, self.view.context_panel, self.view.prompt_panel, self.model.embedding_index)
        elif mode == "Role Play":
            return RolePlaySession(messages, self.view.context_panel, self.view.prompt_panel, self.model.embedding_index)
        raise ValueError(f"Unknown mode: {mode}")

    def update_chat_log(self):
        self.view.clear_chat_log()
        for msg in self.current_session.messages:
            role = msg.get("role", "Unknown").capitalize()
            content = msg.get("content", "")
            self.view.append_to_chat_log(f"{role}: {content}\n")
        self.view.format_chat_log_html()

    def new_conversation(self):
        mode, name, pov = self.view.show_new_chat_dialog()
        if mode and name:
            try:
                self.model.conversation_manager.add_conversation(name, mode, pov)
                icon_path = self.model.conversation_manager.get_icon_path(mode)
                self.view.add_conversation_item(name, icon_path)
                self.view.set_current_conversation_item(name)
                self.model.conversation_manager.save()
            except ValueError as e:
                self.view.show_message_box(_("Error"), str(e))

    def generate_unique_chat_name(self):
        existing_numbers = [int(re.match(r'^Chat (\d+)$', name).group(1)) for name in self.model.conversation_manager.get_conversation_names() if re.match(r'^Chat (\d+)$', name)]
        number = max(existing_numbers, default=0) + 1
        return f"Chat {number}"

    def show_conversation_context_menu(self, pos):
        item = self.view.conversation_list.itemAt(pos)
        if item:
            from PyQt5.QtWidgets import QMenu
            menu = QMenu()
            rename_action = menu.addAction(_("Rename"))
            delete_action = menu.addAction(_("Delete"))
            action = menu.exec_(self.view.conversation_list.mapToGlobal(pos))
            if action == rename_action:
                self.rename_conversation(item)
            elif action == delete_action:
                self.delete_conversation(item)

    def rename_conversation(self, item):
        current_name = item.text()
        new_name, ok = self.view.show_rename_dialog(current_name)
        if ok:
            new_name = new_name.strip()
            if new_name and new_name != current_name:
                try:
                    self.model.conversation_manager.rename_conversation(current_name, new_name)
                    item.setText(new_name)
                    self.model.conversation_manager.save()
                except ValueError as e:
                    self.view.show_message_box(_("Invalid Name"), str(e))

    def delete_conversation(self, item):
        name = item.text()
        if self.view.show_delete_confirmation(name):
            row = self.view.conversation_list.row(item)
            self.view.remove_conversation_item(row)
            self.model.conversation_manager.delete_conversation(name)
            if not self.model.conversation_manager.conversations:
                self.new_conversation()  # Create default if empty
            self.model.conversation_manager.save()

    def on_send_or_stop(self):
        if self.is_streaming:
            self.stop_llm()
        else:
            self.send_message()

    def send_message(self):
        user_input = self.view.chat_input.toPlainText().strip()
        if not user_input or not self.current_session.validate():
            if not self.current_session.validate():
                self.view.show_message_box(_("Error"), _("Role Play mode requires at least one compendium character to be selected."))
            return
        payload = self.current_session.construct_message(user_input)
        if payload:
            self.current_session.append_message("user", user_input)
            self.view.append_to_chat_log(f"User: {user_input}\n")
            self.view.chat_input.clear()
            self.start_llm(payload)

    def start_llm(self, payload):
        overrides = self.view.prompt_panel.get_overrides()
        self.worker = LLMWorker(payload, overrides)
        self.worker.data_received.connect(self.handle_stream_data)
        self.worker.finished.connect(self.handle_stream_finished)
        self.worker.token_limit_exceeded.connect(self.handle_token_limit)
        self.worker.start()
        self.is_streaming = True
        self.view.set_send_button_icon("assets/icons/stop-circle.svg")
        self.pre_stream_cursor_pos = self.view.chat_log.textCursor().position()

    def handle_stream_data(self, data):
        cursor = self.view.chat_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(data)
        self.view.chat_log.setTextCursor(cursor)
        self.view.chat_log.ensureCursorVisible()

    def handle_stream_finished(self):
        if self.current_session:
            # Assume response is collected; in actual, collect from stream
            pass  # Placeholder for collecting full response
        self.cleanup_worker()
        self.is_streaming = False
        self.view.set_send_button_icon("assets/icons/send.svg")
        self.view.format_chat_log_html()
        self.model.conversation_manager.update_messages(self.model.conversation_manager.last_viewed_chat, self.current_session.messages)
        self.model.conversation_manager.save()

    def handle_token_limit(self):
        self.view.show_message_box(_("Token Limit"), _("Token limit exceeded."))

    def stop_llm(self):
        if self.worker:
            self.worker.stop()
        self.cleanup_worker()
        self.is_streaming = False
        self.view.set_send_button_icon("assets/icons/send.svg")
        self.view.format_chat_log_html()

    def cleanup_worker(self):
        if self.worker:
            self.worker.data_received.disconnect()
            self.worker.finished.disconnect()
            self.worker.token_limit_exceeded.disconnect()
            self.worker.deleteLater()
            self.worker = None
        provider_name = self.view.prompt_panel.get_overrides().get("provider") or WWSettingsManager.get_active_llm_name()
        provider = WWApiAggregator.aggregator.get_provider(provider_name)
        # Reset provider if needed

    def preview_prompt(self):
        if self.current_session:
            payload = self.current_session.get_preview_payload()
            if payload:
                dialog = PromptPreviewDialog(controller=self.parent_controller, conversation_payload=payload, parent=self.view)
                dialog.exec_()

    def toggle_context_panel(self):
        visible = not self.view.context_panel.isVisible()
        self.view.toggle_context_panel_visibility(visible)

    def open_pdf_rag_tool(self):
        self.pdf_window = PdfRagApp()
        self.pdf_window.show()

    def zoom_in(self):
        if self.view.font_size < 24:
            self.view.font_size += 2
            self.view.update_font_size()

    def zoom_out(self):
        if self.view.font_size > 8:
            self.view.font_size -= 2
            self.view.update_font_size()

    def toggle_recording(self):
        if not self.view.record_button.isChecked():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        import tempfile
        recording_file = tempfile.mktemp(suffix='.wav')
        self.view.recorder = AudioRecorder()
        self.view.recorder.setup_recording(recording_file)
        self.view.recorder.finished.connect(self.on_recording_finished)
        self.view.recorder.start()
        self.start_time = datetime.datetime.now()
        self.pause_start = None
        self.view.recording_timer.start(1000)
        self.view.set_pause_button_enabled(True)
        self.view.set_record_button_icon("assets/icons/stop-circle.svg")

    def stop_recording(self):
        if self.view.recorder:
            self.view.recorder.stop_recording()
        self.view.recording_timer.stop()
        self.view.set_pause_button_enabled(False)
        self.view.set_record_button_icon("assets/icons/mic.svg")
        self.view.set_time_label("00:00")

    def toggle_pause(self):
        if self.view.recorder.is_paused:
            self.view.recorder.resume()
            self.view.set_pause_button_icon("assets/icons/pause.svg")
            if self.pause_start:
                pause_duration = datetime.datetime.now() - self.pause_start
                self.start_time += pause_duration
                self.pause_start = None
        else:
            self.view.recorder.pause()
            self.view.set_pause_button_icon("assets/icons/play.svg")
            self.pause_start = datetime.datetime.now()

    def update_recording_time(self):
        if self.start_time and not self.view.recorder.is_paused:
            delta = datetime.datetime.now() - self.start_time
            if self.pause_start:
                delta -= datetime.datetime.now() - self.pause_start
            self.view.set_time_label(str(delta).split('.')[0])

    def on_recording_finished(self, file_path):
        self.view.set_override_cursor(self.waiting_cursor)
        language = None if self.view.language_combo.currentText() == "Auto" else self.view.language_combo.currentText()
        self.view.transcription_worker = TranscriptionWorker(file_path, self.view.model_combo.currentText(), language)
        self.view.transcription_worker.finished.connect(self.handle_transcription)
        self.view.transcription_worker.start()

    def handle_transcription(self, text):
        self.view.restore_cursor()
        if not text.startswith("Error"):
            current_text = self.view.chat_input.toPlainText()
            new_text = current_text + " " + text if current_text else text
            self.view.chat_input.setPlainText(new_text)
        else:
            self.view.show_message_box(_("Transcription Error"), text)

    def close_event_handler(self, event):
        self.stop_llm()
        self.model.conversation_manager.save()
        self.view.write_settings()
        event.accept()