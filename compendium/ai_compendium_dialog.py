# ai_compendium_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QTextEdit, QMessageBox, QTreeWidget, QTreeWidgetItem, 
                             QSplitter, QMenu, QWidget, QInputDialog, QSizePolicy, QShortcut, QLabel)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont, QCursor, QKeySequence
import json
import os

class AICompendiumDialog(QDialog):
    def __init__(self, ai_compendium_data, compendium_file, parent=None):
        super().__init__(parent)
        self.ai_compendium_data = ai_compendium_data
        self.compendium_file = compendium_file
        self.existing_compendium = self.load_existing_compendium()
        self.font_size = 12
        self.init_ui()
        self.read_settings()

    def load_existing_compendium(self):
        if os.path.exists(self.compendium_file):
            try:
                with open(self.compendium_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading existing compendium: {e}")
                return {"categories": [], "extensions": {"entries": {}}}
        return {"categories": [], "extensions": {"entries": {}}}

    def init_ui(self):
        self.setWindowTitle(_("AI Compendium Analysis"))
        self.resize(600, 400)

        layout = QVBoxLayout()

        self.splitter = QSplitter(Qt.Horizontal)

        # Left side: Tree for categories, entries, and relationships
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(_("Name"))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree.currentItemChanged.connect(self.on_item_changed)
        self.splitter.addWidget(self.tree)

        # Right side: Two editors with labels
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)

        # Label and top editor: AI-generated content
        self.new_label = QLabel(_("New"))
        self.new_label.setStyleSheet("font-weight: bold;")
        editor_layout.addWidget(self.new_label)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(_("Select an entry or relationship to view or edit its details."))
        editor_layout.addWidget(self.editor)

        # Label and bottom editor: Existing compendium entry
        self.current_label = QLabel(_("Current"))
        self.current_label.setStyleSheet("font-weight: bold;")
        editor_layout.addWidget(self.current_label)
        self.existing_editor = QTextEdit()
        self.existing_editor.setPlaceholderText(_("Existing compendium entry will appear here."))
        self.existing_editor.setReadOnly(True)
        editor_layout.addWidget(self.existing_editor)

        self.splitter.addWidget(editor_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)

        layout.addWidget(self.splitter)

        button_widget = QWidget()
        button_layout = QVBoxLayout(button_widget)
        self.save_button = QPushButton(_("Save to Compendium"))
        self.save_button.clicked.connect(self.save_and_close)
        button_layout.addWidget(self.save_button)

        self.close_button = QPushButton(_("Close"))
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)

        button_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(button_widget)
        self.setLayout(layout)

        self.populate_tree()

        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl+="), self)
        self.zoom_in_shortcut.activated.connect(self.zoom_in)
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        self.zoom_out_shortcut.activated.connect(self.zoom_out)

    def populate_tree(self):
        self.tree.clear()
        existing_entries = {}
        for cat in self.existing_compendium.get("categories", []):
            for entry in cat.get("entries", []):
                key = f"{cat['name']}/{entry['name']}"
                existing_entries[key] = {
                    "content": entry.get("content", ""),
                    "relationships": entry.get("relationships", [])
                }

        for cat in self.ai_compendium_data.get("categories", []):
            cat_item = QTreeWidgetItem(self.tree, [cat.get("name", "Unnamed Category")])
            cat_item.setData(0, Qt.UserRole, "category")
            for entry in cat.get("entries", []):
                entry_name = entry.get("name", "Unnamed Entry")
                entry_content = entry.get("content", "")
                entry_rels = entry.get("relationships", [])
                key = f"{cat['name']}/{entry_name}"
                entry_item = QTreeWidgetItem(cat_item, [entry_name])
                entry_item.setData(0, Qt.UserRole, "entry")
                entry_item.setData(1, Qt.UserRole, entry_content)
                entry_item.setData(3, Qt.UserRole, entry_rels)
                entry_item.setData(4, Qt.UserRole, None)  # Store edited entry content

                if entry_rels:
                    # Add relationships as child items
                    rel_item = QTreeWidgetItem(entry_item, [_("Relationships")])
                    rel_item.setData(0, Qt.UserRole, "relationships")
                    if entry_rels:
                        for rel in entry_rels:
                            rel_name = rel.get("name", "Unknown")
                            rel_type = rel.get("type", "Unknown")
                            rel_child = QTreeWidgetItem(rel_item, [rel_name])
                            rel_child.setData(0, Qt.UserRole, "relationship")
                            rel_child.setData(1, Qt.UserRole, rel_type)
                            rel_child.setData(2, Qt.UserRole, "Active")
                            rel_child.setData(4, Qt.UserRole, None)  # Store edited relationship type

                            # Bold if new entry or content/relationships differ
                            if key not in existing_entries or (
                                existing_entries[key]["content"] != entry_content or
                                existing_entries[key]["relationships"] != entry_rels
                            ):
                                font = QFont()
                                font.setBold(True)
                                rel_child.setFont(0, font)

                # Bold entry if new or modified
                if key in existing_entries:
                    if (existing_entries[key]["content"] == entry_content and 
                        existing_entries[key]["relationships"] == entry_rels):
                        entry_item.setData(2, Qt.UserRole, "Unchanged")
                        entry_item.setFlags(entry_item.flags() & ~Qt.ItemIsEditable)
                    else:
                        font = QFont()
                        font.setBold(True)
                        entry_item.setFont(0, font)
                        entry_item.setData(2, Qt.UserRole, "Modified")
                else:
                    font = QFont()
                    font.setBold(True)
                    entry_item.setFont(0, font)
                    entry_item.setData(2, Qt.UserRole, "Modified")

            cat_item.setExpanded(True)
        self.tree.expandAll()

    def on_item_changed(self, current, previous):
        # Store edits from previous item before clearing
        if previous is not None and not self.editor.isReadOnly():
            role = previous.data(0, Qt.UserRole)
            if role == "entry":
                editor_text = self.editor.toPlainText()
                if editor_text.strip():
                    parts = editor_text.split(_("\n\nRelationships:\n"))
                    if len(parts) > 1 and all(": " in line for line in parts[1].strip().split("\n") if line.startswith("- ")):
                        previous.setData(4, Qt.UserRole, editor_text)
            elif role == "relationship":
                editor_text = self.editor.toPlainText()
                if editor_text.strip() and ": " in editor_text:
                    previous.setData(4, Qt.UserRole, editor_text)

        if current is None:
            self.editor.clear()
            self.existing_editor.clear()
            self.editor.setReadOnly(True)
            return

        role = current.data(0, Qt.UserRole)
        if role == "entry":
            # Load stored edits if available
            edited_text = current.data(4, Qt.UserRole)
            if edited_text is not None:
                self.editor.setPlainText(edited_text)
            else:
                content = current.data(1, Qt.UserRole)
                display_text = _("Content:\n{}\n\nRelationships:\n").format(content)
                rel_found = False
                for rel_item in [current.child(k).child(l) 
                                for k in range(current.childCount()) 
                                for l in range(current.child(k).childCount()) 
                                if current.child(k).text(0) == _("Relationships")]:
                    if rel_item.data(2, Qt.UserRole) == "Active":
                        rel_name = rel_item.text(0)
                        rel_type = rel_item.data(1, Qt.UserRole)
                        edited_type = rel_item.data(4, Qt.UserRole)
                        display_text += f"- {rel_name}: {edited_type or rel_type}\n"
                        rel_found = True
                if not rel_found:
                    display_text += _("None")
                self.editor.setPlainText(display_text.strip())

            has_bold = False
            for rel_item in [current.child(k).child(l) 
                            for k in range(current.childCount()) 
                            for l in range(current.child(k).childCount()) 
                            if current.child(k).text(0) == _("Relationships")]:
                if rel_item.font(0).bold():
                    has_bold = True
                    break
            self.editor.setReadOnly(not has_bold)

            # Populate existing compendium editor
            cat_item = current.parent()
            if cat_item:
                key = f"{cat_item.text(0)}/{current.text(0)}"
                existing_data = None
                for cat in self.existing_compendium.get("categories", []):
                    for entry in cat.get("entries", []):
                        if f"{cat['name']}/{entry['name']}" == key:
                            existing_data = entry
                            break
                    if existing_data:
                        break
                if existing_data:
                    existing_text = _("Content:\n{}\n\nRelationships:\n").format(existing_data.get('content', ''))
                    rels = existing_data.get("relationships", [])
                    if rels:
                        for rel in rels:
                            existing_text += f"- {rel['name']}: {rel.get('type', 'Unknown')}\n"
                    else:
                        existing_text += _("None")
                    self.existing_editor.setPlainText(existing_text.strip())
                else:
                    self.existing_editor.setPlainText(_("This entry does not exist in the compendium yet."))

        elif role == "relationships":
            display_text = _("Relationships:\n")
            rel_found = False
            for i in range(current.childCount()):
                rel_item = current.child(i)
                if rel_item.data(2, Qt.UserRole) == "Active":
                    rel_name = rel_item.text(0)
                    rel_type = rel_item.data(1, Qt.UserRole)
                    edited_type = rel_item.data(4, Qt.UserRole)
                    display_text += f"- {rel_name}: {edited_type or rel_type}\n"
                    rel_found = True
            if not rel_found:
                display_text += _("None")
            self.editor.setPlainText(display_text.strip())
            self.editor.setReadOnly(True)
            # Show parent entry in existing editor
            entry_item = current.parent()
            cat_item = entry_item.parent()
            if cat_item:
                key = f"{cat_item.text(0)}/{entry_item.text(0)}"
                existing_data = None
                for cat in self.existing_compendium.get("categories", []):
                    for entry in cat.get("entries", []):
                        if f"{cat['name']}/{entry['name']}" == key:
                            existing_data = entry
                            break
                    if existing_data:
                        break
                if existing_data:
                    existing_text = _("Content:\n{}\n\nRelationships:\n").format(existing_data.get('content', ''))
                    rels = existing_data.get("relationships", [])
                    if rels:
                        for rel in rels:
                            existing_text += f"- {rel['name']}: {rel.get('type', 'Unknown')}\n"
                    else:
                        existing_text += _("None")
                    self.existing_editor.setPlainText(existing_text.strip())
                else:
                    self.existing_editor.setPlainText(_("This entry does not exist in the compendium yet."))

        elif role == "relationship":
            rel_name = current.text(0)
            rel_type = current.data(1, Qt.UserRole)
            edited_type = current.data(4, Qt.UserRole)
            if edited_type is not None:
                self.editor.setPlainText(f"{rel_name}: {edited_type}")
            else:
                self.editor.setPlainText(f"{rel_name}: {rel_type}")
            self.editor.setPlaceholderText(_("Edit the relationship type for {} (e.g., '{}: Trusted Friend').").format(rel_name, rel_name))
            self.editor.setReadOnly(not current.font(0).bold())
            # Show parent entry in existing editor
            entry_item = current.parent().parent()
            cat_item = entry_item.parent()
            if cat_item:
                key = f"{cat_item.text(0)}/{entry_item.text(0)}"
                existing_data = None
                for cat in self.existing_compendium.get("categories", []):
                    for entry in cat.get("entries", []):
                        if f"{cat['name']}/{entry['name']}" == key:
                            existing_data = entry
                            break
                    if existing_data:
                        break
                if existing_data:
                    existing_text = _("Content:\n{}\n\nRelationships:\n").format(existing_data.get('content', ''))
                    rels = existing_data.get("relationships", [])
                    if rels:
                        for rel in rels:
                            existing_text += f"- {rel['name']}: {rel.get('type', 'Unknown')}\n"
                    else:
                        existing_text += _("None")
                    self.existing_editor.setPlainText(existing_text.strip())
                else:
                    self.existing_editor.setPlainText(_("This entry does not exist in the compendium yet."))

        else:
            self.editor.clear()
            self.existing_editor.clear()
            self.editor.setReadOnly(True)
            self.editor.setPlaceholderText(_("Select an entry or relationship to view or edit its details."))

    def show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        role = item.data(0, Qt.UserRole)
        actions = {}

        if role == "entry":
            is_deleted = item.data(2, Qt.UserRole) == "Deleted"
            if is_deleted:
                actions["restore"] = menu.addAction(_("Restore"))
            else:
                actions["delete"] = menu.addAction(_("Ignore Update"))
                actions["rename"] = menu.addAction(_("Rename Entry"))
                actions["move_to"] = menu.addAction(_("Move To..."))
                actions["move_up"] = menu.addAction(_("Move Up"))
                actions["move_down"] = menu.addAction(_("Move Down"))
        elif role == "relationship":
            is_deleted = item.data(2, Qt.UserRole) == "Deleted"
            if is_deleted:
                actions["restore"] = menu.addAction(_("Restore Relationship"))
            else:
                actions["delete"] = menu.addAction(_("Remove Relationship"))
                actions["rename"] = menu.addAction(_("Rename Relationship"))
        else:
            return

        selected_action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
        if not selected_action:
            return

        for action_id, action in actions.items():
            if selected_action == action:
                if role == "entry":
                    if action_id == "restore":
                        self.restore_entry(item)
                    elif action_id == "delete":
                        self.delete_entry(item)
                    elif action_id == "rename":
                        self.rename_entry(item)
                    elif action_id == "move_to":
                        self.move_entry(item)
                    elif action_id == "move_up":
                        self.move_item(item, "up")
                    elif action_id == "move_down":
                        self.move_item(item, "down")
                elif role == "relationship":
                    if action_id == "restore":
                        self.restore_relationship(item)
                    elif action_id == "delete":
                        self.delete_relationship(item)
                    elif action_id == "rename":
                        self.rename_relationship(item)
                break

    def delete_entry(self, item):
        font = item.font(0)
        font.setStrikeOut(True)
        item.setFont(0, font)
        item.setData(2, Qt.UserRole, "Deleted")
        self.editor.clear()
        self.existing_editor.clear()
        self.editor.setReadOnly(True)

    def restore_entry(self, item):
        font = item.font(0)
        font.setStrikeOut(False)
        if item.data(2, Qt.UserRole) != "Unchanged":
            font.setBold(True)
        item.setFont(0, font)
        item.setFlags(item.flags() | Qt.ItemIsSelectable)
        item.setData(2, Qt.UserRole, "Modified" if item.data(2, Qt.UserRole) != "Unchanged" else "Unchanged")
        self.tree.setCurrentItem(item)

    def delete_relationship(self, item):
        font = item.font(0)
        font.setStrikeOut(True)
        item.setFont(0, font)
        item.setData(2, Qt.UserRole, "Deleted")
        item.setData(4, Qt.UserRole, None)  # Clear edits
        entry_item = item.parent().parent()
        rel_item = item.parent()
        if self.tree.currentItem() in [entry_item, rel_item, item]:
            self.on_item_changed(self.tree.currentItem(), None)

    def restore_relationship(self, item):
        font = item.font(0)
        font.setStrikeOut(False)
        if item.font(0).bold():
            font.setBold(True)
        item.setFont(0, font)
        item.setData(2, Qt.UserRole, "Active")
        entry_item = item.parent().parent()
        rel_item = item.parent()
        if self.tree.currentItem() in [entry_item, rel_item, item]:
            self.on_item_changed(self.tree.currentItem(), None)

    def rename_entry(self, item):
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, _("Rename Entry"), _("New name:"), text=old_name)
        if ok and new_name:
            item.setText(0, new_name)
            if self.tree.currentItem() == item:
                edited_text = item.data(4, Qt.UserRole)
                if edited_text is not None:
                    self.editor.setPlainText(edited_text)
                else:
                    content = item.data(1, Qt.UserRole)
                    display_text = _("Content:\n{}\n\nRelationships:\n").format(content)
                    rel_found = False
                    for rel_item in [item.child(k).child(l) 
                                    for k in range(item.childCount()) 
                                    for l in range(item.child(k).childCount()) 
                                    if item.child(k).text(0) == _("Relationships")]:
                        if rel_item.data(2, Qt.UserRole) == "Active":
                            rel_name = rel_item.text(0)
                            rel_type = rel_item.data(1, Qt.UserRole)
                            edited_type = rel_item.data(4, Qt.UserRole)
                            display_text += f"- {rel_name}: {edited_type or rel_type}\n"
                            rel_found = True
                    if not rel_found:
                        display_text += _("None")
                    self.editor.setPlainText(display_text.strip())

    def rename_relationship(self, item):
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, _("Rename Relationship"), _("New name:"), text=old_name)
        if ok and new_name:
            item.setText(0, new_name)
            if self.tree.currentItem() == item:
                edited_type = item.data(4, Qt.UserRole)
                if edited_type is not None:
                    unused, type_part = edited_type.split(": ", 1) if ": " in edited_type else (None, edited_type)
                    self.editor.setPlainText(f"{new_name}: {type_part}")
                    item.setData(4, Qt.UserRole, f"{new_name}: {type_part}")
                else:
                    rel_type = item.data(1, Qt.UserRole)
                    self.editor.setPlainText(f"{new_name}: {rel_type}")
            # Update entry editor if affected
            entry_item = item.parent().parent()
            if entry_item.data(4, Qt.UserRole) is not None:
                edited_text = entry_item.data(4, Qt.UserRole)
                parts = edited_text.split(_("\n\nRelationships:\n"))
                if len(parts) > 1:
                    rel_lines = parts[1].strip().split("\n")
                    updated_lines = []
                    for line in rel_lines:
                        if line.startswith(f"- {old_name}:"):
                            updated_lines.append(f"- {new_name}:{line[len(old_name)+3:]}")
                        else:
                            updated_lines.append(line)
                    entry_item.setData(4, Qt.UserRole, _("{}\n\nRelationships:\n").format(parts[0]) + "\n".join(updated_lines))

    def move_item(self, item, direction):
        parent = item.parent()
        index = parent.indexOfChild(item)
        if direction == "up" and index > 0:
            parent.takeChild(index)
            parent.insertChild(index - 1, item)
            self.tree.setCurrentItem(item)
        elif direction == "down" and index < parent.childCount() - 1:
            parent.takeChild(index)
            parent.insertChild(index + 1, item)
            self.tree.setCurrentItem(item)

    def move_entry(self, item):
        menu = QMenu(self)
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            if cat_item.data(0, Qt.UserRole) == "category":
                action = menu.addAction(cat_item.text(0))
                action.setData(cat_item)
        selected_action = menu.exec_(QCursor.pos())
        if selected_action:
            target_category = selected_action.data()
            current_parent = item.parent()
            current_parent.removeChild(item)
            target_category.addChild(item)
            target_category.setExpanded(True)
            self.tree.setCurrentItem(item)

    def save_and_close(self):
        try:
            new_data = {"categories": [], "extensions": {"entries": {}}}
            root = self.tree.invisibleRootItem()
            for i in range(root.childCount()):
                cat_item = root.child(i)
                cat_data = {"name": cat_item.text(0), "entries": []}
                for j in range(cat_item.childCount()):
                    entry_item = cat_item.child(j)
                    if entry_item.data(2, Qt.UserRole) != "Deleted":
                        entry_name = entry_item.text(0)
                        edited_text = entry_item.data(4, Qt.UserRole)

                        if edited_text is not None and self.tree.currentItem() == entry_item and not self.editor.isReadOnly():
                            editor_text = self.editor.toPlainText()
                            if editor_text.strip() and _("\n\nRelationships:\n") in editor_text:
                                parts = editor_text.split(_("\n\nRelationships:\n"))
                                if len(parts) > 1 and all(": " in line for line in parts[1].strip().split("\n") if line.startswith("- ")):
                                    edited_text = editor_text
                                else:
                                    edited_text = None  # Revert to stored if invalid

                        if edited_text is not None:
                            parts = edited_text.split(_("\n\nRelationships:\n"))
                            entry_content = parts[0].replace(_("Content:\n"), "").strip()
                            relationships = []
                            if len(parts) > 1:
                                rel_lines = parts[1].strip().split("\n")
                                for line in rel_lines:
                                    if line.startswith("- ") and ": " in line:
                                        name, rel_type = line[2:].split(": ", 1)
                                        rel_status = "Active"
                                        for rel_item in [entry_item.child(k).child(l) 
                                                        for k in range(entry_item.childCount()) 
                                                        for l in range(entry_item.child(k).childCount()) 
                                                        if entry_item.child(k).text(0) == _("Relationships")]:
                                            if rel_item.text(0) == name:
                                                rel_status = rel_item.data(2, Qt.UserRole)
                                                edited_type = rel_item.data(4, Qt.UserRole)
                                                if edited_type is not None and ": " in edited_type:
                                                    unused, rel_type = edited_type.split(": ", 1)
                                                break
                                        if rel_status == "Active":
                                            relationships.append({"name": name, "type": rel_type})
                        else:
                            entry_content = entry_item.data(1, Qt.UserRole)
                            relationships = [
                                {"name": rel_item.text(0), "type": rel_item.data(4, Qt.UserRole) or rel_item.data(1, Qt.UserRole)}
                                for rel_item in [entry_item.child(k).child(l) 
                                                for k in range(entry_item.childCount()) 
                                                for l in range(entry_item.child(k).childCount()) 
                                                if entry_item.child(k).text(0) == _("Relationships")]
                                if rel_item.data(2, Qt.UserRole) == "Active"
                            ]

                        # Override individual relationship edits if currently selected
                        if self.tree.currentItem() and self.tree.currentItem().data(0, Qt.UserRole) == "relationship" and not self.editor.isReadOnly():
                            rel_item = self.tree.currentItem()
                            rel_name = rel_item.text(0)
                            editor_text = self.editor.toPlainText()
                            if editor_text.strip() and ": " in editor_text:
                                unused, rel_type = editor_text.split(": ", 1)
                                for rel in relationships:
                                    if rel["name"] == rel_name:
                                        rel["type"] = rel_type
                                        break
                                else:
                                    if rel_item.data(2, Qt.UserRole) == "Active":
                                        relationships.append({"name": rel_name, "type": rel_type})

                        entry_data = {
                            "name": entry_name,
                            "content": entry_content,
                            "relationships": relationships
                        }
                        cat_data["entries"].append(entry_data)
                        new_data["extensions"]["entries"][entry_name] = {
                            "relationships": relationships
                        }
                if cat_data["entries"]:
                    new_data["categories"].append(cat_data)

            json.dumps(new_data)
            self.ai_compendium_data = new_data
            self.write_settings()
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to save: {}").format(str(e)))
            return

    def reject(self):
        self.write_settings()
        super().reject()

    def closeEvent(self, event):
        self.write_settings()
        event.accept()

    def get_compendium_data(self):
        return self.ai_compendium_data

    def zoom_in(self):
        if self.font_size < 24:
            self.font_size += 2
            self.update_font_size()

    def zoom_out(self):
        if self.font_size > 8:
            self.font_size -= 2
            self.update_font_size()

    def update_font_size(self):
        font = self.tree.header().font()
        font.setPointSize(self.font_size)
        self.tree.header().setFont(font)
        for i in range(self.tree.topLevelItemCount()):
            header_item = self.tree.topLevelItem(i)
            font = header_item.font(0)
            font.setPointSize(self.font_size)
            header_item.setFont(0, font)
            for j in range(header_item.childCount()):
                child_item = header_item.child(j)
                font = child_item.font(0)
                font.setPointSize(self.font_size)
                child_item.setFont(0, font)
                for k in range(child_item.childCount()):
                    rel_item = child_item.child(k)
                    font = rel_item.font(0)
                    font.setPointSize(self.font_size)
                    rel_item.setFont(0, font)
                    for l in range(rel_item.childCount()):
                        rel_child = rel_item.child(l)
                        font = rel_child.font(0)
                        font.setPointSize(self.font_size)
                        rel_child.setFont(0, font)
        
        font = self.editor.font()
        font.setPointSize(self.font_size)
        self.editor.setFont(font)
        font = self.existing_editor.font()
        font.setPointSize(self.font_size)
        self.existing_editor.setFont(font)

    def read_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        geometry = settings.value("prompt_preview/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.font_size = settings.value("ai_compendium_dialog/fontSize", 12, type=int)
        self.update_font_size()

    def write_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue("ai_compendium_dialog/geometry", self.saveGeometry())
        settings.setValue("ai_compendium_dialog/fontSize", self.font_size)
