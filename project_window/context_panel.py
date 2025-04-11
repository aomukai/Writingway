import os
import json
import re
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem, QTextEdit
from PyQt5.QtCore import Qt
from compendium.compendium_manager import CompendiumManager
from settings.settings_manager import WWSettingsManager

class ContextPanel(QWidget):
    """
    A panel that lets the user choose extra context for the prose prompt.
    It now displays two panels side-by-side:
      - Project: shows chapters and scenes from the project (only scenes are checkable).
      - Compendium: shows compendium entries organized by category.
    Selections persist until manually changed.
    """

    def __init__(self, project_structure, project_name, parent=None):
        super().__init__(parent)
        self.project_structure = project_structure  # reference to the project structure
        self.project_name = project_name
        self.controller = parent
        self.compendium_manager = CompendiumManager(project_name)
        self.uuid_map = {}  # Map UUIDs to QTreeWidgetItems
        self.init_ui()
        if hasattr(self.controller, "model") and self.controller.model:
            self.controller.model.structureChanged.connect(self.on_structure_changed)

    def init_ui(self):
        # Use a horizontal layout to take advantage of the unused horizontal space.
        layout = QHBoxLayout(self)
        # QSplitter provides adjustable space between panels.
        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter)

        # Left: Project Structure
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderHidden(True)
        self.build_project_tree()
        # Propagate check state changes (if needed) for project tree items.
        self.project_tree.itemChanged.connect(self.propagate_check_state)
        splitter.addWidget(self.project_tree)

        # Right: Compendium
        self.compendium_tree = QTreeWidget()
        self.compendium_tree.setHeaderHidden(True)
        self.build_compendium_tree()
        self.compendium_tree.itemChanged.connect(self.propagate_check_state)
        splitter.addWidget(self.compendium_tree)

        # Optionally, set initial splitter ratios (here both panels share space equally)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        self.setLayout(layout)

    def build_project_tree(self):
        """Build a tree from the project structure showing only chapters and scenes."""
        self.project_tree.clear()
        self.uuid_map.clear()
        for act in self.project_structure.get("acts", []):
            # Create the Act item (not user-checkable)
            act_item = QTreeWidgetItem(
                self.project_tree, [act.get("name", "Unnamed Act")]
            )
            act_item.setFlags(act_item.flags() & ~Qt.ItemIsUserCheckable)
            self.uuid_map[act["uuid"]] = act_item

            # Add Summary item if it exists
            if "summary" in act and not act["summary"].startswith("This is the summary"):
                summary_item = QTreeWidgetItem(act_item, ["Summary"])
                summary_item.setFlags(summary_item.flags() | Qt.ItemIsUserCheckable)
                summary_item.setCheckState(0, Qt.Unchecked)
                summary_item.setData(
                    0, Qt.UserRole, {"type": "summary", "data": act}
                )
                self.uuid_map[act["uuid"] + "_summary"] = summary_item  # Unique key for summary

            for chapter in act.get("chapters", []):
                # Create the Chapter item (not user-checkable)
                chapter_item = QTreeWidgetItem(
                    act_item, [chapter.get("name", "Unnamed Chapter")]
                )
                chapter_item.setFlags(chapter_item.flags() & ~Qt.ItemIsUserCheckable)
                chapter_item.setData(
                    0, Qt.UserRole, {"type": "chapter", "data": chapter}
                )
                self.uuid_map[chapter["uuid"]] = chapter_item

                # Add Summary item if it exists
                if "summary" in chapter and not chapter["summary"].startswith("This is the summary"):
                    summary_item = QTreeWidgetItem(chapter_item, ["Summary"])
                    summary_item.setFlags(summary_item.flags() | Qt.ItemIsUserCheckable)
                    summary_item.setCheckState(0, Qt.Unchecked)
                    summary_item.setData(
                        0, Qt.UserRole, {"type": "summary", "data": chapter}
                    )
                    self.uuid_map[chapter["uuid"] + "_summary"] = summary_item

                for scene in chapter.get("scenes", []):
                    # Scenes remain checkable
                    scene_item = QTreeWidgetItem(
                        chapter_item, [scene.get("name", "Unnamed Scene")]
                    )
                    scene_item.setFlags(scene_item.flags() | Qt.ItemIsUserCheckable)
                    scene_item.setCheckState(0, Qt.Unchecked)
                    scene_item.setData(
                        0, Qt.UserRole, {"type": "scene", "data": scene}
                    )
                    self.uuid_map[scene["uuid"]] = scene_item

        self.project_tree.expandAll()

    def build_compendium_tree(self):
        """Build a tree from the compendium data."""
        self.compendium_tree.clear()
        data = self.compendium_manager.load_data()

        # Get categories from the new format (list) or legacy format (dict)
        categories = data.get("categories", [])
        if isinstance(categories, dict):
            # Legacy format: convert dict to list of category objects.
            new_categories = []
            for cat, entries in categories.items():
                new_categories.append({"name": cat, "entries": entries})
            categories = new_categories

        for cat in categories:
            cat_name = cat.get("name", "Unnamed Category")
            entries = cat.get("entries", [])
            cat_item = QTreeWidgetItem(self.compendium_tree, [cat_name])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsUserCheckable)
            for entry in sorted(entries, key=lambda e: e.get("name", "")):
                entry_name = entry.get("name", "Unnamed Entry")
                entry_item = QTreeWidgetItem(cat_item, [entry_name])
                entry_item.setFlags(entry_item.flags() | Qt.ItemIsUserCheckable)
                entry_item.setCheckState(0, Qt.Unchecked)
                entry_item.setData(
                    0, Qt.UserRole, {"type": "compendium", "category": cat_name, "label": entry_name}
                )
        self.compendium_tree.expandAll()

    def propagate_check_state(self, item, column):
        """
        Propagate check state changes to children and update parent items.
        This method can cause partial-check states on parent items if some children
        are checked. If you don't want partial checks at all, you can remove or
        simplify this logic.
        """
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "summary" and item.checkState(column) == Qt.Checked:
            # When summary is checked, uncheck all children of the parent
            parent = item.parent()
            if parent:
                for i in range(parent.childCount()):
                    child = parent.child(i)
                    if child != item and child.flags() & Qt.ItemIsUserCheckable:
                        child.setCheckState(0, Qt.Unchecked)
        elif item.childCount() > 0:
            state = item.checkState(column)
            for i in range(item.childCount()):
                child = item.child(i)
                # Only update children if they're user-checkable:
                if child.flags() & Qt.ItemIsUserCheckable:
                    child.setCheckState(0, state)
        self.update_parent_check_state(item)

    def update_parent_check_state(self, item):
        parent = item.parent()
        # If parent is not user-checkable, there's no checkbox to update
        if not parent or not (parent.flags() & Qt.ItemIsUserCheckable):
            return

        checked = sum(
            1
            for i in range(parent.childCount())
            if parent.child(i).checkState(0) == Qt.Checked
        )
        if checked == parent.childCount():
            parent.setCheckState(0, Qt.Checked)
        elif checked > 0:
            parent.setCheckState(0, Qt.PartiallyChecked)
        else:
            parent.setCheckState(0, Qt.Unchecked)

        # Recursively update further up
        self.update_parent_check_state(parent)

    def get_selected_context_text(self):
        """Collect selected text from both panels, formatted with headers."""
        texts = []
        temp_editor = QTextEdit()

        # Gather from Project panel
        root = self.project_tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._traverse_project_item(root.child(i), texts, temp_editor)

        # Gather from Compendium panel
        for i in range(self.compendium_tree.topLevelItemCount()):
            cat_item = self.compendium_tree.topLevelItem(i)
            category = cat_item.text(0)
            for j in range(cat_item.childCount()):
                entry_item = cat_item.child(j)
                if entry_item.checkState(0) == Qt.Checked:
                    text = self.compendium_manager.get_text(category, entry_item.text(0))
                    texts.append(f"[Compendium Entry - {category} - {entry_item.text(0)}]:\n{text}")

        if texts:
            return "\n\n".join(texts)
        return ""

    def _load_content(self, data_type, data, hierarchy):
        """Helper method to load content consistently for summaries and scenes."""
        if data_type == "summary":
            content = self.controller.model.load_summary(hierarchy)
            return content
        elif data_type == "scene":
            # Use existing autosave loading logic
            return self.controller.model.load_autosave(hierarchy) or data.get("content")
        return None

    def _traverse_project_item(self, item, texts, temp_editor):
        data = item.data(0, Qt.UserRole)
        hierarchy = self.controller.get_item_hierarchy(item)
        
        if data and item.checkState(0) == Qt.Checked:
            content_type = data.get("type")
            content = self._load_content(content_type, data.get("data"), hierarchy)
            
            if content:
                temp_editor.setHtml(content)
                content_text = temp_editor.toPlainText()
                if content_type == "summary":
                    texts.append(f"[Summary - {item.parent().text(0)}]:\n{content_text}")
                elif content_type == "scene":
                    texts.append(f"[Scene Content - {item.text(0)}]:\n{content_text}")
        
        # Recurse children
        for i in range(item.childCount()):
            self._traverse_project_item(item.child(i), texts, temp_editor)

    def on_structure_changed(self, hierarchy, uuid):
        """Handle structure changes by updating only affected items."""
        if self.isHidden():
            return # Panel will be populated when shown
        node = self.controller.model._get_node_by_hierarchy(hierarchy)
        if uuid in self.uuid_map:  # Existing node modified
            item = self.uuid_map[uuid]
            if node:  # Update (e.g., rename)
                item.setText(0, node["name"])
                item.setData(0, Qt.UserRole, {"type": item.data(0, Qt.UserRole)["type"], "data": node})
                self._update_item_for_summary(hierarchy, uuid)
            else:  # Delete
                parent = item.parent() or self.project_tree.invisibleRootItem()
                parent.removeChild(item)
                del self.uuid_map[uuid]
                if uuid + "_summary" in self.uuid_map:
                    del self.uuid_map[uuid + "_summary"]
        else:
            # Fallback to full rebuild if no current item
            self.build_project_tree()
            # Optionally call _update_item_for_summary(hierarchy, uuid) here if node exists
            if node:
                self._update_item_for_summary(hierarchy, uuid)

    def _update_item_for_summary(self, hierarchy, uuid):
        """Update or insert a summary checkbox for the item at the given hierarchy."""
        node = self.controller.model._get_node_by_hierarchy(hierarchy)
        if not node or "summary" not in node:
            return
        current_item = self.uuid_map.get(uuid)
        if not current_item:
            return

        # Check for existing "Summary" child
        summary_exists = False
        summary_item = None
        for i in range(current_item.childCount()):
            child = current_item.child(i)
            if child.text(0) == "Summary":
                summary_item = child
                summary_exists = True
                if node["summary"].startswith("This is the summary"):
                    current_item.removeChild(child)
                    del self.uuid_map[uuid + "_summary"]
                break

        # Add new "Summary" item if it doesn't exist and summary is meaningful
        if not summary_exists and not node["summary"].startswith("This is the summary"):
            summary_item = QTreeWidgetItem(["Summary"])
            summary_item.setFlags(summary_item.flags() | Qt.ItemIsUserCheckable)
            summary_item.setCheckState(0, Qt.Unchecked)
            summary_item.setData(0, Qt.UserRole, {"type": "summary", "data": node})
            current_item.insertChild(0, summary_item)  # Insert at the top
            self.project_tree.expandItem(current_item)  # Expand the parent item
            self.uuid_map[uuid + "_summary"] = summary_item

        # Apply bold formatting to the "Summary" item if it exists
        if summary_item:
            font = summary_item.font(0)
            font.setBold(True)
            summary_item.setFont(0, font)