#!/usr/bin/env python3
import os
import time
import uuid
from typing import Optional
from PyQt5.QtCore import pyqtSignal, QObject
from . import project_settings_manager as psm
from compendium.compendium_manager import CompendiumManager
from settings.settings_manager import WWSettingsManager
from settings.autosave_manager import load_latest_autosave, save_scene, get_latest_autosave_path
from .tree_manager import load_structure, save_structure, update_structure_from_tree, get_structure_file_path

class ProjectModel(QObject):
    """Manages project data and persistence."""
    structureChanged = pyqtSignal(list, str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, project_name):
        super().__init__()
        self.project_name = project_name
        self.structure = load_structure(project_name)
        self.migrate_legacy_content()
        self.settings = self.load_settings()
        self.autosave_enabled = WWSettingsManager.get_setting("general", "enable_autosave", False)
        self.unsaved_changes = False
        self.last_saved_hierarchy = None
        self.compendium = CompendiumManager(project_name)

    def load_settings(self):
        settings = psm.load_project_settings(self.project_name)
        return {
            "global_pov": settings.get("global_pov", _("Third Person Limited")),
            "global_pov_character": settings.get("global_pov_character", _("Character")),
            "global_tense": settings.get("global_tense", _("Present Tense"))
        }

    def save_settings(self):
        psm.save_project_settings(self.project_name, self.settings)

    def update_structure(self, tree):
        old_structure = self.structure
        self.structure = update_structure_from_tree(tree, self.project_name)
        def merge_fields(old_node, new_node):
            if old_node.get("uuid") == new_node.get("uuid"):
                if "latest_file" in old_node:
                    new_node["latest_file"] = old_node["latest_file"]
                if "has_summary" in old_node:
                    new_node["has_summary"] = old_node["has_summary"]
                if "summary" in old_node:
                    new_node["summary"] = old_node["summary"]
            for key in ["chapters", "scenes"]:
                if key in old_node and key in new_node:
                    for old_child, new_child in zip(old_node[key], new_node[key]):
                        merge_fields(old_child, new_child)
        for old_act, new_act in zip(old_structure.get("acts", []), self.structure.get("acts", [])):
            merge_fields(old_act, new_act)
        self.save_structure()

    def save_structure(self):
        save_structure(self.project_name, self.structure)

    def load_autosave(self, hierarchy, node: Optional[dict]=None):
        return load_latest_autosave(self.project_name, hierarchy, node)

    def migrate_legacy_content(self):
        def traverse_and_migrate(node, hierarchy):
            if "content" in node:
                uuid_val = node.setdefault("uuid", str(uuid.uuid4()))
                latest_autosave_path = get_latest_autosave_path(self.project_name, hierarchy)
                if not latest_autosave_path:
                    filepath = save_scene(self.project_name, hierarchy, uuid_val, node["content"])
                    if filepath:
                        del node["content"]
                        node["latest_file"] = filepath
                else:
                    del node["content"]
            if "summary" in node:
                node["has_summary"] = not node["summary"].startswith("This is the summary")
            if "chapters" in node:
                for i, chapter in enumerate(node["chapters"]):
                    traverse_and_migrate(chapter, hierarchy + [chapter["name"]])
            if "scenes" in node:
                for i, scene in enumerate(node["scenes"]):
                    traverse_and_migrate(scene, hierarchy + [scene["name"]])
        file_path = get_structure_file_path(self.project_name)
        backup_path = file_path + ".backup"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        if os.path.exists(file_path):
            os.rename(file_path, backup_path)
        acts = self.structure.get("acts", [])
        for act in acts:
            traverse_and_migrate(act, [act["name"]])
        if os.path.exists(backup_path):
            self.save_structure()

    def load_scene_content(self, hierarchy) -> Optional[str]:
        node = self._get_node_by_hierarchy(hierarchy)
        if not node:
            return None
        uuid_val = node.setdefault("uuid", str(uuid.uuid4()))
        content = load_latest_autosave(self.project_name, hierarchy, node)
        if content is None and "content" in node:
            content = node["content"]
            filepath = save_scene(self.project_name, hierarchy, uuid_val, content)
            if filepath:
                del node["content"]
                node["latest_file"] = filepath
                self.save_structure()
                self.structureChanged.emit(hierarchy, uuid_val)
        elif content and "latest_file" not in node:
            latest_autosave = get_latest_autosave_path(self.project_name, hierarchy)
            if latest_autosave:
                node["latest_file"] = latest_autosave
                self.save_structure()
        if content and content.startswith("<!-- UUID:"):
            content = "\n".join(content.split("\n")[1:])
        return content

    def save_scene(self, hierarchy, content, expected_project_name: Optional[str]=None):
        node = self._get_node_by_hierarchy(hierarchy)
        if not node:
            return None
        uuid_val = node.setdefault("uuid", str(uuid.uuid4()))
        filepath = save_scene(self.project_name, hierarchy, uuid_val, content, expected_project_name=expected_project_name)
        if filepath:
            if "content" in node:
                del node["content"]
            node["latest_file"] = filepath
            self.save_structure()
            self.structureChanged.emit(hierarchy, uuid_val)
        return filepath
    
    def save_summary(self, hierarchy, summary_text):
        node = self._get_node_by_hierarchy(hierarchy)
        if not node:
            return False
        uuid_val = node.setdefault("uuid", str(uuid.uuid4()))
        try:
            node["summary"] = summary_text
            node["has_summary"] = bool(summary_text.strip())
            if not summary_text.strip():
                self.errorOccurred.emit(_("Warning: Saved empty summary for {}. Use 'Delete Summary' to clear it.").format("/".join(hierarchy)))
            self.save_structure()
            self.last_saved_hierarchy = hierarchy
            self.structureChanged.emit(hierarchy, uuid_val)
            return True
        except Exception as e:
            print(f"Error saving summary for {hierarchy}: {e}")
            return False
    
    def save_summary_to_file(self, hierarchy, summary_text):
        """
        Save the summary to a file and update the structure with the filepath.
        
        Args:
            hierarchy (list): The hierarchy path to the act or chapter (e.g., ["Act 1", "Chapter 1"]).
            summary_text (str): The summary content to save.
        
        Returns:
            str: The filepath where the summary was saved, or None if failed.
        """

        node = self._get_node_by_hierarchy(hierarchy)
        if not node:
            return False
        uuid_val = node.setdefault("uuid", str(uuid.uuid4()))

        # Generate a unique filename for the summary
        sanitized_project_name = WWSettingsManager.sanitize(self.project_name)
        sanitized_hierarchy = "-".join(WWSettingsManager.sanitize(h) for h in hierarchy)
        timestamp = time.strftime("%Y%m%d%H%M%S")
        filename = f"{sanitized_project_name}-{sanitized_hierarchy}-Summary_{timestamp}.html"
        filepath = WWSettingsManager.get_project_relpath(self.project_name, filename)

        # Embed UUID in the summary content
        summary_with_uuid = f"<!-- UUID: {uuid_val} -->\n{summary_text}"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(summary_with_uuid)
            # Update the structure to reference the file instead of storing the text
            if "summary" in node:
                del node["summary"]

            node["latest_file"] = filepath  # Track latest summary file
            self.save_structure()
            self.last_saved_hierarchy = hierarchy
            self.structureChanged.emit(hierarchy, uuid_val)
            return filepath
        except Exception as e:
            print(f"Error saving summary to {filepath}: {e}")
            return None


    def reset_summary(self, hierarchy):
        node = self._get_node_by_hierarchy(hierarchy)
        if not node:
            return False
        uuid_val = node.get("uuid")
        node["has_summary"] = False
        del node["summary"]
        self.save_structure()
        self.structureChanged.emit(hierarchy, uuid_val)
        return True

    def load_summary(self, hierarchy: Optional[list] = None, uuid: Optional[str] = None) -> Optional[str]:
        if uuid and hierarchy:
            raise ValueError(_("Provide either uuid or hierarchy, not both"))
        if not uuid and not hierarchy:
            raise ValueError(_("Either uuid or hierarchy must be provided"))
        node = None
        if uuid:
            node = self._find_node_by_uuid(self.structure.get("acts", []), uuid)
        elif hierarchy:
            node = self._get_node_by_hierarchy(hierarchy)
        if node and "summary" in node and node.get("has_summary", False):
            summary = node["summary"]
            if WWSettingsManager.is_project_file_path(summary):
                return self._load_summary_from_file(node, summary)
            if summary.strip() and len(summary.strip()) >= 10:
                return summary
            print(f"DEBUG: Summary for {hierarchy or uuid} is empty or too short (<10 chars)")
        elif node and node.get("has_summary", False): # node is saved to file
            return self._load_summary_from_file(node)
        return None
    
    def _load_summary_from_file(self, node: dict, summary_file:Optional[str] = None):
        if not summary_file:
            summary_file = node.get("latest_file", '')
        if summary_file and os.path.exists(summary_file):
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Strip UUID comment
                    if content.startswith("<!-- UUID:"):
                        content = "\n".join(content.split("\n")[1:])
                    return content
            except Exception as e:
                print(f"Error loading summary from {summary_file}: {e}")
                return None
        return None

    
    def _find_node_by_uuid(self, nodes, target_uuid):
        for node in nodes:
            if node.get("uuid") == target_uuid:
                return node
            for child in node.get("chapters", []) + node.get("scenes", []):
                result = self._find_node_by_uuid([child], target_uuid)
                if result:
                    return result
        return None
    
    def _check_duplicate_name(self, nodes, name, exclude_uuid=None):
        for node in nodes:
            if node["name"] == name and (exclude_uuid is None or node["uuid"] != exclude_uuid):
                return True
        return False
    
    def add_act(self, act_name):
        if self._check_duplicate_name(self.structure.get("acts", []), act_name):
            self.errorOccurred.emit(_("An Act named '{}' already exists. Please choose a unique name.").format(act_name))
            return
        new_act = {
            "uuid": str(uuid.uuid4()),
            "name": act_name,
            "summary": _("This is the summary for {}.").format(act_name),
            "has_summary": False,
            "chapters": []
        }
        self.structure.setdefault("acts", []).append(new_act)
        self.save_structure()
        self.structureChanged.emit([act_name], new_act["uuid"])

    def add_chapter(self, act_name, chapter_name):
        for act in self.structure.get("acts", []):
            if act.get("name") == act_name:
                if self._check_duplicate_name(act.get("chapters", []), chapter_name):
                    self.errorOccurred.emit(_("A Chapter named '{}' already exists in Act '{}'. Please choose a unique name.").format(chapter_name, act_name))
                    return
                new_chapter = {
                    "uuid": str(uuid.uuid4()),
                    "name": chapter_name,
                    "summary": _("This is the summary for {}.").format(chapter_name),
                    "has_summary": False,
                    "scenes": []
                }
                act.setdefault("chapters", []).append(new_chapter)
                self.save_structure()
                self.structureChanged.emit([act_name, chapter_name], new_chapter["uuid"])
                break

    def add_scene(self, act_name, chapter_name, scene_name):
        for act in self.structure.get("acts", []):
            if act.get("name") == act_name:
                for chapter in act.get("chapters", []):
                    if chapter.get("name") == chapter_name:
                        if self._check_duplicate_name(chapter.get("scenes", []), scene_name):
                            self.errorOccurred.emit(_("A Scene named '{}' already exists in Chapter '{}' of Act '{}'. Please choose a unique name.").format(scene_name, chapter_name, act_name))
                            return
                        new_scene = {
                            "uuid": str(uuid.uuid4()),
                            "name": scene_name
                        }
                        chapter.setdefault("scenes", []).append(new_scene)
                        self.save_structure()
                        self.structureChanged.emit([act_name, chapter_name, scene_name], new_scene["uuid"])
                        break
                break

    def rename_node(self, hierarchy, new_name):
        node = self._get_node_by_hierarchy(hierarchy)
        if not node:
            return
        uuid_val = node["uuid"]
        parent_nodes = self._get_parent_nodes(hierarchy)
        if self._check_duplicate_name(parent_nodes, new_name, exclude_uuid=uuid_val):
            level_name = "Act" if len(hierarchy) == 1 else "Chapter" if len(hierarchy) == 2 else "Scene"
            parent_context = " in " + " -> ".join(hierarchy[:-1]) if len(hierarchy) > 1 else ""
            self.errorOccurred.emit(_("A {} named '{}' already exists {}. Please choose a unique name.").format(level_name, new_name, parent_context))
            return
        old_hierarchy = hierarchy.copy()
        node["name"] = new_name
        self.save_structure()
        new_hierarchy = old_hierarchy[:-1] + [new_name]
        self.structureChanged.emit(new_hierarchy, uuid_val)

    def _get_parent_nodes(self, hierarchy):
        if not hierarchy:
            return []
        current = self.structure.get("acts", [])
        for level, name in enumerate(hierarchy[:-1]):
            for item in current:
                if item.get("name") == name:
                    current = item.get("chapters" if level == 0 else "scenes", [])
                    break
        return current
    
    def delete_node(self, hierarchy):
        node = self._get_node_by_hierarchy(hierarchy)
        uuid_val = node.get("uuid") or None
        parent, index = self._get_parent_and_index(hierarchy)
        if parent and index is not None:
            parent.pop(index)
            self.save_structure()
            self.structureChanged.emit(hierarchy, uuid_val)

    def _get_node_by_hierarchy(self, hierarchy):
        current = self.structure.get("acts", [])
        for level, name in enumerate(hierarchy):
            for item in current:
                if item.get("name") == name:
                    if level == len(hierarchy) - 1:
                        return item
                    current = item.get("chapters" if level == 0 else "scenes", [])
                    break
        return None

    def _get_parent_and_index(self, hierarchy):
        current = self.structure.get("acts", [])
        for level, name in enumerate(hierarchy[:-1]):
            for item in current:
                if item.get("name") == name:
                    current = item.get("chapters" if level == 0 else "scenes", [])
                    break
        for i, item in enumerate(current):
            if item.get("name") == hierarchy[-1]:
                return current, i
        return None, None