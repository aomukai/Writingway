import os
import time
import json
import tiktoken
import re
import logging
import threading

from PyQt5.QtWidgets import (QMainWindow, QSplitter, QLabel, QShortcut, 
                             QMessageBox, QInputDialog, QApplication, QDialog,
                             QTreeWidgetItem)
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSlot
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QTextCursor, QKeySequence
from .project_model import ProjectModel
from .global_toolbar import GlobalToolbar
from .project_tree_widget import ProjectTreeWidget
from .scene_editor import SceneEditor
from .bottom_stack import BottomStack
from .focus_mode import FocusMode
from .rewrite_feature import RewriteDialog
from util.tts_manager import WW_TTSManager
from compendium.compendium_panel import CompendiumPanel
from settings.backup_manager import show_backup_dialog
from settings.llm_api_aggregator import WWApiAggregator
from settings.llm_worker import LLMWorker
from settings.settings_manager import WWSettingsManager
from settings.theme_manager import ThemeManager
from workshop.workshop import WorkshopWindow
from util.text_analysis_gui import TextAnalysisApp
from util.web_llm import MainWindow
from util.whisper_app import WhisperApp
from util.ia_window import IAWindow
from muse.prompts_window import PromptsWindow
from .token_limit_dialog import TokenLimitDialog
from gettext import pgettext
import muse.prompt_handler as prompt_handler

# Set the path to PyQt5 plugins
import PyQt5
pyqt_dir = os.path.dirname(PyQt5.__file__)
possible_paths = [
    os.path.join(pyqt_dir, "Qt5", "plugins", "platforms"),
    os.path.join(pyqt_dir, "Qt", "plugins", "platforms")
]
plugin_path = ""
for path in possible_paths:
    if os.path.exists(path) and os.listdir(path):
        plugin_path = path
        break
if plugin_path:
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path


