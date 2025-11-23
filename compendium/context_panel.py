from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem, QTextEdit
from PyQt5.QtCore import Qt, pyqtSlot
from compendium.compendium_manager import CompendiumManager, CompendiumEventBus
from settings.selection_manager import SelectionManager

class ContextPanel(QWidget):
    """
    A panel that lets the user choose extra context for the prose prompt.
    It now displays two panels side-by-side:
      - Project: shows chapters and scenes from the project (only scenes are checkable).
      - Compendium: shows compendium entries organized by category.
    Selections persist until manually changed.
    """
    def __init__(self, project_structure, project_name, parent, enhanced_window=None):
        super().__init__(parent)
        self.project_structure = project_structure
        self.project_name = project_name
        self.controller = parent
        self.event_bus = CompendiumEventBus.get_instance()
        self.compendium_manager = CompendiumManager(project_name, event_bus=self.event_bus)
        self.selection_manager = SelectionManager(project_name, parent.metaObject().className())
        self.enhanced_window = enhanced_window
        self.uuid_map = {}
        self._building_tree = False
        self.init_ui()
        if hasattr(self.controller, "model") and self.controller.model:
            self.controller.model.structureChanged.connect(self.on_structure_changed)
        self.event_bus.add_updated_listener(self.update_compendium_tree)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter)

        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderHidden(True)
        self.build_project_tree()
        self.project_tree.itemChanged.connect(self.propagate_check_state)
        splitter.addWidget(self.project_tree)

        self.compendium_tree = QTreeWidget()
        self.compendium_tree.setHeaderHidden(True)
        self.build_compendium_tree()
        self.compendium_tree.itemChanged.connect(self.on_compendium_item_changed)
        splitter.addWidget(self.compendium_tree)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        self.setLayout(layout)

    def on_compendium_item_changed(self, item, column):
        """
        Handle compendium item changes, saving selections and propagating check states.
        """
        if not self._building_tree:
            self.selection_manager.save_selections(self.compendium_tree)
        self.propagate_check_state(item, column)

    def build_project_tree(self):
        """Build a tree from the project structure showing only chapters and scenes."""
        check_states = {}
        for uuid, item in self.uuid_map.items():
            if item.flags() & Qt.ItemIsUserCheckable:
                check_states[uuid] = item.checkState(0)

        self.project_tree.clear()
        self.uuid_map.clear()
        for act in self.project_structure.get("acts", []):
            act_item = QTreeWidgetItem(self.project_tree, [act.get("name", "Unnamed Act")])
            act_item.setFlags(act_item.flags() & ~Qt.ItemIsUserCheckable)
            act_item.setData(0, Qt.UserRole, {"type": "act", "data": act})
            self.uuid_map[act["uuid"]] = act_item

            if "summary" in act and not act["summary"].startswith("This is the summary"):
                summary_item = QTreeWidgetItem(act_item, ["Summary"])
                summary_item.setFlags(summary_item.flags() | Qt.ItemIsUserCheckable)
                summary_uuid = act["uuid"] + "_summary"
                summary_item.setCheckState(0, check_states.get(summary_uuid, Qt.Unchecked))
                summary_item.setData(0, Qt.UserRole, {"type": "summary", "data": act})
                self.uuid_map[summary_uuid] = summary_item

            for chapter in act.get("chapters", []):
                chapter_item = QTreeWidgetItem(act_item, [chapter.get("name", "Unnamed Chapter")])
                chapter_item.setFlags(chapter_item.flags() & ~Qt.ItemIsUserCheckable)
                chapter_item.setData(0, Qt.UserRole, {"type": "chapter", "data": chapter})
                self.uuid_map[chapter["uuid"]] = chapter_item

                if "summary" in chapter and not chapter["summary"].startswith("This is the summary"):
                    summary_item = QTreeWidgetItem(chapter_item, ["Summary"])
                    summary_item.setFlags(summary_item.flags() | Qt.ItemIsUserCheckable)
                    summary_uuid = chapter["uuid"] + "_summary"
                    summary_item.setCheckState(0, check_states.get(summary_uuid, Qt.Unchecked))
                    summary_item.setData(0, Qt.UserRole, {"type": "summary", "data": chapter})
                    self.uuid_map[summary_uuid] = summary_item

                for scene in chapter.get("scenes", []):
                    scene_item = QTreeWidgetItem(chapter_item, [scene.get("name", "Unnamed Scene")])
                    scene_item.setFlags(scene_item.flags() | Qt.ItemIsUserCheckable)
                    scene_item.setCheckState(0, check_states.get(scene["uuid"], Qt.Unchecked))
                    scene_item.setData(0, Qt.UserRole, {"type": "scene", "data": scene})
                    self.uuid_map[scene["uuid"]] = scene_item

        self.project_tree.expandAll()

    def build_compendium_tree(self):
        """Build a tree from the compendium data and restore selections."""
        self._building_tree = True
        self.compendium_tree.clear()
        data = self.compendium_manager.load_data()

        categories = data.get("categories", [])
        if isinstance(categories, dict):
            new_categories = [{"name": cat, "entries": entries} for cat, entries in categories.items()]
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
                item_path = f"{cat_name}/{entry_name}"
                entry_item.setCheckState(0, Qt.Checked if self.selection_manager.is_checked(item_path) else Qt.Unchecked)
                entry_item.setData(
                    0, Qt.UserRole, {"type": "compendium", "category": cat_name, "label": entry_name}
                )
        self.compendium_tree.expandAll()
        self._building_tree = False

    def restore_selection(self, selected_item_info):
        """Attempt to reselect the previously selected item."""
        if not selected_item_info:
            return
        item_type = selected_item_info["type"]
        item_name = selected_item_info["name"]
        if item_type == "category":
            for i in range(self.compendium_tree.topLevelItemCount()):
                cat_item = self.compendium_tree.topLevelItem(i)
                if cat_item.text(0) == item_name and cat_item.data(0, Qt.UserRole) == "category":
                    self.compendium_tree.setCurrentItem(cat_item)
                    return
        elif item_type == "entry":
            category_name = selected_item_info["category"]
            for i in range(self.compendium_tree.topLevelItemCount()):
                cat_item = self.compendium_tree.topLevelItem(i)
                if category_name and cat_item.text(0) != category_name:
                    continue
                for j in range(cat_item.childCount()):
                    entry_item = cat_item.child(j)
                    if entry_item.text(0) == item_name and entry_item.data(0, Qt.UserRole) == "entry":
                        self.compendium_tree.setCurrentItem(entry_item)
                        return
                if category_name and cat_item.text(0) == category_name:
                    if cat_item.childCount() > 0:
                        self.compendium_tree.setCurrentItem(cat_item.child(0))
                    else:
                        self.compendium_tree.setCurrentItem(cat_item)
                    return
        self.compendium_tree.clearSelection()

    def propagate_check_state(self, item, column):
        """
        Propagate check state changes to children and update parent items.
        """
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "summary" and item.checkState(column) == Qt.Checked:
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
                if child.flags() & Qt.ItemIsUserCheckable:
                    child.setCheckState(0, state)
        self.update_parent_check_state(item)

    def update_parent_check_state(self, item):
        parent = item.parent()
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

        self.update_parent_check_state(parent)

    def get_selected_context_text(self):
        """
        Collect selected text from both compendium and project panels for compatibility.
        """
        compendium_text = self.get_selected_compendium_text()
        story_text = self.get_selected_story_text()
        texts = [text for text in [compendium_text, story_text] if text]
        return "\n\n".join(texts) if texts else ""

    def get_selected_compendium_text(self):
        """Collect selected text from the compendium panel, formatted with headers."""
        texts = []
        for i in range(self.compendium_tree.topLevelItemCount()):
            cat_item = self.compendium_tree.topLevelItem(i)
            category = cat_item.text(0)
            for j in range(cat_item.childCount()):
                entry_item = cat_item.child(j)
                if entry_item.checkState(0) == Qt.Checked:
                    text = self.compendium_manager.get_text(category, entry_item.text(0))
                    texts.append(f"[Compendium Entry - {category} - {entry_item.text(0)}]:\n{text}")
        return "\n\n".join(texts) if texts else ""

    def get_selected_story_text(self):
        """Collect selected text from the project panel, formatted with headers."""
        texts = []
        temp_editor = QTextEdit()
        root = self.project_tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._traverse_project_item(root.child(i), texts, temp_editor)
        return "\n\n".join(texts) if texts else ""

    def _load_content(self, data_type, data, hierarchy):
        """Helper method to load content consistently for summaries and scenes."""
        if data_type == "summary":
            uuid_val = data.get("uuid")
            if uuid_val:
                return self.controller.model.load_summary(uuid=uuid_val)
        elif data_type == "scene":
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

        for i in range(item.childCount()):
            self._traverse_project_item(item.child(i), texts, temp_editor)

    def on_structure_changed(self, hierarchy, uuid):
        """Handle structure changes by updating the project tree."""
        if self.isHidden():
            return
        node = self.controller.model._get_node_by_hierarchy(hierarchy)
        if not node:
            if uuid in self.uuid_map:
                item = self.uuid_map[uuid]
                parent = item.parent() or self.project_tree.invisibleRootItem()
                parent.removeChild(item)
                del self.uuid_map[uuid]
                if uuid + "_summary" in self.uuid_map:
                    del self.uuid_map[uuid + "_summary"]
            return

        self.project_structure = self.controller.model.structure
        self.build_project_tree()
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

        if not summary_exists and not node["summary"].startswith("This is the summary"):
            summary_item = QTreeWidgetItem(["Summary"])
            summary_item.setFlags(summary_item.flags() | Qt.ItemIsUserCheckable)
            summary_item.setCheckState(0, Qt.Unchecked)
            summary_item.setData(0, Qt.UserRole, {"type": "summary", "data": node})
            current_item.insertChild(0, summary_item)
            self.project_tree.expandItem(current_item)
            self.uuid_map[uuid + "_summary"] = summary_item

        if summary_item:
            font = summary_item.font(0)
            font.setBold(True)
            summary_item.setFont(0, font)

    def update_compendium_tree(self, project_name):
        """Update the compendium tree if the project name matches."""
        if project_name == self.project_name and self.isVisible():
            self.build_compendium_tree()