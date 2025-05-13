import os
import json
import re
import uuid
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtCore import Qt
from settings.settings_manager import WWSettingsManager

def get_structure_file_path(project_name, backward_compat=False):
    """Return the path to the project-specific structure file."""
    sanitized = re.sub(r'\s+', '', project_name)
    structure_name = sanitized + '_structure.json'
    path = WWSettingsManager.get_project_path(sanitized, structure_name)
    if backward_compat:
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if os.path.exists(path): 
            oldpath = WWSettingsManager.get_project_path(file=structure_name)
            if os.path.exists(oldpath):
                newpath_modtime = os.path.getmtime(path)
                oldpath_modtime = os.path.getmtime(oldpath)
                if (oldpath_modtime > newpath_modtime):
                    os.rename(oldpath, path)
        else:
            # check in Projects home
            oldpath = WWSettingsManager.get_project_path(file=structure_name)
            if os.path.exists(oldpath):
                os.rename(oldpath, path)
            else:
                # check in cwd
                oldpath = os.path.join(os.getcwd(), structure_name)
                if os.path.exists(oldpath):
                    os.rename(oldpath, path)
    return path

def load_structure(project_name):
    """
    Load the project structure from the file.
    If the file is missing or in an unexpected format, return a default structure.
    """
    # The words "This is the summary" have special meaning, so we can't localize them
    structure = {"acts": [
        {"name": "Act 1", "summary": "This is the summary for Act 1.",
        "chapters": [
            {"name": "Chapter 1", "summary": "This is the summary for Chapter 1.",
            "scenes": [
                {"name": "Scene 1"}
            ]
            }
        ]
        }
    ]}
    file_path = get_structure_file_path(project_name, True)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            structure = json.load(f)
        
        # Add UUIDs to existing nodes
        def add_uuids(node):
            if "uuid" not in node:
                node["uuid"] = str(uuid.uuid4())
            for child in node.get("chapters", []) + node.get("scenes", []):
                add_uuids(child)
        for act in structure.get("acts", []):
            add_uuids(act)
        save_structure(project_name, structure)
    return structure

def save_structure(project_name, structure):
    """Save the given project structure to the file."""
    file_path = get_structure_file_path(project_name)
    try:
        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(structure, f, indent=4)
    except Exception as e:
        print("Error saving project structure:", e)

def populate_tree(tree, structure):
    """
    Populate the provided QTreeWidget with the project structure.
    The structure is expected to contain "acts", each with "chapters" and "scenes".
    If a node is not a dict or lacks a "name" key, it is converted to a dict using its string value.
    """
    def ensure_dict(node):
        if not isinstance(node, dict):
            return {"name": str(node), "uuid": str(uuid.uuid4())}
        # Ensure a "name" key exists.
        if "name" not in node:
            node["name"] = "Unnamed"
        if "uuid" not in node:
            node["uuid"] = str(uuid.uuid4())
        return node

    tree.clear()
    for act in structure.get("acts", []):
        act = ensure_dict(act)
        act_item = QTreeWidgetItem(tree, [act.get("name", "Unnamed Act")])
        act_item.setData(0, Qt.UserRole, act)
        for chapter in act.get("chapters", []):
            chapter = ensure_dict(chapter)
            chapter_item = QTreeWidgetItem(act_item, [chapter.get("name", "Unnamed Chapter")])
            chapter_item.setData(0, Qt.UserRole, chapter)
            for scene in chapter.get("scenes", []):
                scene = ensure_dict(scene)
                scene_item = QTreeWidgetItem(chapter_item, [scene.get("name", "Unnamed Scene")])
                scene_item.setData(0, Qt.UserRole, scene)
    tree.expandAll()

def update_structure_from_tree(tree, project_name):
    """
    Rebuild the project structure by traversing the QTreeWidget.
    Saves the updated structure and returns it.
    """
    structure = {"acts": []}
    root = tree.invisibleRootItem()
    for i in range(root.childCount()):
        act_item = root.child(i)
        act = act_item.data(0, Qt.UserRole)
        chapters = []
        for j in range(act_item.childCount()):
            chapter_item = act_item.child(j)
            chapter = chapter_item.data(0, Qt.UserRole)
            scenes = []
            for k in range(chapter_item.childCount()):
                scene_item = chapter_item.child(k)
                scene = scene_item.data(0, Qt.UserRole)
                scenes.append(scene)
            chapter["scenes"] = scenes
            chapters.append(chapter)
        act["chapters"] = chapters
        structure["acts"].append(act)
    save_structure(project_name, structure)
    return structure

def delete_node(tree, item, project_name):
    """
    Deletes the specified item from the QTreeWidget and updates the project structure.
    Returns the updated structure.
    """
    if item is None:
        return
    parent = item.parent()
    if parent is None:
        index = tree.indexOfTopLevelItem(item)
        if index != -1:
            tree.takeTopLevelItem(index)
    else:
        index = parent.indexOfChild(item)
        if index != -1:
            parent.takeChild(index)
    new_structure = update_structure_from_tree(tree, project_name)
    return new_structure
