#!/usr/bin/env python3
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtCore import Qt

def add_act(window):
    """Add a new act using ProjectModel."""
    text, ok = QInputDialog.getText(window, _("Add Act"), _("Enter act name:"))
    if ok and text.strip():
        window.model.add_act(text.strip())  # Delegate to ProjectModel
        # No need to update the tree here; ProjectModel emits structureChanged

def add_chapter(window, act_item):
    """Add a new chapter using ProjectModel."""
    text, ok = QInputDialog.getText(window, _("Add Chapter"), _("Enter chapter name:"))
    if ok and text.strip():
        act_name = act_item.text(0)
        window.model.add_chapter(act_name, text.strip())  # Delegate to ProjectModel
        # No need to update the tree here; ProjectModel emits structureChanged

def add_scene(window, chapter_item):
    """Add a new scene using ProjectModel."""
    text, ok = QInputDialog.getText(window, _("Add Scene"), _("Enter scene name:"))
    if ok and text.strip():
        chapter_name = chapter_item.text(0)
        act_item = chapter_item.parent()
        act_name = act_item.text(0)
        window.model.add_scene(act_name, chapter_name, text.strip())  # Delegate to ProjectModel
        # No need to update the tree here; ProjectModel emits structureChanged

def rename_item(window, item):
    """Rename a tree item and sync via ProjectModel."""
    current_name = item.text(0)
    new_name, ok = QInputDialog.getText(
        window, _("Rename"), _("Enter new name:"), text=current_name)
    if ok and new_name.strip():
        hierarchy = window.get_item_hierarchy(item)
        window.model.rename_node(hierarchy, new_name.strip())
        # Tree will update via structureChanged signal

def move_item_up(window, item):
    """Move an item up in the tree."""
    parent = item.parent() or window.project_tree.tree.invisibleRootItem()
    index = parent.indexOfChild(item)
    if index > 0:
        parent.takeChild(index)
        parent.insertChild(index - 1, item)
        window.project_tree.tree.setCurrentItem(item)
        hierarchy = window.get_item_hierarchy(item)
        uuid = item.data(0, Qt.UserRole)["uuid"]

        window.model.update_structure(window.project_tree.tree)
#        tree_manager.update_structure_from_tree(window.project_tree.tree, window.model.project_name)
        window.model.structureChanged.emit(hierarchy, uuid)

def move_item_down(window, item):
    """Move an item down in the tree."""
    parent = item.parent() or window.project_tree.tree.invisibleRootItem()
    index = parent.indexOfChild(item)
    if index < parent.childCount() - 1:
        parent.takeChild(index)
        parent.insertChild(index + 1, item)
        window.project_tree.tree.setCurrentItem(item)
        hierarchy = window.get_item_hierarchy(item)
        uuid = item.data(0, Qt.UserRole)["uuid"]
        window.model.update_structure(window.project_tree.tree)
#        tree_manager.update_structure_from_tree(window.project_tree.tree, window.model.project_name)
        window.model.structureChanged.emit(hierarchy, uuid)