class ProjectWindow(QMainWindow):
    def __init__(self, project_name, compendium_window):
        super().__init__()
        self.model = ProjectModel(project_name)
        self.current_theme = WWSettingsManager.get_appearance_settings()["theme"]
        self.icon_tint = QColor(ThemeManager.ICON_TINTS.get(self.current_theme, "black"))
        self.tts_playing = False
        self.unsaved_preview = False
        self.enhanced_window = compendium_window
        self.worker = None
        self.init_ui()
        self.setup_connections()
        self.read_settings()
        self.load_initial_state()
        self.enhanced_window.compendium_updated.connect(self.on_compendium_updated)

        # Restore the toolbar if the user invoked toggleViewAction and saved the settings
        # If we prevent the user from hiding the toolbar, this will be redundant (but harmless)
        self.global_toolbar.toolbar.show()

    def init_ui(self):
        self.setWindowTitle(_("Project: {}").format(self.model.project_name))
        self.resize(900, 600)

        # Status Bar
        self.setup_status_bar()

        # UI Components
        self.global_toolbar = GlobalToolbar(self, self.icon_tint)
        self.addToolBar(self.global_toolbar.toolbar)

        main_splitter = QSplitter(Qt.Horizontal)
        self.project_tree = ProjectTreeWidget(self, self.model)
        main_splitter.addWidget(self.project_tree)

        right_vertical_splitter = QSplitter(Qt.Vertical)
        top_horizontal_splitter = QSplitter(Qt.Horizontal)
        self.compendium_panel = CompendiumPanel(self)
        self.compendium_panel.setVisible(False)
        top_horizontal_splitter.addWidget(self.compendium_panel)
        self.scene_editor = SceneEditor(self, self.icon_tint)
        top_horizontal_splitter.addWidget(self.scene_editor)
        top_horizontal_splitter.setStretchFactor(0, 1)  # Compendium
        top_horizontal_splitter.setStretchFactor(1, 3)  # Editor

        self.bottom_stack = BottomStack(self, self.model, self.icon_tint)
        self.bottom_stack.preview_text.textChanged.connect(self.on_preview_text_changed)
        right_vertical_splitter.addWidget(top_horizontal_splitter)
        right_vertical_splitter.addWidget(self.bottom_stack)
        right_vertical_splitter.setStretchFactor(0, 3)
        right_vertical_splitter.setStretchFactor(1, 1)

        main_splitter.addWidget(right_vertical_splitter)
        main_splitter.setStretchFactor(0, 1)  # Tree
        main_splitter.setStretchFactor(1, 3)  # Right Side
        self.main_splitter = main_splitter
        self.setCentralWidget(main_splitter)

    def setup_status_bar(self):
        self.setStatusBar(self.statusBar())
        self.word_count_label = QLabel(_("Words: {}").format(0))
        self.last_save_label = QLabel(_("Last Saved: {}").format("Never"))
        self.statusBar().addPermanentWidget(self.word_count_label)
        self.statusBar().addPermanentWidget(self.last_save_label)

    def setup_connections(self):
        self.focus_mode_shortcut = QShortcut(QKeySequence("F11"), self)
        self.focus_mode_shortcut.activated.connect(self.open_focus_mode)

    def on_compendium_updated(self, project_name):
        if project_name == self.model.project_name:
            current_pov = self.bottom_stack.pov_character_combo.currentText() if self.bottom_stack.pov_character_combo else ""
            self.update_pov_character_dropdown()
            if self.bottom_stack.pov_character_combo:
                self.restore_pov_character(current_pov)
                if self.bottom_stack.pov_character_combo.currentText() != current_pov:
                    self.handle_pov_character_change()

    def load_initial_state(self):
        self.bottom_stack.pov_combo.setCurrentText(self.model.settings["global_pov"])
        self.bottom_stack.pov_character_combo.setCurrentText(self.model.settings["global_pov_character"])
        self.bottom_stack.tense_combo.setCurrentText(self.model.settings["global_tense"])
        self.update_pov_character_dropdown()
        self.bottom_stack.prompt_input.setPlainText(self.load_prompt_input())
        if self.model.autosave_enabled:
            self.start_autosave_timer()
        if self.project_tree.tree.topLevelItemCount() > 0:
            act_item = self.project_tree.tree.topLevelItem(0)
            if act_item.childCount() > 0:
                chapter_item = act_item.child(0)
                if chapter_item.childCount() > 0:
                    self.project_tree.tree.setCurrentItem(chapter_item.child(0))

    def start_autosave_timer(self):
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(300000)  # 5 minutes
        self.autosave_timer.timeout.connect(self.autosave_scene)
        self.autosave_timer.start()

    def read_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        geometry = settings.value(f"{self.model.project_name}/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        windowState = settings.value(f"{self.model.project_name}/windowState")
        if windowState:
            self.restoreState(windowState)
        if hasattr(self, "main_splitter"):
            main_splitter_state = settings.value(f"{self.model.project_name}/mainSplitterState")
            if main_splitter_state:
                self.main_splitter.restoreState(main_splitter_state)
        if hasattr(self, "project_tree"):
            treeHeaderState = settings.value(f"{self.model.project_name}/treeHeaderState")
            if treeHeaderState:
                self.project_tree.tree.header().restoreState(treeHeaderState)

    def write_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue(f"{self.model.project_name}/geometry", self.saveGeometry())
        settings.setValue(f"{self.model.project_name}/windowState", self.saveState())
        if hasattr(self, "main_splitter"):
            settings.setValue(f"{self.model.project_name}/mainSplitterState", self.main_splitter.saveState())
        if hasattr(self, "project_tree"):
            settings.setValue(f"{self.model.project_name}/treeHeaderState", self.project_tree.tree.header().saveState())

    def closeEvent(self, event):
        if not self.check_unsaved_changes():
            event.ignore()
            return
        # Stop the autosave timer if it exists and is running
        if hasattr(self, 'autosave_timer') and self.autosave_timer.isActive():
            self.autosave_timer.stop()
        self.write_settings()
        event.accept()

    # This used to ask if you want to save. Now it just autosaves.
    def check_unsaved_changes(self, item=None):
        if self.model.unsaved_changes:
            self.autosave_scene(item)
        if self.unsaved_preview:
            self.autosave_preview()
        return True

    @pyqtSlot(QTreeWidgetItem, QTreeWidgetItem)
    def tree_item_changed(self, current, previous):
        if not current:
            self.scene_editor.editor.clear()
            self.bottom_stack.stack.setCurrentIndex(0)
            return
        if previous:
            self.check_unsaved_changes(previous)
        self.load_current_item_content()
        self.model.unsaved_changes = False
        self.unsaved_preview = False


    def load_current_item_content(self):
        current = self.project_tree.tree.currentItem()
        if not current:
            return
        level = self.project_tree.get_item_level(current)
        editor = self.scene_editor.editor
        hierarchy = self.get_item_hierarchy(current)
        if level >= 2:  # Scene
            content = self.model.load_scene_content(hierarchy)
            if content and content.lstrip().startswith("<"):
                editor.setHtml(content)
            else:
                editor.setPlainText(content)
            editor.setPlaceholderText(_("Enter scene content..."))
            self.bottom_stack.stack.setCurrentIndex(1)
        else:  # Summary
            content = self.model.load_summary(hierarchy)
            if content and content.lstrip().startswith("<"):
                editor.setHtml(content)
            else:
                editor.setPlainText(content)
            editor.setPlaceholderText(_("Enter summary for {}...").format(current.text(0)))
            self.bottom_stack.stack.setCurrentIndex(0)
        self.update_setting_tooltips()
        # Force update toolbar state after loading content
        self.scene_editor.update_toolbar_state()

    def get_item_hierarchy(self, item):
        hierarchy = []
        current = item
        while current:
            hierarchy.insert(0, current.text(0).strip())
            current = current.parent()
        return hierarchy

    def set_scene_status(self, item, new_status):
        scene_data = item.data(0, Qt.UserRole) or {"name": item.text(0)}
        scene_data["status"] = new_status
        item.setData(0, Qt.UserRole, scene_data)
        self.project_tree.assign_item_icon(item, self.project_tree.get_item_level(item))  # Update icon
        self.model.update_structure(self.project_tree.tree)

    def manual_save_scene(self):
        current_item = self.project_tree.tree.currentItem()
        if not current_item or self.project_tree.get_item_level(current_item) < 2:
            QMessageBox.warning(self, _("Manual Save"), _("Please select a scene for manual save."))
            return
        content = self.scene_editor.editor.toHtml()
        if not content.strip():
            QMessageBox.warning(self, _("Manual Save"), _("There is no content to save."))
            return
        hierarchy = self.get_item_hierarchy(current_item)
        filepath = self.model.save_scene(hierarchy, content)
        if filepath:
            self.update_save_status(_("Scene manually saved"))
            self.model.unsaved_changes = False

    def autosave_scene(self, current_item=None):
        if not current_item:
            current_item = self.project_tree.tree.currentItem()
        if not current_item or self.project_tree.get_item_level(current_item) < 2:
            return
        content = self.scene_editor.editor.toHtml()
        if not content.strip():
            return
        hierarchy = self.get_item_hierarchy(current_item)
        filepath = self.model.save_scene(hierarchy, content, expected_project_name=self.model.project_name)
        if filepath:
            self.update_save_status(_("Scene autosaved"))
            self.model.unsaved_changes = False


    def update_save_status(self, message):
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.last_save_label.setText(_("Last Saved: {}").format(now))
        self.statusBar().showMessage(message, 3000)

    # This function is a placeholder for the autosave preview feature.
    # Currently the preview remains even if you navigate away from the scene.
    def autosave_preview(self):
        pass

    def on_oh_shit(self):
        current_item = self.project_tree.tree.currentItem()
        if not current_item or self.project_tree.get_item_level(current_item) < 2:
            QMessageBox.warning(self, _("Backup Versions"), _("Please select a scene to view backups."))
            return
        backup_file_path = show_backup_dialog(self, self.model.project_name, current_item.text(0))
        if backup_file_path:
            with open(backup_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            editor = self.scene_editor.editor
            if backup_file_path.endswith(".html"):
                editor.setHtml(content)
            else:
                editor.setPlainText(content)
            QMessageBox.information(self, _("Backup Loaded"), _("Backup loaded from:\n{}").format(backup_file_path))

    def handle_pov_change(self, index):
        value = self.bottom_stack.pov_combo.currentText()
        if value == _("Custom..."):
            custom, ok = QInputDialog.getText(self, _("Custom POV"), _("Enter custom POV:"), text=self.model.settings["global_pov"])
            if ok and custom.strip():
                value = custom.strip()
                combo = self.bottom_stack.pov_combo
                if combo.findText(value) == -1:
                    combo.blockSignals(True)  # Block signals
                    combo.insertItem(0, value)
                    combo.setCurrentText(value)  # Set the new value
                    combo.blockSignals(False)  # Unblock signals
                else:
                    combo.blockSignals(True)
                    combo.setCurrentText(value)
                    combo.blockSignals(False)
            else:
                combo = self.bottom_stack.pov_combo
                combo.blockSignals(True)
                combo.setCurrentText(self.model.settings["global_pov"])
                combo.blockSignals(False)
                return
        self.model.settings["global_pov"] = value
        self.update_setting_tooltips()
        self.model.save_settings()

    def handle_pov_character_change(self, index=0):
        value = self.bottom_stack.pov_character_combo.currentText()
        if value == _("Custom..."):
            custom, ok = QInputDialog.getText(self, _("Custom POV Character"), _("Enter custom POV Character:"), text=self.model.settings["global_pov_character"])
            if ok and custom.strip():
                value = custom.strip()
                combo = self.bottom_stack.pov_character_combo
                if combo.findText(value) == -1:
                    combo.blockSignals(True)  # Block signals
                    combo.insertItem(0, value)
                    combo.setCurrentText(value)  # Set the new value
                    combo.blockSignals(False)  # Unblock signals
                else:
                    combo.blockSignals(True)
                    combo.setCurrentText(value)
                    combo.blockSignals(False)
            else:
                combo = self.bottom_stack.pov_character_combo
                combo.blockSignals(True)
                combo.setCurrentText(self.model.settings["global_pov_character"])
                combo.blockSignals(False)
                return
        self.model.settings["global_pov_character"] = value
        self.update_setting_tooltips()
        self.model.save_settings()

    def handle_tense_change(self, index):
        value = self.bottom_stack.tense_combo.currentText()
        if value == _("Custom..."):
            custom, ok = QInputDialog.getText(self, pgettext("verb_tense", "Custom Tense"), pgettext("verb_tense", "Enter custom Tense:"), text=self.model.settings["global_tense"])
            if ok and custom.strip():
                value = custom.strip()
                if self.bottom_stack.tense_combo.findText(value) == -1:
                    self.bottom_stack.tense_combo.insertItem(0, value)
            else:
                self.bottom_stack.tense_combo.setCurrentText(self.model.settings["global_tense"])
                return
        self.model.settings["global_tense"] = value
        self.update_setting_tooltips()
        self.model.save_settings()

    def update_setting_tooltips(self):
        self.bottom_stack.pov_combo.setToolTip(_("POV: {}").format(self.model.settings['global_pov']))
        self.bottom_stack.pov_character_combo.setToolTip(_("POV Character: {}").format(self.model.settings['global_pov_character']))
        self.bottom_stack.tense_combo.setToolTip(pgettext("verb_tense", "Tense: {}").format(self.model.settings['global_tense']))

    def send_prompt(self):
        action_beats = self.bottom_stack.prompt_input.toPlainText().strip()
        if not action_beats:
            QMessageBox.warning(self, _("LLM Prompt"), _("Please enter some action beats before sending."))
            return
        
        prose_config = self.bottom_stack.prose_prompt_panel.get_prompt()
        if not prose_config:
            QMessageBox.warning(self, _("LLM Prompt"), _("Please select a prompt."))
            return
        overrides = self.bottom_stack.prose_prompt_panel.get_overrides()
        additional_vars = self.bottom_stack.get_additional_vars()
        current_scene_text = self.scene_editor.editor.toPlainText().strip() if self.project_tree.tree.currentItem() and self.project_tree.get_item_level(self.project_tree.tree.currentItem()) >= 2 else None
        extra_context = self.bottom_stack.context_panel.get_selected_context_text()
        
        final_prompt = prompt_handler.assemble_final_prompt(prose_config, action_beats, additional_vars, current_scene_text, extra_context)
        
        self.bottom_stack.preview_text.clear()
        self.bottom_stack.send_button.setEnabled(False)
        self.bottom_stack.preview_text.setReadOnly(True) # User clicks can really mess up the text inserts
        QApplication.processEvents()
        self.stop_llm()
        self.worker = LLMWorker(final_prompt, overrides)
        self.worker.data_received.connect(self.update_text)
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.cleanup_worker)
        self.worker.token_limit_exceeded.connect(self.handle_token_limit_error)
        self.worker.start()


    def handle_token_limit_error(self, error_msg):
        self.bottom_stack.send_button.setEnabled(True)
        current_item = self.project_tree.tree.currentItem()
        level = self.project_tree.get_item_level(current_item) if current_item else -1
        
        # Step 1: Check for existing summary
        if current_item and level < 2 and current_item.data(0, Qt.UserRole).get("summary"):
            summary = current_item.data(0, Qt.UserRole)["summary"]
            self.retry_with_summary(summary)
            return
        
        # Step 2: Auto-generate summary
        self.statusBar().showMessage(_("Generating summary to fit token limit…"))
        self.bottom_stack.summary_controller.create_summary()
        QTimer.singleShot(30000, lambda: self.retry_with_auto_summary())

    def retry_with_summary(self, summary):
        additional_vars = {
            "pov": self.model.settings["global_pov"] or _("Third Person"),
            "pov_character": self.model.settings["global_pov_character"] or _("Character"),
            "tense": self.model.settings["global_tense"] or _("Present Tense"),
            # Add more ad-hoc tags here if needed, e.g., "assistant": "Grok"
        }
        action_beats = self.bottom_stack.prompt_input.toPlainText().strip()
        prose_config = self.bottom_stack.prose_prompt_panel.get_prompt()
        final_prompt = prompt_handler.assemble_final_prompt(
            prose_config.get("text"),
            action_beats, additional_vars,
            summary,  # Use summary instead of full story
            None
        )
        self.bottom_stack.preview_text.clear()
        self.bottom_stack.preview_text.setReadOnly(True) # User clicks can really mess up the text inserts
        self.worker = LLMWorker(final_prompt, prose_config)
        self.worker.data_received.connect(self.update_text)
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.cleanup_worker)
        self.worker.token_limit_exceeded.connect(self.show_token_limit_dialog)
        self.worker.start()

    def retry_with_auto_summary(self):
        summary = self.scene_editor.editor.toPlainText().strip()
        self.bottom_stack.preview_text.setPlainText(summary)  # Show for editing
        self.statusBar().showMessage(_("Summary generated. Edit if needed, then resend."))
        # User can hit "Send" again after tweaking

    def show_token_limit_dialog(self, error_msg):
        prose_config = self.bottom_stack.prose_prompt_panel.get_prompt()
        max_tokens = prose_config.get("max_tokens", 2000)
        dialog = TokenLimitDialog(error_msg, self.bottom_stack.preview_text.toPlainText(), max_tokens, parent=self)
        dialog.use_summary.connect(self.retry_with_summary)
        dialog.truncate_story.connect(self.retry_with_truncated_story)
        dialog.exec_()

    def retry_with_truncated_story(self):
        full_text = self.scene_editor.editor.toPlainText()
        prose_config = self.bottom_stack.prose_prompt_panel.get_prompt()
        tokens = tiktoken.get_encoding("cl100k_base").encode(full_text)
        max_tokens = prose_config.get("max_tokens", 2000) * 0.5  # Use half for safety
        truncated = self.encoding.decode(tokens[-int(max_tokens):])
        self.retry_with_summary(truncated)

    def update_text(self, text):
        cursor = self.bottom_stack.preview_text.textCursor()
        cursor.movePosition(QTextCursor.End)  # Move cursor to the end
        self.bottom_stack.preview_text.setTextCursor(cursor)
        self.bottom_stack.preview_text.insertPlainText(text)

    def cleanup_worker(self):
        logging.debug(f"Starting cleanup_worker, worker: {id(self.worker) if self.worker else None}")
        try:
            if self.worker:
                worker_id = id(self.worker)
                if self.worker.isRunning():
                    logging.debug(f"Stopping worker {worker_id}")
                    self.worker.stop()
                    self.worker.wait(5000)  # Wait up to 5 seconds for the thread to stop
                    if self.worker.isRunning():
                        logging.warning(f"Worker {worker_id} did not stop in time; skipping termination")
                try:
                    logging.debug(f"Disconnecting signals for worker {worker_id}")
                    self.worker.data_received.disconnect()
                    self.worker.finished.disconnect()
                    self.worker.token_limit_exceeded.disconnect()
                except TypeError as e:
                    logging.debug(f"Signal disconnection error for worker {worker_id}: {e}")
                logging.debug(f"Scheduling worker {worker_id} for deletion")
                self.worker.deleteLater()  # Schedule deletion
                self.worker = None  # Clear reference
        except Exception as e:
            logging.error(f"Error cleaning up LLMWorker: {e}", exc_info=True)
            QMessageBox.critical(self, _("Thread Error"), _("An error occurred while stopping the LLM thread: {}").format(str(e)))

    def on_finished(self):
        self.bottom_stack.send_button.setEnabled(True)
        self.bottom_stack.preview_text.setReadOnly(False)

        raw_text = self.bottom_stack.preview_text.toPlainText()
        if not raw_text.strip():
            QMessageBox.warning(self, _("LLM Response"), _("The LLM did not return any text. Possible token limit reached or an error occurred."))
            return

        # Format Markdown-style bold and italic text as HTML.
        formatted_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", raw_text)  # Bold
        formatted_text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", formatted_text)  # Italic
        formatted_text = formatted_text.replace("\n", "<br>")

        self.bottom_stack.preview_text.setHtml(formatted_text)

        logging.debug(f"Active threads: {threading.enumerate()}")

    def stop_llm(self):
        logging.debug(f"Starting stop_llm, worker: {id(self.worker) if self.worker else None}")
        try:
            if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
                logging.debug("Calling worker.stop()")
                self.worker.stop()
                logging.debug("Calling WWApiAggregator.interrupt()")
                WWApiAggregator.interrupt()
            self.bottom_stack.send_button.setEnabled(True)
            self.bottom_stack.preview_text.setReadOnly(False)
            logging.debug("Calling cleanup_worker")
            self.cleanup_worker()
        except Exception as e:
            logging.error(f"Error in stop_llm: {e}", exc_info=True)
            QMessageBox.critical(self, _("Error"), _("An error occurred while stopping the LLM: {}").format(str(e)))

    def apply_preview(self):
        """Appends the LLM's output to the scene editor."""
        try:
            preview = self.bottom_stack.preview_text.toHtml().strip()
            if not preview:
                QMessageBox.warning(self, _("Apply Preview"), _("No preview text to apply."))
                return

            # Include the prompt block if the checkbox is checked
            prompt_block = None
            if self.bottom_stack.include_prompt_checkbox.isChecked():
                prompt = self.bottom_stack.prompt_input.toPlainText().strip()
                if prompt:
                    prompt_block = f"\n{'_' * 10}\n{prompt}\n{'_' * 10}\n"

            # Append the formatted text and prompt block to the scene editor
            cursor = self.scene_editor.editor.textCursor()
            cursor.movePosition(QTextCursor.End)  # Move cursor to the end of the current text
            if prompt_block:
                cursor.insertText(prompt_block)
            cursor.insertHtml(preview)
            self.scene_editor.editor.moveCursor(QTextCursor.End)  # Ensure the cursor is at the end

            # Clear the preview text area after applying
            self.bottom_stack.preview_text.clear()
            self.unsaved_preview = False
            self.model.unsaved_changes = True
        except Exception as e:
            QMessageBox.warning(self, _("Apply Preview"), _("Error: {}").format(str(e)))
        

    def save_summary(self):
        current_item = self.project_tree.tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, _("Summary"), _("No Act or Chapter selected."))
            return
        summary_text = self.scene_editor.editor.toHtml()  # Use HTML to preserve formatting
        hierarchy = self.get_item_hierarchy(current_item)
        filepath = self.model.save_summary(hierarchy, summary_text)
        if filepath:
            self.update_save_status(_("Summary saved successfully"))
            self.model.unsaved_changes = False
            QMessageBox.information(self, _("Summary"), _("Summary saved successfully."))
        else:
            QMessageBox.critical(self, _("Summary"), _("Failed to save summary."))
            
    def toggle_bold(self):
        cursor = self.scene_editor.editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Normal if self.scene_editor.editor.fontWeight() == QFont.Bold else QFont.Bold)
        cursor.mergeCharFormat(fmt)
        self.scene_editor.editor.mergeCurrentCharFormat(fmt)

    def toggle_italic(self):
        cursor = self.scene_editor.editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.scene_editor.editor.fontItalic())
        cursor.mergeCharFormat(fmt)
        self.scene_editor.editor.mergeCurrentCharFormat(fmt)

    def toggle_underline(self):
        cursor = self.scene_editor.editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.scene_editor.editor.fontUnderline())
        cursor.mergeCharFormat(fmt)
        self.scene_editor.editor.mergeCurrentCharFormat(fmt)

    def align_left(self):
        self.scene_editor.editor.setAlignment(Qt.AlignLeft)

    def align_center(self):
        self.scene_editor.editor.setAlignment(Qt.AlignCenter)

    def align_right(self):
        self.scene_editor.editor.setAlignment(Qt.AlignRight)

    def set_font_size(self, size):
        cursor = self.scene_editor.editor.textCursor()
        if not cursor.hasSelection():
            # Apply to the current position for typing new text
            fmt = self.scene_editor.editor.currentCharFormat()
            fmt.setFontPointSize(float(size))  # Ensure size is a float
            self.scene_editor.editor.setCurrentCharFormat(fmt)
        else:
            # Apply to selected text, preserving formatting
            fmt = QTextCharFormat()  # Get the current format of the selection
            fmt.setFontPointSize(float(size))  # Update only the size
            cursor.mergeCharFormat(fmt)  # Apply to the selection directly
        # No need for setTextCursor here, as mergeCharFormat updates the text directly

    def update_font_family(self, font):
        cursor = self.scene_editor.editor.textCursor()
        if not cursor.hasSelection():
            # Apply to current position for typing new text
            fmt = self.scene_editor.editor.currentCharFormat()
            fmt.setFontFamilies([font.family()])
            # Preserve existing size if set, otherwise use default from combo
            current_size = self.scene_editor.font_size_combo.currentText()
            fmt.setFontPointSize(float(current_size) if current_size else font.pointSizeF())
            self.scene_editor.editor.setCurrentCharFormat(fmt)
        else:
            # Apply to selected text, preserving formatting
            fmt = QTextCharFormat()  # Get the current format of the selection
            fmt.setFontFamilies([font.family()])  # Update only the family
            cursor.mergeCharFormat(fmt)  # Apply to the selection directly
        # No need for setTextCursor here, as mergeCharFormat updates the text directly
       
    def toggle_tts(self):
        if self.tts_playing:
            WW_TTSManager.stop()
            self.tts_playing = False
            self.scene_editor.tts_action.setIcon(ThemeManager.get_tinted_icon("assets/icons/play-circle.svg"))
        else:
            cursor = self.scene_editor.editor.textCursor()
            text = cursor.selectedText() if cursor.hasSelection() else self.scene_editor.editor.toPlainText()
            start_position = 0 if cursor.hasSelection() else cursor.position()
            if not text.strip():
                QMessageBox.warning(self, _("TTS Warning"), _("There is no text to read."))
                return
            self.tts_playing = True
            self.scene_editor.tts_action.setIcon(ThemeManager.get_tinted_icon("assets/icons/stop-circle.svg"))
            WW_TTSManager.speak(text, start_position=start_position, on_complete=self.tts_completed)

    def tts_completed(self):
        self.tts_playing = False
        self.scene_editor.tts_action.setIcon(ThemeManager.get_tinted_icon("assets/icons/play-circle.svg"))

    def open_focus_mode(self):
        scene_text = self.scene_editor.editor.toPlainText()
        image_directory = os.path.join(os.getcwd(), "assets", "backgrounds")
        self.focus_window = FocusMode(image_directory, scene_text)
        self.focus_window.on_close = self.focus_mode_closed
        self.focus_window.show()

    def focus_mode_closed(self, updated_text):
        self.scene_editor.editor.setPlainText(updated_text)

    def open_analysis_editor(self):
        current_text = self.scene_editor.editor.toPlainText()
        self.analysis_editor_window = TextAnalysisApp(parent=self, initial_text=current_text, save_callback=self.analysis_save_callback)
        self.analysis_editor_window.show()
        
    def open_web_llm(self):
        self.web_llm = MainWindow()
        self.web_llm.show()
        
    def open_whisper_app(self):
        self.whisper_app = WhisperApp(self)
        self.whisper_app.show()
        
    def open_ia_window(self):
        """Open the Internet Archive window."""
        self.ia_window = IAWindow()
        self.ia_window.show()

    def analysis_save_callback(self, updated_text):
        self.scene_editor.editor.setPlainText(updated_text)
        self.manual_save_scene()

    def open_compendium(self):
        self.compendium_panel.setVisible(not self.compendium_panel.isVisible())

    def open_prompts_window(self):
        prompts_window = PromptsWindow(self.model.project_name, self)
        prompts_window.finished.connect(self.repopulate_prompts)
        prompts_window.exec_()

    def repopulate_prompts(self):
        self.bottom_stack.prose_prompt_panel.repopulate_prompts()

    def open_workshop(self):
        self.workshop_window = WorkshopWindow(self)
        self.workshop_window.show()

    def rewrite_selected_text(self):
        cursor = self.scene_editor.editor.textCursor()
        if not cursor.hasSelection():
            QMessageBox.warning(self, _("Rewrite"), _("No text selected to rewrite."))
            return
        selected_text = cursor.selectedText()
        dialog = RewriteDialog(self.model.project_name, selected_text, self)
        if dialog.exec_() == QDialog.Accepted:
            cursor.insertText(dialog.rewritten_text)
            self.scene_editor.editor.setTextCursor(cursor)

    def update_pov_character_dropdown(self):
        compendium_path = WWSettingsManager.get_project_path(self.model.project_name, "compendium.json")
        characters = []
        if os.path.exists(compendium_path):
            try:
                with open(compendium_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for cat in data.get("categories", []):
                    if cat.get("name", "").lower() == "characters":
                        characters = [entry.get("name", "").strip() for entry in cat.get("entries", []) if entry.get("name", "").strip()]
                        break
            except Exception as e:
                print(f"Error loading characters from compendium: {e}")
        if not characters:
            characters = ["Alice", "Bob", "Charlie"]
        characters.append(_("Custom..."))
        self.bottom_stack.pov_character_combo.blockSignals(True)
        self.bottom_stack.pov_character_combo.clear()
        self.bottom_stack.pov_character_combo.blockSignals(False)
        self.bottom_stack.pov_character_combo.addItems(characters)

    def restore_pov_character(self, previous_pov):
        """Restore the previous POV character if it still exists, otherwise handle appropriately."""
        combo = self.bottom_stack.pov_character_combo
        index = combo.findText(previous_pov)
        
        if index >= 0:  # Previous POV character still exists
            combo.setCurrentIndex(index)
        else:  # Previous POV character was deleted
            if combo.count() == 2 and combo.itemText(0) != _("Custom..."):  # Only one character + Custom...
                combo.setCurrentIndex(0)  # Select the only character
            elif combo.count() > 2:  # Multiple characters + Custom...
                # Add and select a placeholder if it doesn't exist
                placeholder = _("-- Select Character --")
                if combo.findText(placeholder) == -1:
                    combo.insertItem(0, placeholder)
                combo.setCurrentIndex(0)
            else:  # No characters, only Custom...
                combo.setCurrentIndex(combo.findText(_("Custom...")))

    def update_icons(self):
        tint_str = ThemeManager.ICON_TINTS.get(self.current_theme, "black")
        self.icon_tint = QColor(tint_str)
        self.global_toolbar.update_tint(self.icon_tint)
        self.scene_editor.update_tint(self.icon_tint)
        self.bottom_stack.update_tint(self.icon_tint)
        self.project_tree.assign_all_icons()

    def change_theme(self, new_theme):
        self.current_theme = new_theme
        ThemeManager.apply_to_app(new_theme)
        self.update_icons()

    def on_editor_text_changed(self):
        text = self.scene_editor.editor.toPlainText()
        self.word_count_label.setText(_("Words: {}").format(len(text.split())))
        self.model.unsaved_changes = True

    def on_preview_text_changed(self):
        preview_text = self.bottom_stack.preview_text.toPlainText().strip()
        self.unsaved_preview = bool(preview_text)  # True if not empty, False if empty

    def load_prompt_input(self):
        prompt_input_file = WWSettingsManager.get_project_path(self.model.project_name, "action-beat.txt")
        if os.path.exists(prompt_input_file):
            try:
                with open(prompt_input_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"Error loading prompt input: {e}")
        return ""

    def on_prompt_input_text_changed(self):
        if self.model.autosave_enabled:
            if not hasattr(self, 'prompt_input_timer'):
                self.prompt_input_timer = QTimer(self)
                self.prompt_input_timer.setSingleShot(True)
                self.prompt_input_timer.timeout.connect(self.save_prompt_input)
            self.prompt_input_timer.start(5000)  # 5 seconds

    def save_prompt_input(self):
        project_folder = WWSettingsManager.get_project_path(self.model.project_name)
        os.makedirs(project_folder, exist_ok=True)
        prompt_input_file = os.path.join(project_folder, "action-beat.txt")
        try:
            with open(prompt_input_file, "w", encoding="utf-8") as f:
                f.write(self.bottom_stack.prompt_input.toPlainText())
        except Exception as e:
            print(f"Error saving prompt input: {e}")

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    window = ProjectWindow("My Awesome Project")
    window.show()
    sys.exit(app.exec_())