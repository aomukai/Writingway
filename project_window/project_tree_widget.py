import uuid
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QMenu, 
                             QMessageBox, QInputDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from . import tree_manager
from . import project_structure_manager as psm

class ProjectTreeWidget(QWidget):
    """Left panel with the project structure tree."""
    def __init__(self, controller, model):
        super().__init__()
        self.controller = controller
        self.model = model
        self.tree = QTreeWidget()
        self.init_ui()
        self.model.structureChanged.connect(self.refresh_tree)
        self.model.errorOccurred.connect(self.show_error_message)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree.setHeaderLabels(["Name", "Status"])
        self.tree.setColumnCount(2)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.currentItemChanged.connect(self.controller.tree_item_changed)
        self.populate()

    def populate(self):
        """Populate the tree with the project structure."""
        tree_manager.populate_tree(self.tree, self.model.structure)
        self.assign_all_icons()

    def update_scene_status_icon(self, item):
        """Update the status icon for a scene item."""
        tint = self.controller.icon_tint
        status = item.data(0, Qt.UserRole).get("status", "To Do")
        icons = {
            "To Do": "assets/icons/circle.svg",
            "In Progress": "assets/icons/loader.svg",
            "Final Draft": "assets/icons/check-circle.svg"
        }
        item.setIcon(1, self.controller.get_tinted_icon(icons.get(status, ""), tint) if status in icons else QIcon())
        item.setText(1, "")

    def get_item_level(self, item):
        """Calculate the level of an item in the tree."""
        level = 0
        temp = item
        while temp.parent():
            level += 1
            temp = temp.parent()
        return level

    def refresh_tree(self, hierarchy, uuid):
        """Refresh the tree structure based on the model's data."""
        # Instead of full repopulation, sync specific changes
        self._sync_tree_with_structure(hierarchy, uuid)

    def _sync_tree_with_structure(self, hierarchy, uuid):
        """Synchronize the tree with the project structure incrementally."""
        def find_item_by_uuid(parent, target_uuid, level=0):
            for i in range(parent.childCount()):
                item = parent.child(i)
                item_data = item.data(0, Qt.UserRole)
                if item_data.get("uuid") == target_uuid:
                    return item, level
                found, found_level = find_item_by_uuid(item, target_uuid, level + 1)
                if found:
                    return found, found_level
            return None, -1

        root = self.tree.invisibleRootItem()
        item, level = find_item_by_uuid(root, uuid)
        if item:
            node = self.model._get_node_by_hierarchy(hierarchy)
            if node:  # Update or create
                item.setText(0, node["name"])
                item.setData(0, Qt.UserRole, node)
                self.assign_item_icon(item, level)
            else:  # Delete
                parent = item.parent() or root
                parent.removeChild(item)
        else:  # New item, rebuild or insert
            self.populate()  # Fallback to full rebuild for simplicity

    def get_item_level(self, item):
        """Calculate the level of an item in the tree."""
        level = 0
        temp = item
        while temp.parent():
            level += 1
            temp = temp.parent()
        return level

    def assign_item_icon(self, item, level):
        """Assign an icon to a tree item based on its level and status."""
        tint = self.controller.icon_tint
        scene_data = item.data(0, Qt.UserRole) or {"name": item.text(0), "status": "To Do"}

        if level < 2:  # Act or Chapter
            item.setIcon(0, self.controller.get_tinted_icon("assets/icons/book.svg", tint))
            item.setText(1, "")  # No status for acts or chapters
        else:  # Scene
            item.setIcon(0, self.controller.get_tinted_icon("assets/icons/edit.svg", tint))
            status = scene_data.get("status", "To Do")
            icons = {
                "To Do": "assets/icons/circle.svg",
                "In Progress": "assets/icons/loader.svg",
                "Final Draft": "assets/icons/check-circle.svg"
            }
            item.setIcon(1, self.controller.get_tinted_icon(icons.get(status, ""), tint) if status in icons else QIcon())
            item.setText(1, "")

    def assign_all_icons(self):
        """Recursively assign icons to all items in the tree."""
        def assign_icons_recursively(item, level=0):
            self.assign_item_icon(item, level)
            for i in range(item.childCount()):
                assign_icons_recursively(item.child(i), level + 1)

        for i in range(self.tree.topLevelItemCount()):
            assign_icons_recursively(self.tree.topLevelItem(i))

    def show_context_menu(self, pos):
        """Display context menu for tree items."""
        item = self.tree.itemAt(pos)
        menu = QMenu()
        hierarchy = self.controller.get_item_hierarchy(item) if item else []
        if not item:
            menu.addAction("Add Act", lambda: self.model.add_act(QInputDialog.getText(self, "Add Act", "Enter act name:")[0]))
        else:
            menu.addAction("Rename", lambda: psm.rename_item(self.controller, item))
            menu.addAction("Delete", lambda: self.model.delete_node(hierarchy))
            menu.addAction("Move Up", lambda: psm.move_item_up(self.controller, item))
            menu.addAction("Move Down", lambda: psm.move_item_down(self.controller, item))
            level = self.get_item_level(item)
            if level == 0:
                menu.addAction("Add Chapter", lambda: psm.add_chapter(self.controller, item))
            elif level == 1:
                menu.addAction("Add Scene", lambda: psm.add_scene(self.controller, item))
            if level >= 2:
                status_menu = menu.addMenu("Set Scene Status")
                for status in ["To Do", "In Progress", "Final Draft"]:
                    status_menu.addAction(status, lambda s=status: self.controller.set_scene_status(item, s))
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def show_error_message(self, message):
        """Display an error message to the user."""
        QMessageBox.warning(self, "Duplicate Name Error", message)