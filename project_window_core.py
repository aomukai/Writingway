#!/usr/bin/env python3
import os
import time
import glob
import json
import re
import threading
import pyttsx3
from PyQt5.QtWidgets import (
    QMainWindow, QInputDialog, QMenu, QMessageBox, QApplication, QDialog,
    QFontDialog, QShortcut, QLabel
)
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtGui import QFont, QTextCharFormat, QIcon, QKeySequence, QPixmap, QPainter, QColor, QImage
from compendium import CompendiumWindow
from workshop import WorkshopWindow
from rewrite_feature import RewriteDialog
from backup_manager import show_backup_dialog
from summary_feature import create_summary as create_summary_feature
from prompts import load_project_options
from tree_manager import load_structure, save_structure, populate_tree, update_structure_from_tree, delete_node
from context_panel import ContextPanel
import tts_manager
import autosave_manager
from dialogs import CreateSummaryDialog
from project_ui import build_main_ui
from settings_manager import WWSettingsManager
import project_settings_manager as settings_manager
from project_structure_manager import add_act, add_chapter, add_scene, rename_item, move_item_up, move_item_down
from theme_manager import ThemeManager  # <-- Added import for theme management
from focus_mode import FocusMode
from llm_worker import LLMWorker


class ProjectWindow(QMainWindow):
    def __init__(self, project_name):
        super().__init__()
        self.project_name = project_name
        self.setWindowTitle(f"Project: {project_name}")
        self.resize(900, 600)
        self.current_pov = ""
        self.current_pov_character = "Character"
        self.current_tense = "Present Tense"
        self.current_prose_prompt = None
        self.current_prose_config = None
        self.tts_playing = False
        self.structure = load_structure(self.project_name)
        self.init_ui()
        self.readSettings()  # Restore saved window and splitter settings

        # Set tree to use 2 columns: Name and Status.
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Name", "Status"])
        # Status bar labels for word count and last save time.
        self.word_count_label = QLabel("Words: 0")
        self.last_save_label = QLabel("Last Saved: Never")
        self.statusBar().addPermanentWidget(self.word_count_label)
        self.statusBar().addPermanentWidget(self.last_save_label)
        self.editor.textChanged.connect(self.update_word_count)

        self.load_autosave_setting()
        if self.autosave_enabled:
            self.start_autosave_timer()
        if self.tree.topLevelItemCount() > 0:
            act_item = self.tree.topLevelItem(0)
            if act_item.childCount() > 0:
                chapter_item = act_item.child(0)
                if chapter_item.childCount() > 0:
                    self.tree.setCurrentItem(chapter_item.child(0))
        self.updateSettingTooltips()
        self.populate_prompt_dropdown()

        # Bind F11 key to open focus mode
        self.focus_mode_shortcut = QShortcut(QKeySequence("F11"), self)
        self.focus_mode_shortcut.activated.connect(self.open_focus_mode)

        # NEW: Update the POV Character dropdown from compendium data.
        self.update_pov_character_dropdown()

    def updateSettingTooltips(self):
        # Only update tooltips if the corresponding widgets exist.
        if hasattr(self, "pov_combo"):
            self.pov_combo.setToolTip(f"POV: {self.current_pov}")
        if hasattr(self, "pov_character_combo"):
            self.pov_character_combo.setToolTip(f"POV Character: {self.current_pov_character}")
        if hasattr(self, "tense_combo"):
            self.tense_combo.setToolTip(f"Tense: {self.current_tense}")

    def load_autosave_setting(self):
        self.autosave_enabled = WWSettingsManager.get_setting(
            "general", "enable_autosave", False)
        settings = settings_manager.load_project_settings(self.project_name)
        self.current_pov = settings.get("global_pov", self.current_pov)
        self.current_pov_character = settings.get(
            "global_pov_character", self.current_pov_character)
        self.current_tense = settings.get("global_tense", self.current_tense)

    def save_global_settings(self):
        project_settings = {
            "global_pov": self.current_pov,
            "global_pov_character": self.current_pov_character,
            "global_tense": self.current_tense
        }
        settings_manager.save_project_settings(
            self.project_name, project_settings)

    def populate_tree(self):
        populate_tree(self.tree, self.structure)
        self.assign_tree_icons()

    def assign_tree_icons(self):
        # For nodes at level < 2, use the book icon in column 0 and leave column 1 empty.
        # For scene nodes (level >= 2), set column 0 with the "edit" icon and scene name,
        # and set column 1 with the status icon.
        def set_icon_recursively(item):
            level = 0
            temp = item
            while temp.parent():
                level += 1
                temp = temp.parent()
            if level < 2:
                item.setIcon(0, QIcon("assets/icons/book.svg"))
                item.setText(1, "")  # No status icon for non-scenes.
            else:
                # Ensure metadata exists.
                scene_data = item.data(0, Qt.UserRole)
                if not scene_data or not isinstance(scene_data, dict):
                    scene_data = {"name": item.text(0), "status": "To Do"}
                    item.setData(0, Qt.UserRole, scene_data)
                # Set the left column: scene name with "edit" icon.
                item.setText(0, scene_data.get("name", "Unnamed Scene"))
                item.setIcon(0, QIcon("assets/icons/edit.svg"))
                # Set the right column: status icon.
                self.update_scene_status_icon(item)
            # Process children recursively.
            for i in range(item.childCount()):
                set_icon_recursively(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            set_icon_recursively(top_item)

    from PyQt5.QtGui import QImage, qAlpha  # make sure qAlpha is imported

    def get_tinted_icon(self, file_path, tint_color=QColor(150, 150, 150)):
        """
        Loads an icon from file_path and applies a tint using QPainter.
        If tint_color is black, returns the original icon.
        Otherwise, fills a pixmap with tint_color and applies the source icon as a mask.
        """
        if tint_color == QColor("black"):
            return QIcon(file_path)

        original_pix = QPixmap(file_path)
        if original_pix.isNull():
            return QIcon()

        tinted_pix = QPixmap(original_pix.size())
        tinted_pix.fill(tint_color)

        painter = QPainter(tinted_pix)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawPixmap(0, 0, original_pix)
        painter.end()

        return QIcon(tinted_pix)

    def update_scene_status_icon(self, item):
        tint = self.icon_tint if hasattr(self, 'icon_tint') else QColor(150, 150, 150)
        scene_data = item.data(0, Qt.UserRole)
        status = scene_data.get("status", "To Do")
        if status == "To Do":
            icon = self.get_tinted_icon("assets/icons/circle.svg", tint_color=tint)
        elif status == "In Progress":
            icon = self.get_tinted_icon("assets/icons/loader.svg", tint_color=tint)
        elif status == "Final Draft":
            icon = self.get_tinted_icon("assets/icons/check-circle.svg", tint_color=tint)
        else:
            icon = QIcon()  # No icon.
        item.setIcon(1, icon)
        item.setText(1, "")

    def update_structure_from_tree(self):
        self.structure = update_structure_from_tree(self.tree, self.project_name)

    def get_summary_filename(self, item):
        def sanitize(text):
            return re.sub(r'\W+', '', text)
        hierarchy = []
        temp = item
        while temp:
            hierarchy.insert(0, temp.text(0).strip())
            temp = temp.parent()
        sanitized = [sanitize(x) for x in hierarchy]
        filename = f"{sanitize(self.project_name)}-Summary-" + "-".join(sanitized) + ".txt"
        project_folder = os.path.join(os.getcwd(), "Projects", sanitize(self.project_name))
        if not os.path.exists(project_folder):
            os.makedirs(project_folder)
        return os.path.join(project_folder, filename)

    def init_ui(self):
        build_main_ui(self)
        
    def readSettings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        geometry = settings.value(f"{self.project_name}/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        windowState = settings.value(f"{self.project_name}/windowState")
        if windowState is not None:
            self.restoreState(windowState)
        main_splitter_state = settings.value(f"{self.project_name}/mainSplitterState")
        if main_splitter_state is not None and hasattr(self, "main_splitter"):
            self.main_splitter.restoreState(main_splitter_state)
        treeHeaderState = settings.value(f"{self.project_name}/treeHeaderState")
        if treeHeaderState is not None and hasattr(self, "tree"):
            self.tree.header().restoreState(treeHeaderState)

    def writeSettings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue(f"{self.project_name}/geometry", self.saveGeometry())
        settings.setValue(f"{self.project_name}/windowState", self.saveState())
        if hasattr(self, "main_splitter"):
            settings.setValue(f"{self.project_name}/mainSplitterState", self.main_splitter.saveState())
        if hasattr(self, "tree"):
            settings.setValue(f"{self.project_name}/treeHeaderState", self.tree.header().saveState())

    def closeEvent(self, event):
        self.writeSettings()  # Save settings before closing
        event.accept()

    def update_word_count(self):
        # Count words based on plain text
        text = self.editor.toPlainText()
        words = text.split()
        count = len(words)
        self.word_count_label.setText(f"Words: {count}")

    def toggle_context_panel(self):
        if self.context_panel.isVisible():
            self.context_panel.setVisible(False)
            self.context_toggle_button.setText("Context")
        else:
            self.context_panel.build_project_tree()
            self.context_panel.build_compendium_tree()
            self.context_panel.setVisible(True)
            self.context_toggle_button.setText("Hide")

    def open_workshop(self):
        self.workshop_window = WorkshopWindow(self)
        self.workshop_window.show()

    def open_compendium(self):
        if hasattr(self, "compendium_panel"):
            visible = self.compendium_panel.isVisible()
            self.compendium_panel.setVisible(not visible)
        else:
            print("Compendium panel not found.")

    def open_prompts_window(self):
        from prompts import PromptsWindow
        prompts_window = PromptsWindow(self.project_name, self)
        prompts_window.finished.connect(self.repopulate_prompts)
        prompts_window.exec_()

    def show_editor_context_menu(self, pos):
        menu = self.editor.createStandardContextMenu()
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            rewrite_action = menu.addAction("Rewrite")
            rewrite_action.triggered.connect(self.rewrite_selected_text)
        menu.exec_(self.editor.mapToGlobal(pos))

    def rewrite_selected_text(self):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            QMessageBox.warning(self, "Rewrite", "No text selected to rewrite.")
            return
        selected_text = cursor.selectedText()
        dialog = RewriteDialog(self.project_name, selected_text, self)
        if dialog.exec_() == QDialog.Accepted:
            cursor.insertText(dialog.rewritten_text)
            self.editor.setTextCursor(cursor)

    def open_project_options(self):
        pass

    def tree_item_changed(self, current, previous):
        # Before switching, if there is a previous item, check for unsaved changes.
        if previous is not None:
            # Determine the level of the previous item (e.g. scene level is >= 2)
            level = 0
            temp = previous
            while temp.parent():
                level += 1
                temp = temp.parent()

            # For scenes, compare the current editor content to what was last loaded.
            unsaved_in_editor = False
            if level >= 2:
                # Assume self.last_loaded_content holds the text as last loaded/saved.
                original_content = self.last_loaded_content if hasattr(self, "last_loaded_content") else ""
                if self.editor.toPlainText().strip() != original_content.strip():
                    unsaved_in_editor = True

            # Check if the "action beats" or "LLM output preview" fields have any content.
            unsaved_in_prompt = bool(self.prompt_input.toPlainText().strip())
            unsaved_in_preview = bool(self.preview_text.toPlainText().strip())

            # If any unsaved content exists, warn the user.
            if unsaved_in_editor or unsaved_in_prompt or unsaved_in_preview:
                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    "You have unsaved content in this scene and/or pending prompt output. Do you really want to leave?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    # Revert the selection back to the previous item.
                    self.tree.blockSignals(True)
                    self.tree.setCurrentItem(previous)
                    self.tree.blockSignals(False)
                    return

        # Proceed with loading the new item.
        if current is None:
            self.editor.clear()
            self.bottom_stack.setCurrentIndex(0)
            return

        # (Existing logic to load autosaved content or scene data for the new item.)
        level = 0
        temp = current
        while temp.parent():
            level += 1
            temp = temp.parent()
        if level >= 2:
            autosave_content = self.load_latest_autosave_for_item(current)
            if autosave_content is not None:
                if autosave_content.lstrip().startswith("<"):
                    self.editor.setHtml(autosave_content)
                else:
                    self.editor.setPlainText(autosave_content)
            else:
                scene_data = current.data(0, Qt.UserRole)
                content = scene_data.get("content", "") if isinstance(scene_data, dict) else ""
                if content.lstrip().startswith("<"):
                    self.editor.setHtml(content)
                else:
                    self.editor.setPlainText(content)
            self.editor.setPlaceholderText("Enter scene content...")
            self.bottom_stack.setCurrentIndex(1)
        else:
            # For non-scene items (e.g. summaries).
            item_data = current.data(0, Qt.UserRole)
            content = item_data.get("summary", "") if isinstance(item_data, dict) else ""
            if content.lstrip().startswith("<"):
                self.editor.setHtml(content)
            else:
                self.editor.setPlainText(content)
            self.editor.setPlaceholderText(f"Enter summary for {current.text(0)}...")
            self.bottom_stack.setCurrentIndex(0)

        # Update the "last loaded" content to match what was just loaded.
        self.last_loaded_content = self.editor.toPlainText()

        self.updateSettingTooltips()

    def load_latest_autosave_for_item(self, item):
        # Build hierarchy from tree item and delegate to autosave_manager
        def sanitize(text):
            return re.sub(r'\W+', '', text)
        hierarchy = []
        current = item
        while current:
            hierarchy.insert(0, current.text(0).strip())
            current = current.parent()
        return autosave_manager.load_latest_autosave(self.project_name, hierarchy)

    def show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu()
        if item is None:
            add_act_action = menu.addAction("Add Act")
            action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if action == add_act_action:
                add_act(self)
            return
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        move_up_action = menu.addAction("Move Up")
        move_down_action = menu.addAction("Move Down")
        level = 0
        temp = item
        while temp.parent():
            level += 1
            temp = temp.parent()
        if level == 0:
            add_chapter_action = menu.addAction("Add Chapter")
        elif level == 1:
            add_scene_action = menu.addAction("Add Scene")
        if level >= 2:
            status_menu = menu.addMenu("Set Scene Status")
            for status_option in ["To Do", "In Progress", "Final Draft"]:
                action_status = status_menu.addAction(status_option)
                action_status.triggered.connect(lambda checked, s=status_option: self.set_scene_status(item, s))
        action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
        if action == rename_action:
            rename_item(self, item)
        elif action == delete_action:
            delete_node(self.tree, item, self.project_name)
        elif action == move_up_action:
            move_item_up(self, item)
        elif action == move_down_action:
            move_item_down(self, item)
        elif level == 0 and 'add_chapter_action' in locals() and action == add_chapter_action:
            add_chapter(self, item)
        elif level == 1 and 'add_scene_action' in locals() and action == add_scene_action:
            add_scene(self, item)

    def set_scene_status(self, item, new_status):
        scene_data = item.data(0, Qt.UserRole)
        if not isinstance(scene_data, dict):
            scene_data = {"name": item.text(0), "status": new_status}
        else:
            scene_data["status"] = new_status
        item.setData(0, Qt.UserRole, scene_data)
        self.update_scene_status_icon(item)
        self.update_structure_from_tree()

    def start_autosave_timer(self):
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(300000)
        self.autosave_timer.timeout.connect(self.autosave_scene)
        self.autosave_timer.start()

    def manual_save_scene(self):
        current_item = self.tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Manual Save", "No scene selected for saving.")
            return
        level = 0
        temp = current_item
        while temp.parent():
            level += 1
            temp = temp.parent()
        if level < 2:
            QMessageBox.warning(self, "Manual Save", "Please select a scene for manual save.")
            return
        # Use toHtml() to save rich formatting
        content = self.editor.toHtml()
        if not content.strip():
            QMessageBox.warning(self, "Manual Save", "There is no content to save.")
            return
        hierarchy = []
        item = current_item
        while item:
            hierarchy.insert(0, item.text(0).strip())
            item = item.parent()
        filepath = autosave_manager.save_scene(self.project_name, hierarchy, content)
        if filepath:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            self.last_save_label.setText(f"Last Saved: {now}")
            self.statusBar().showMessage("Scene manually saved", 3000)
            scene_data = current_item.data(0, Qt.UserRole)
            if not isinstance(scene_data, dict):
                scene_data = {"name": current_item.text(0)}
            scene_data["content"] = content
            scene_data["status"] = scene_data.get("status", "To Do")
            current_item.setData(0, Qt.UserRole, scene_data)
            self.update_structure_from_tree()
        else:
            self.statusBar().showMessage("No changes detected. Manual save skipped.", 3000)

    def autosave_scene(self):
        current_item = self.tree.currentItem()
        if not current_item:
            return
        level = 0
        temp = current_item
        while temp.parent():
            level += 1
            temp = temp.parent()
        if level < 2:
            return
        # Use toHtml() to save rich formatting
        content = self.editor.toHtml()
        if not content.strip():
            return
        hierarchy = []
        item = current_item
        while item:
            hierarchy.insert(0, item.text(0).strip())
            item = item.parent()
        filepath = autosave_manager.save_scene(self.project_name, hierarchy, content)
        if filepath:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            self.last_save_label.setText(f"Last Saved: {now}")
            self.statusBar().showMessage("Scene autosaved", 3000)
            scene_data = current_item.data(0, Qt.UserRole)
            if not isinstance(scene_data, dict):
                scene_data = {"name": current_item.text(0)}
            scene_data["content"] = content
            scene_data["status"] = scene_data.get("status", "To Do")
            current_item.setData(0, Qt.UserRole, scene_data)
            self.update_structure_from_tree()

    def on_oh_shit(self):
        current_item = self.tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Backup Versions", "No scene selected.")
            return
        level = 0
        temp = current_item
        while temp.parent():
            level += 1
            temp = temp.parent()
        if level < 2:
            QMessageBox.warning(self, "Backup Versions", "Please select a scene to view backups.")
            return
        scene_identifier = current_item.text(0)
        backup_file_path = show_backup_dialog(self, self.project_name, scene_identifier)
        if backup_file_path:
            try:
                with open(backup_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if backup_file_path.endswith(".html"):
                    self.editor.setHtml(content)
                else:
                    self.editor.setPlainText(content)
                scene_data = current_item.data(0, Qt.UserRole)
                if not isinstance(scene_data, dict):
                    scene_data = {"name": current_item.text(0)}
                scene_data["content"] = content
                current_item.setData(0, Qt.UserRole, scene_data)
                self.update_structure_from_tree()
                QMessageBox.information(self, "Backup Loaded", f"Backup loaded from:\n{backup_file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error loading backup file: {e}")
        else:
            QMessageBox.information(self, "Backup", "No backup file selected.")

    def handle_pov_change(self, index):
        value = self.pov_combo.currentText()
        if value == "Custom...":
            custom, ok = QInputDialog.getText(self, "Custom POV", "Enter custom POV:", text=self.current_pov if self.current_pov not in [
                                              "First Person", "Omniscient", "Third Person Limited"] else "")
            if ok and custom.strip():
                custom = custom.strip()
                if self.pov_combo.findText(custom) == -1:
                    self.pov_combo.insertItem(0, custom)
                self.current_pov = custom
                self.pov_combo.setCurrentText(custom)
            else:
                self.pov_combo.setCurrentText(self.current_pov)
                return
        else:
            self.current_pov = value
        self.pov_combo.setToolTip(f"POV: {self.current_pov}")
        self.save_global_settings()

    def handle_pov_character_change(self, index):
        value = self.pov_character_combo.currentText()
        if value == "Custom...":
            custom, ok = QInputDialog.getText(self, "Custom POV Character", "Enter custom POV Character:",
                                              text=self.current_pov_character if self.current_pov_character not in ["Alice", "Bob", "Charlie"] else "")
            if ok and custom.strip():
                custom = custom.strip()
                if self.pov_character_combo.findText(custom) == -1:
                    self.pov_character_combo.insertItem(0, custom)
                self.current_pov_character = custom
                self.pov_character_combo.setCurrentText(custom)
            else:
                self.pov_character_combo.setCurrentText(self.current_pov_character)
                return
        else:
            self.current_pov_character = value
        self.pov_character_combo.setToolTip(f"POV Character: {self.current_pov_character}")
        self.save_global_settings()

    def handle_tense_change(self, index):
        value = self.tense_combo.currentText()
        if value == "Custom...":
            custom, ok = QInputDialog.getText(self, "Custom Tense", "Enter custom Tense:", text=self.current_tense if self.current_tense not in [
                                              "Past Tense", "Present Tense"] else "")
            if ok and custom.strip():
                custom = custom.strip()
                if self.tense_combo.findText(custom) == -1:
                    self.tense_combo.insertItem(0, custom)
                self.current_tense = custom
                self.tense_combo.setCurrentText(custom)
            else:
                self.tense_combo.setCurrentText(self.current_tense)
                return
        else:
            self.current_tense = value
        self.tense_combo.setToolTip(f"Tense: {self.current_tense}")
        self.save_global_settings()

    def repopulate_prompts(self):
        self.populate_prompt_dropdown()

    def populate_prompt_dropdown(self):
        prompts_file = "prompts.json"
        prose_prompts = []
        if os.path.exists(prompts_file):
            try:
                with open(prompts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                prose_prompts = data.get("Prose", [])
            except Exception as e:
                print("Error loading prose prompts:", e)
        if not prose_prompts:
            prose_prompts = [{
                "name": "Default Prose Prompt",
                "text": "You are collaborating with the author to write a scene. Write the scene in {pov} point of view, from the perspective of {pov_character}, and in {tense}.",
                "provider": "Local",
                "model": "Local Model",
                "max_tokens": 200,
                "temperature": 0.7
            }]
        self.prompt_dropdown.blockSignals(True)
        self.prompt_dropdown.clear()
        self.prompt_dropdown.addItem("Select Prose Prompt")
        for prompt in prose_prompts:
            name = prompt.get("name", "Unnamed")
            self.prompt_dropdown.addItem(name)
        self.prompt_dropdown.blockSignals(False)
        self._prose_prompts = prose_prompts

    def prompt_dropdown_changed(self, index):
        if index == 0:
            return
        selected_prompt = self._prose_prompts[index - 1] if index - 1 < len(self._prose_prompts) else None
        if selected_prompt:
            self.current_prose_prompt = selected_prompt.get("text", "")
            self.current_prose_config = selected_prompt
            if hasattr(self, "model_indicator"):
                self.model_indicator.setText(f"[Model: {selected_prompt.get('model', 'Unknown')}]")

    def send_prompt(self):
        action_beats = self.prompt_input.toPlainText().strip()
        if not action_beats:
            QMessageBox.warning(self, "LLM Prompt", "Please enter some action beats before sending.")
            return
        if self.current_prose_prompt is not None:
            prose_prompt = self.current_prose_prompt
        else:
            prose_prompt = ("You are collaborating with the author to write a scene. "
                            "Write the scene in {pov} point of view, from the perspective of {pov_character}, and in {tense}.")
        pov = self.current_pov or "Third Person"
        pov_character = self.current_pov_character or "Character"
        tense = self.current_tense or "Present Tense"
        overrides = {}
        if self.current_prose_config:
            overrides = {
                "provider": self.current_prose_config.get("provider", "Local"),
                "model": self.current_prose_config.get("model", "Local Model"),
                "max_tokens": self.current_prose_config.get("max_tokens", 200),
                "temperature": self.current_prose_config.get("temperature", 0.7)
            }
        current_scene_text = None
        current_item = self.tree.currentItem()
        if current_item:
            level = 0
            temp = current_item
            while temp.parent():
                level += 1
                temp = temp.parent()
            if level >= 2:
                current_scene_text = self.editor.toPlainText().strip()
        extra_context = self.context_panel.get_selected_context_text()
        import prompt_handler
        final_prompt = prompt_handler.assemble_final_prompt(
            action_beats, prose_prompt, pov, pov_character, tense,
            current_scene_text, extra_context
        )
        self.send_button.setEnabled(False)
        QApplication.processEvents()

        self.worker = LLMWorker(final_prompt, overrides)
        self.worker.data_received.connect(self.update_text)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        self.stop_button.setEnabled(True)

    def update_text(self, text):
        self.preview_text.insertPlainText(text)

    def on_finished(self):
        self.send_button.setEnabled(True)

    def stop_llm(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.terminate()
            self.stop_button.setEnabled(False)
        self.send_button.setEnabled(True)


    def apply_preview(self):
        preview = self.preview_text.toPlainText().strip()
        if not preview:
            QMessageBox.warning(self, "Apply Preview", "No preview text to apply.")
            return
        # Only include the action beats if the checkbox is checked.
        if hasattr(self, "include_prompt_checkbox") and self.include_prompt_checkbox.isChecked():
            prompt = self.prompt_input.toPlainText().strip()
            if prompt:
                # Create a visual block for the prompt (customize as desired)
                prompt_block = "\n" + ("_" * 10) + "\n" + prompt + "\n" + ("_" * 10) + "\n"
            else:
                prompt_block = ""
        else:
            prompt_block = ""

        current_text = self.editor.toPlainText()
        # Append the prompt block (if any) and then the LLM output
        self.editor.setPlainText(current_text + "\n" + prompt_block + preview)
        
        # Scroll to the end of the editor after appending the text.
        from PyQt5.QtGui import QTextCursor
        self.editor.moveCursor(QTextCursor.End)
        
        self.preview_text.clear()
        self.prompt_input.clear()

    def retry_prompt(self):
        self.preview_text.clear()
        self.send_prompt()

    def create_summary(self):
        default_prompt = "Enter your summarizer prompt here..."
        dialog = CreateSummaryDialog(default_prompt, self)
        if dialog.exec_() == QDialog.Accepted:
            summary_prompt = dialog.prompt
            create_summary_feature(self)

    def save_summary(self):
        current_item = self.tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Summary", "No Act or Chapter selected.")
            return
        summary_text = self.editor.toPlainText()
        item_data = current_item.data(0, Qt.UserRole)
        if not isinstance(item_data, dict):
            item_data = {"name": current_item.text(0)}
        item_data["summary"] = summary_text
        current_item.setData(0, Qt.UserRole, item_data)
        self.update_structure_from_tree()
        QMessageBox.information(self, "Summary", "Summary saved successfully.")

    def toggle_bold(self):
        cursor = self.editor.textCursor()
        fmt = QTextCharFormat()
        current_weight = self.editor.fontWeight()
        fmt.setFontWeight(QFont.Normal if current_weight == QFont.Bold else QFont.Bold)
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)

    def toggle_italic(self):
        cursor = self.editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.editor.fontItalic())
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)

    def toggle_underline(self):
        cursor = self.editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.editor.fontUnderline())
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)

    def align_left(self):
        self.editor.setAlignment(Qt.AlignLeft)

    def align_center(self):
        self.editor.setAlignment(Qt.AlignCenter)

    def align_right(self):
        self.editor.setAlignment(Qt.AlignRight)

    def choose_font(self):
        font, ok = QFontDialog.getFont(self.editor.font(), self, "Choose Font")
        if ok:
            self.editor.setCurrentFont(font)

    def set_font_size(self, size):
        font = self.editor.currentFont()
        font.setPointSize(size)
        self.editor.setCurrentFont(font)

    def toggle_tts(self):
        if self.tts_playing:
            tts_manager.stop()
            self.tts_playing = False
            self.tts_action.setIcon(QIcon("assets/icons/play-circle.svg"))
        else:
            cursor = self.editor.textCursor()
            if cursor.hasSelection():
                text = cursor.selectedText()
                start_position = 0
            else:
                text = self.editor.toPlainText()
                start_position = cursor.position()
            if not text.strip():
                QMessageBox.warning(self, "TTS Warning", "There is no text to read.")
                return
            self.tts_playing = True
            self.tts_action.setIcon(QIcon("assets/icons/stop-circle.svg"))
            def run_speech():
                try:
                    tts_manager.speak(
                        text,
                        start_position=start_position,
                        on_complete=lambda: QTimer.singleShot(0, lambda: self.tts_action.setIcon(QIcon("assets/icons/play-circle.svg")))
                    )
                except Exception as e:
                    print("Error during TTS:", e)
            threading.Thread(target=run_speech).start()

    def perform_tts(self):
        self.toggle_tts()

    def open_focus_mode(self):
        scene_text = self.editor.toPlainText()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_directory = os.path.join(base_dir, "assets", "backgrounds")
        self.focus_window = FocusMode(image_directory, scene_text, parent=None)
        self.focus_window.on_close = self.focus_mode_closed
        self.focus_window.show()

    def focus_mode_closed(self, updated_text):
        self.editor.setPlainText(updated_text)

    # === New: Open Analysis Editor ===
    def open_analysis_editor(self):
        current_text = self.editor.toPlainText()
        from text_analysis_gui import TextAnalysisApp
        def analysis_save_callback(updated_text):
            self.editor.setPlainText(updated_text)
            self.manual_save_scene()
        self.analysis_editor_window = TextAnalysisApp(parent=self, initial_text=current_text, save_callback=analysis_save_callback)
        self.analysis_editor_window.show()

    # === New: Method to update icons based on the current theme ===
    def update_icons(self):
        tint_str = ThemeManager.ICON_TINTS.get(self.current_theme, "black")
        tint = QColor(tint_str)
        self.icon_tint = tint
        self.compendium_action.setIcon(self.get_tinted_icon("assets/icons/book.svg", tint_color=tint))
        self.prompt_options_action.setIcon(self.get_tinted_icon("assets/icons/settings.svg", tint_color=tint))
        self.workshop_action.setIcon(self.get_tinted_icon("assets/icons/message-square.svg", tint_color=tint))
        self.focus_mode_action.setIcon(self.get_tinted_icon("assets/icons/maximize-2.svg", tint_color=tint))
        self.bold_action.setIcon(self.get_tinted_icon("assets/icons/bold.svg", tint_color=tint))
        self.italic_action.setIcon(self.get_tinted_icon("assets/icons/italic.svg", tint_color=tint))
        self.underline_action.setIcon(self.get_tinted_icon("assets/icons/underline.svg", tint_color=tint))
        self.tts_action.setIcon(self.get_tinted_icon("assets/icons/play-circle.svg", tint_color=tint))
        self.align_left_action.setIcon(self.get_tinted_icon("assets/icons/align-left.svg", tint_color=tint))
        self.align_center_action.setIcon(self.get_tinted_icon("assets/icons/align-center.svg", tint_color=tint))
        self.align_right_action.setIcon(self.get_tinted_icon("assets/icons/align-right.svg", tint_color=tint))
        self.manual_save_action.setIcon(self.get_tinted_icon("assets/icons/save.svg", tint_color=tint))
        self.oh_shit_action.setIcon(self.get_tinted_icon("assets/icons/share.svg", tint_color=tint))
        self.send_button.setIcon(self.get_tinted_icon("assets/icons/send.svg", tint_color=tint))
        if self.context_panel.isVisible():
            self.context_toggle_button.setIcon(self.get_tinted_icon("assets/icons/book-open.svg", tint_color=tint))
        else:
            self.context_toggle_button.setIcon(self.get_tinted_icon("assets/icons/book.svg", tint_color=tint))
        self.apply_button.setIcon(self.get_tinted_icon("assets/icons/feather.svg", tint_color=tint))
        self.assign_tree_icons()

    # === New: Method to change theme and update icons dynamically ===
    def change_theme(self, new_theme):
        self.current_theme = new_theme
        ThemeManager.apply_to_app(new_theme)
        self.update_icons()

    # === NEW: Method to update POV Character dropdown using compendium data ===
    def update_pov_character_dropdown(self):
        import json, os, re
        def sanitize(text):
            return re.sub(r'\W+', '', text)
        # Construct the path to the compendium file in your project's folder.
        project_folder = os.path.join(os.getcwd(), "Projects", sanitize(self.project_name))
        compendium_path = os.path.join(project_folder, "compendium.json")
        characters = []
        if os.path.exists(compendium_path):
            try:
                with open(compendium_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Look for a category named "Characters" (ignoring case).
                for cat in data.get("categories", []):
                    if cat.get("name", "").lower() == "characters":
                        for entry in cat.get("entries", []):
                            name = entry.get("name", "").strip()
                            if name:
                                characters.append(name)
                        break  # Found the category; exit loop.
            except Exception as e:
                print("Error loading characters from compendium:", e)
        # Fallback to default names if no characters were found.
        if not characters:
            characters = ["Alice", "Bob", "Charlie"]
        # Ensure "Custom..." is the last option.
        if "Custom..." not in characters:
            characters.append("Custom...")
        # Update the POV character combo box.
        self.pov_character_combo.clear()
        self.pov_character_combo.addItems(characters)

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    window = ProjectWindow("My Awesome Project")
    window.show()
    sys.exit(app.exec_())
